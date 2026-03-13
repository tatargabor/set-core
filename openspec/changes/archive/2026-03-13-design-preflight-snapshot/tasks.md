## 1. Snapshot Extraction Function

- [x] 1.1 Add `fetch_design_snapshot()` to `lib/design/bridge.sh` — accepts optional `force` flag, requires `DESIGN_MCP_CONFIG` and `DESIGN_FILE_REF`, runs `run_claude` with MCP config and snapshot extraction prompt, writes output to `$STATE_DIR/design-snapshot.md`
- [x] 1.2 Implement cache logic — skip fetch if `$STATE_DIR/design-snapshot.md` exists and `force` is not set; log "Using cached design snapshot"
- [x] 1.3 Define the snapshot extraction prompt — instruct LLM to call `get_metadata`, `get_variable_defs`, `get_design_context` (and optionally `get_screenshot`) on the design file URL, compile into structured markdown with Pages & Frames table, Design Tokens, Component Hierarchy, Layout Breakpoints, Visual Descriptions sections
- [x] 1.4 Set `RUN_CLAUDE_TIMEOUT=120` for the snapshot call; on timeout or failure return 1 with warning log, no snapshot file created

## 2. Prompt Section Snapshot-Aware Mode

- [x] 2.1 Modify `design_prompt_section()` in `lib/design/bridge.sh` to accept an optional `$STATE_DIR` parameter
- [x] 2.2 When `$STATE_DIR/design-snapshot.md` exists and is non-empty, return its content with a "Design Context (Snapshot)" header and a note that live MCP is also available
- [x] 2.3 When no snapshot exists, return existing generic prompt (current behavior preserved)

## 3. Planner Integration

- [x] 3.1 In `lib/orchestration/planner.sh` `run_decomposition()`, after `check_design_mcp_health()` passes, call `fetch_design_snapshot()` before building `design_context`
- [x] 3.2 Pass `force=true` to `fetch_design_snapshot()` when in a replan cycle (detect via `_REPLAN_CYCLE` variable)
- [x] 3.3 Update `design_prompt_section()` call to pass `$STATE_DIR` so it can check for cached snapshot
- [x] 3.4 After mcp_auth checkpoint approval + retry health check success, also call `fetch_design_snapshot()`

## 4. Tests

- [x] 4.1 Add unit tests to `tests/unit/test_design_bridge.sh` for `fetch_design_snapshot()` — mock `run_claude` to return sample snapshot markdown, verify file written to expected path
- [x] 4.2 Test cache logic — verify second call skips fetch, verify `force=true` re-fetches
- [x] 4.3 Test timeout handling — mock `run_claude` with non-zero exit, verify function returns 1 and no snapshot file created
- [x] 4.4 Test `design_prompt_section()` snapshot-aware mode — verify snapshot content returned when cache file exists, generic prompt when not
