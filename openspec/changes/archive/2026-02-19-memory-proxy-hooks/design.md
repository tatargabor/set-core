## Context

Currently 5 separate bash hook scripts handle memory. Each independently checks health, parses JSON, calls `set-memory recall/proactive`, and formats output. PreToolUse only fires on regex-matched Bash commands. There is no PostToolUse hook, no MCP integration, and no way for the LLM to actively interact with memory.

The shodh-memory upstream uses two integration layers:
1. **Hooks** (`memory-hook.ts`): single handler for 6 events, calling REST API on every tool use
2. **MCP server** (`@shodh/memory-mcp`): 15 tools the LLM can call directly (remember, recall, proactive_context, etc.)

Both layers talk to the same shodh REST server on localhost:3030. The Rust binary auto-starts with the MCP server.

### Shodh source analysis (point-by-point reference)

**hooks/claude-settings.json:**
- 6 events: SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, SubagentStop, Stop
- PreToolUse matches: Edit, Write, Bash
- PostToolUse matches: Edit, Write, Bash, TodoWrite, Read, Task
- Single handler: `bun run $SHODH_HOOKS_DIR/memory-hook.ts <EventName>`

**hooks/memory-hook.ts:**
- `surfaceProactiveContext()` — core function called by most events, queries `/api/relevant`
- PostToolUse:Read → surfaces file-specific context after reading
- PostToolUse:Bash → stores error patterns for learning, surfaces related fixes
- PostToolUse:Edit/Write → logs FileAccess memories
- Stop → captures last user-assistant exchange from transcript

**mcp-server/index.ts:**
- Auto-spawns shodh binary server on first connect (~15MB binary + ~23MB embedding model)
- Exposes 15 MCP tools: remember, recall, proactive_context, list_memories, forget, memory_stats, etc.
- REST API at localhost:3030, same server hooks call

**src/handlers/recall.rs:**
- `/api/recall`: hybrid retrieval (semantic search + graph traversal + Hebbian coactivation)
- `/api/relevant` (proactive_context): 5 parallel operations via tokio::join! — reminders, todos, facts, memories, response processing. Quality gates: min 0.05, relative 30% of top. Target <30ms.
- Anti-echo filter: >70% word overlap → skip (prevents surfacing what agent just wrote)

**src/python.rs:**
- PyO3 FFI — Python calls Rust directly, no HTTP. Our `set-memory` CLI uses this path.
- Same MemorySystem struct as the REST server, just different access method.

## Goals / Non-Goals

**Goals:**
- Adopt shodh's two-layer model: hooks (passive) + MCP (active)
- Single unified hook handler replacing 5 scripts
- PostToolUse hooks for Read, Edit, Write, Bash, Task, Grep
- MCP server registration giving LLM direct memory tools
- Session-level dedup cache
- Clean up all old .md memory references
- Updated CLAUDE.md with hook + MCP instructions

