## Context

The set-core orchestration pipeline has 5 stages where design context would be valuable:

1. **Decompose** (skill, runs in Claude Code session → has MCP access)
2. **Planner** (bash, `run_claude` = `claude -p` → needs `--mcp-config` for MCP)
3. **Dispatcher** (bash, builds proposal.md → injects static context, no live MCP needed)
4. **Agent runtime** (Claude Code via wt-loop → has MCP access natively)
5. **Verifier** (bash, `run_claude` → needs `--mcp-config` for MCP)

The key discovery: `claude -p` supports `--mcp-config <json>`, so bash stages CAN access MCP if we pass the config. This means one unified approach works everywhere — no REST API fallback needed.

Current `run_claude()` in `wt-common.sh`:
```bash
exec env -u CLAUDECODE claude -p "$(cat '$tmpprompt')" --dangerously-skip-permissions $quoted_args
```

The `set-orch-core` Python bridge (`bin/set-orch-core`) handles state init and template rendering. The design-bridge could be Python too, but detection/config-export is simple enough for bash. Template rendering for design prompt sections could use `set-orch-core template` later.

## Goals / Non-Goals

**Goals:**
- Detect registered design MCP servers from `.claude/settings.json`
- Export MCP config as JSON file for `--mcp-config` passthrough
- Generate design-aware prompt sections for planner/verifier
- Inject design references per-change in dispatcher's proposal.md
- Provide agent rule template for runtime design queries
- Surface missing design elements as ambiguities

