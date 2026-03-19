## Why

The bash→Python orchestrator migration left the design snapshot pipeline broken at 4 levels. The Python planner's `_fetch_design_context()` only reads an existing `design-snapshot.md` but never fetches one from the Figma MCP — the fetch logic lived in the bash planner and was not ported. Additionally, `dispatch_ready_changes()` doesn't propagate `design_snapshot_dir` to `dispatch_change()`, and the verifier's design compliance section is a placeholder (`pass`). The result: projects with a registered Figma MCP and `design_file` configured get zero design context — agents use framework defaults instead of Figma design tokens.

## What Changes

- Port `setup_design_bridge()`, `check_design_mcp_health()`, and `fetch_design_snapshot()` logic to Python in the planner preflight
- Make `_fetch_design_context()` actually invoke `fetch-figma-design.py` when a design MCP is detected and `design_file` is configured
- If a design MCP is registered and `design_file` is set but the snapshot fetch fails, raise an error to block decomposition (fail-fast, don't silently proceed without design)
- Propagate `design_snapshot_dir` through `dispatch_ready_changes()` → `dispatch_change()`
- Wire up `build_design_review_section()` in the verifier (replace `pass` placeholder)
- Add unit tests for the new Python design bridge functions

## Capabilities

### New Capabilities
- `python-design-bridge`: Python-native design MCP detection, health check, snapshot fetch, and fail-fast gate in the planner preflight

### Modified Capabilities
- `design-snapshot`: Snapshot fetch now happens in Python planner, not bash planner; adds fail-fast behavior when design is configured but fetch fails
- `mcp-preflight-check`: Health check and snapshot fetch called from Python `run_decomposition()` instead of bash `planner.sh`
- `design-dispatch-injection`: `design_snapshot_dir` propagated through the full dispatch chain
- `design-verify-gate`: Verifier actually calls `build_design_review_section()` instead of `pass` placeholder

## Impact

- **lib/set_orch/planner.py** — `_fetch_design_context()` rewritten to detect MCP, health-check, fetch snapshot, and fail if configured but unfetchable
- **lib/set_orch/dispatcher.py** — `dispatch_ready_changes()` passes `design_snapshot_dir` to `dispatch_change()`
- **lib/set_orch/verifier.py** — design compliance section wired up via bash bridge call
- **lib/set_orch/engine.py** — passes `design_snapshot_dir` to dispatch calls
- **tests/unit/** — new test file for Python design bridge functions