**Non-Goals:**
- Building our own MCP server (use shodh's `@shodh/memory-mcp` directly)
- Building our own REST server (shodh's MCP auto-starts it)
- Changing shodh-memory internals or the set-memory CLI
- LLM API traffic proxying (hooks + MCP is sufficient, as shodh proves)

## Decisions

### Decision 1: Build own MCP server wrapping set-memory CLI
**Choice:** Build a Python MCP server that shells out to `set-memory` commands, registered as `set-memory` in Claude Code.

**Rationale:** shodh's MCP server (`@shodh/memory-mcp`) bypasses our `set-memory` layer — no branch boosting, no auto-tagging, no export/import/sync. By wrapping our own CLI, all custom logic applies equally to hooks and MCP. The shodh MCP pattern (tool definitions → subprocess calls) is the template we follow, but targeting `set-memory` commands instead of REST :3030.

**Configuration:**
```bash
claude mcp add set-memory -- python /path/to/set-memory-mcp-server.py
```

**Tool catalog (~20 tools):**
- Core: remember, recall, proactive_context, forget, forget_by_tags, list_memories, get_memory, context_summary, brain, memory_stats
- Maintenance: health, audit, cleanup, dedup
- Sync: sync, sync_push, sync_pull, sync_status
- Export/Import: export, import_memories

### Decision 2: Hooks call set-memory CLI, not REST API
**Choice:** Hooks continue using `set-memory recall`/`set-memory proactive` (Python FFI), not the REST API.

**Rationale:** Our hooks already work with the CLI. The Python FFI path (~200ms) is fast enough. The REST API requires the server to be running, which the MCP server handles — but hooks fire even when MCP isn't loaded. CLI path is always available.

**Alternative considered:** Having hooks call localhost:3030 like shodh's TypeScript hooks. Rejected because it adds a dependency on the server being up.

### Decision 3: Single unified handler
**Choice:** Single `bin/wt-hook-memory` bash script with `case "$1"` dispatching.

**Rationale:** 5 scripts share ~80% code. Same pattern as shodh's single `memory-hook.ts`. Enables shared session cache and single health check.

### Decision 4: Session dedup cache
**Choice:** `/tmp/set-memory-session-<ID>.json` tracking seen queries.

**Mechanism:** hash(event+tool+query)[:16] as key. If seen → exit 0. `session_id` from hook input JSON (not env var).

**Cache lifecycle:**
- `SessionStart(source=startup)` → clear cache (new session)
- `SessionStart(source=clear)` → clear cache (user reset)
- `SessionStart(source=resume)` → keep cache (continuing)
- `SessionStart(source=compact)` → keep cache (context compressed mid-session)

### Decision 5: MCP + hooks coexistence via single path
**Choice:** Both layers active simultaneously, both going through `set-memory` CLI.

**How they work together:**
- **Hooks** inject context automatically — agent doesn't need to do anything
- **MCP tools** let the agent actively search when it needs deeper context
- **Single path** — both hooks and MCP call `set-memory` → PyO3 → shodh Rust
- **Same logic** — branch boosting, auto-tagging, dedup all apply to both paths
- **Same storage** — both access the same shodh-memory data
- **No duplication concern** — hooks surface recent/relevant, MCP for targeted deep dives
- **CLAUDE.md** explains both: "Memory is injected automatically. You can also use MCP tools for deeper searches."

### Decision 6: Cleanup old references
**Choice:** `set-project init` removes all deprecated memory instructions from SKILL.md and command .md files.

**What gets cleaned:**
- `<!-- set-memory hooks -->` blocks in all variants
- Manual `set-memory recall` / `set-memory remember` instructions in skills
- "Proactive Memory" / "Persistent Memory" sections that don't match the new template
- Old hot-topics.json files

### Decision 8: PostToolUse creates memories, not just recalls
**Choice:** PostToolUse:Edit/Write creates FileAccess memories. PostToolUse:Bash stores error patterns from stderr.

**Rationale:** shodh does both — logging file interactions builds the knowledge graph (agent learns which files it has touched and why), and storing error patterns from successful Bash calls that have stderr enables learning from warnings and partial failures that don't trigger PostToolUseFailure.

**What gets created:**
- Edit/Write → `Context` memory with file path + modification summary, tagged `file-access`
- Bash (with error output) → `Learning` memory with command + error excerpt, tagged `error,bash`

### Decision 9: Use `proactive` over `recall` for richer context
**Choice:** Use `set-memory proactive` (not `recall`) for PreToolUse and PostToolUse events where possible.

**Rationale:** shodh uses `proactive_context` (5 parallel operations: reminders, todos, facts, memories, response processing) on all events. Our `set-memory proactive` provides relevance-scored results vs plain `recall` (just semantic search). SessionStart and UserPromptSubmit already use `proactive` — extend to PreToolUse and PostToolUse for consistency.

**Trade-off:** `proactive` may be slightly slower than `recall`. Acceptable within the 5-second hook timeout.

### Decision 7: CLAUDE.md rewrite
**Choice:** New template covering both hooks and MCP.

```markdown
## Persistent Memory

Memory is automatically injected via system-reminder tags on every prompt and tool use.
You also have MCP memory tools available for active searches.

**Automatic (hooks):** Memory context appears in system-reminders labeled
"PROJECT MEMORY", "PROJECT CONTEXT", "MEMORY: Context for this file/command".
On EVERY turn, check for and use this context before independent research.

**Active (MCP tools):** Use `remember`, `recall`, `proactive_context` tools
for deeper memory interactions when automatic context isn't enough.
```

## Risks / Trade-offs

**[Risk] MCP server Python startup latency** → Each MCP tool call spawns `set-memory` subprocess (~200ms Python startup). Acceptable because MCP calls are LLM-initiated (not latency-critical like hooks). Can optimize later with direct PyO3 imports if needed.

**[Risk] Hook output format varies by event** → PreToolUse uses `hookSpecificOutput.additionalContext`, PostToolUse uses top-level `additionalContext`. The unified handler must output the correct JSON structure per event type. Verify during implementation.

**[Risk] Hooks and MCP surfacing duplicate context** → Different purposes: hooks for ambient context, MCP for targeted queries. CLAUDE.md clarifies roles.

**[Risk] Old settings.json with individual hook scripts** → Backward-compat wrappers during transition. `wt-deploy-hooks` upgrade path replaces old with new.

## Migration Plan

1. Create `bin/wt-hook-memory` unified handler
2. Convert old scripts to thin wrappers
3. Create `bin/set-memory-mcp-server.py` wrapping full set-memory CLI
4. Update `wt-deploy-hooks` template
5. Update `set-project init` (hooks + CLAUDE.md + MCP registration + cleanup)
6. Run `set-project init` on existing projects to upgrade
7. Remove old wrappers after one release cycle