**Non-Goals:**
- Implementing a specific Figma adapter (that's `set-project-web`)
- Writing to design tools (read-only in v1)
- Design token extraction pipeline (future)
- Design compliance scoring in verifier (future)
- Supporting the community write MCP server

## Decisions

### D1: Detection via .claude/settings.json MCP registry

**Decision:** Detect design MCP servers by scanning `.claude/settings.json` for MCP server entries whose name matches known design tool patterns (`figma`, `penpot`, `sketch`, etc).

**Implementation:**
```bash
detect_design_mcp() {
    local settings="${PROJECT_ROOT}/.claude/settings.json"
    [[ -f "$settings" ]] || return 1

    # Check mcpServers keys for known design tools
    local design_server
    design_server=$(jq -r '
      .mcpServers // {} | keys[] |
      select(test("^(figma|penpot|sketch|zeplin)"))
    ' "$settings" 2>/dev/null | head -1)

    [[ -n "$design_server" ]] && echo "$design_server" || return 1
}
```

**Rationale:** The MCP registration is already in `.claude/settings.json` (set by `claude mcp add`). No additional config needed — if the user registered a Figma MCP, we detect it.

**Alternatives considered:**
- Dedicated config file (`.claude/design.yaml`) — rejected, adds config surface for no benefit
- Environment variable (`DESIGN_MCP_NAME`) — rejected, doesn't compose with existing MCP registration

### D2: MCP config export for run_claude passthrough

**Decision:** Extract the design MCP server config from `.claude/settings.json` and write it to a temp JSON file compatible with `claude --mcp-config`.

**Implementation:**
```bash
get_design_mcp_config() {
    local settings="${PROJECT_ROOT}/.claude/settings.json"
    local server_name="$1"  # from detect_design_mcp

    local config_file
    config_file=$(mktemp --suffix=.json)

    jq --arg name "$server_name" '{
      mcpServers: { ($name): .mcpServers[$name] }
    }' "$settings" > "$config_file"

    echo "$config_file"
}
```

Then `run_claude` gains:
```bash
local mcp_config="${DESIGN_MCP_CONFIG:-}"
if [[ -n "$mcp_config" ]]; then
    quoted_args+=" --mcp-config $mcp_config"
fi
```

**Rationale:** `claude --mcp-config` accepts a JSON file with the same format as `.claude/settings.json` (subset). We extract just the design server entry.

### D3: Prompt enrichment — conditional design section

**Decision:** When a design MCP is detected, inject a design instruction section into the planner/verifier prompts. The section tells the LLM that design tools are available via MCP and how to use them.

**Implementation:**
```bash
design_prompt_section() {
    local server_name="$1"
    local design_file_ref="${DESIGN_FILE_REF:-}"  # e.g., "figma://file/XYZ"

    cat <<EOF
## Design Context

A design tool ($server_name) is available via MCP. You can query it for:
- Frame/page inventory: what screens/views are designed
- Component details: properties, variants, states
- Design tokens: colors, spacing, typography, shadows
- Layout information: auto-layout, constraints, dimensions

${design_file_ref:+Design file reference: $design_file_ref}

When planning changes that involve UI:
- Query the design tool to understand what frames exist
- Map each change to specific design frames
- If a required frame/page is MISSING from the design, flag it as an ambiguity
- Include design frame references in change scope descriptions
EOF
}
```

**Rationale:** The LLM needs explicit instructions to use MCP tools — just having them available isn't enough. The prompt section tells it what's possible and when to query.

### D4: Dispatcher — design references in proposal.md

**Decision:** The dispatcher checks if the plan's change entry has a `design_ref` field (set by decompose or planner) and injects it into the proposal.md.

**Implementation in dispatcher.sh:**
```bash
# After existing proposal sections
local design_ref
design_ref=$(jq -r --arg n "$change_name" \
    '.changes[] | select(.name == $n) | .design_ref // empty' "$plan_file")
if [[ -n "$design_ref" ]]; then
    cat >> "$proposal_path" <<EOF

## Design Reference
Frame: $design_ref
Query the design MCP tool for detailed specifications when implementing UI elements.
EOF
fi
```

**Rationale:** Static reference injection is cheap and reliable. The agent then uses MCP at runtime for live details.

### D5: Agent rule template for runtime design queries

**Decision:** Deploy a rule file (`templates/rules/design-bridge-rule.md`) to projects with a design MCP. The rule instructs agents to query the design tool when implementing UI.

**Template:**
```markdown
# Design Tool Integration

This project has a design tool connected via MCP. When implementing UI:
1. Query the design tool for the relevant frame/page before writing CSS/components
2. Use exact colors, spacing, and typography from design tokens
3. Match component structure to design components
4. If a design element is missing, note it in your reflection
```

**Rationale:** Rules are always loaded into Claude Code context. This is the most reliable way to ensure agents use the design MCP during implementation.

### D6: Ambiguity flow for missing design elements

**Decision:** Reuse the existing ambiguity mechanism. When decompose or planner finds a function/page that has no corresponding design frame, it adds it to the plan's ambiguities. The orchestrator's existing ambiguity handling (pause + user notification) applies.

**No new code needed** — just prompt instructions telling decompose/planner to flag missing frames as ambiguities in the standard format.

### D7: Design file reference in orchestration config

**Decision:** The design file reference (e.g., Figma file URL/ID) is stored in `.claude/orchestration.yaml` under a `design_file` key. This is set by the project template init (e.g., `set-project-web` asks "Van Figma fájlod?").

```yaml
# .claude/orchestration.yaml
design_file: "https://www.figma.com/file/XYZ..."
```

The bridge reads this and passes it as `DESIGN_FILE_REF` to prompt sections.

**Rationale:** `orchestration.yaml` already holds project-specific orchestration config. Design file reference is another orchestration concern.

## Risks / Trade-offs

**[Risk: MCP rate limits (Pro = 200/day)]**
- Mitigation: Design queries are infrequent — decompose (1-2 calls), planner (1-2), per-agent (5-10). A 7-change run uses ~60-80 calls. Well within 200/day.

**[Risk: run_claude + --mcp-config overhead]**
- Mitigation: MCP connection is per-invocation. The design MCP is HTTP-based (remote server), so connection is fast (~100ms). Only invoked when design prompt section triggers a tool call.

**[Risk: Design MCP unavailable during run]**
- Mitigation: All design-bridge functions are non-fatal. If detection fails or MCP is unreachable, the pipeline continues without design context — identical to today's behavior.

**[Risk: Prompt bloat from design section]**
- Mitigation: Design prompt section is ~150 tokens. Only injected when design MCP is detected.

## Migration Plan

1. Add `lib/design/bridge.sh` with detection + config export + prompt section
2. Extend `run_claude()` with `--mcp-config` passthrough
3. Wire into planner.sh and dispatcher.sh
4. Add decompose skill instructions
5. Add agent rule template
6. Deploy to projects via `set-project init`

No migration needed for existing projects — design-bridge is purely additive. Projects without design MCP see zero change.
