## 1. Design Bridge Core Module

- [x] 1.1 Create `lib/design/bridge.sh` with `detect_design_mcp()` — scan `.claude/settings.json` mcpServers for known design tool names (figma, penpot, sketch, zeplin), return first match or exit 1
- [x] 1.2 Add `get_design_mcp_config()` to bridge.sh — extract MCP server config from settings.json into temp JSON file, print path to stdout
- [x] 1.3 Add `design_prompt_section()` to bridge.sh — generate LLM prompt section with design tool capabilities, file reference from `DESIGN_FILE_REF`, and ambiguity flagging instructions
- [x] 1.4 Add `load_design_file_ref()` to bridge.sh — read `design_file` from `.claude/orchestration.yaml` via yq/jq, export as `DESIGN_FILE_REF`
- [x] 1.5 Add unit tests for detection (with/without figma entry, missing settings file, multiple design MCPs) — 12 tests, all pass

## 2. run_claude MCP Passthrough

- [x] 2.1 Extend `run_claude()` in `bin/wt-common.sh` — when `DESIGN_MCP_CONFIG` env var is set and non-empty, append `--mcp-config "$DESIGN_MCP_CONFIG"` to the claude CLI command
- [x] 2.2 Test that `run_claude` with `DESIGN_MCP_CONFIG=""` behaves identically to current (no regression)

## 3. Planner Integration

- [ ] 3.1 Source `lib/design/bridge.sh` in planner.sh (after config.sh/utils.sh)
- [ ] 3.2 In planner's context-gathering phase: call `detect_design_mcp`, if found → `get_design_mcp_config` + `load_design_file_ref` + export `DESIGN_MCP_CONFIG`
- [ ] 3.3 Append `design_prompt_section` output to the planning prompt (after existing context sections)
- [ ] 3.4 Verify planner runs clean when no design MCP is registered (non-fatal path)

## 4. Dispatcher Integration

- [ ] 4.1 In dispatcher.sh `dispatch_change()`: read `design_ref` from plan change entry, if non-empty append `## Design Reference` section to proposal.md
- [ ] 4.2 In dispatcher.sh: if design MCP detected, export `DESIGN_MCP_CONFIG` to the wt-loop environment (so agent has access)
- [ ] 4.3 Verify dispatch works identically when no design MCP is present (non-fatal path)

## 5. Decompose Skill Update

- [ ] 5.1 Update `.claude/skills/wt/decompose/SKILL.md` — add design MCP awareness section: detect if design MCP tools are available, query for frame/page inventory, map frames to changes
- [ ] 5.2 Add `design_ref` field to decompose output schema (optional string, frame/page reference per-change)
- [ ] 5.3 Add design gap ambiguity instruction: if spec requires a page but no design frame exists, add `design_gap` ambiguity to output

## 6. Agent Rule Template

- [ ] 6.1 Create `templates/rules/design-bridge-rule.md` — instruct agents to query design MCP for UI specs (colors, spacing, typography, layout, component structure) before implementing UI elements
- [ ] 6.2 Update `lib/project/deploy.sh` — conditionally deploy design-bridge rule only when design MCP is detected in project settings
- [ ] 6.3 Verify `wt-project init` skips design rule when no design MCP is registered

## 7. Integration Verification

- [ ] 7.1 End-to-end test: register a mock design MCP, run planner with a UI-heavy spec, verify design prompt section appears in prompt and `--mcp-config` is passed
- [ ] 7.2 Regression test: run planner without design MCP, verify output is identical to baseline
