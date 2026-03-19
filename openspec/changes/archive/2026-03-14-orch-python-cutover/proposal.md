## Why

The orchestration system has a critical duplication problem: the main monitor loop, merge pipeline, and completion logic exist in both bash (`lib/orchestration/monitor.sh`, `merger.sh`) and Python (`lib/set_orch/engine.py`, `merger.py`). Only the bash versions run — the Python versions are dead code. Every bug fix must be applied twice (e.g., the "infinite replan when all changes fail" fix required commits `267cedfd4` for Python and `25a71bb72` for bash). Additionally, the Python `engine.py:_handle_auto_replan()` calls back into bash `planner.sh`, creating a circular dependency that prevents clean cutover.

## What Changes

- **Cut over `monitor_loop()`**: Make `cmd_start()` call `set-orch-core engine monitor` (Python) instead of bash `monitor_loop()`. The Python `engine.py` already has a near-complete implementation.
- **Fill Python gaps in monitor loop**: Add missing functions that bash has but Python doesn't — `send_summary_email()`, `trigger_checkpoint()`, `final_coverage_check()`, signal trap handlers, `cleanup_orchestrator()`.
- **Cut over `merge_change()`**: Route bash `merge_change()` through `set-orch-core merge execute` (Python). Fill gaps: `update_coverage_status()`, `_sync_running_worktrees()`, `fix_base_build_with_llm()`, hook dispatch.
- **Cut over `auto_replan_cycle()`**: Move full replan orchestration to Python, eliminating the circular bash↔Python dependency.
- **Cut over `cmd_plan()` orchestration**: Move planning orchestration (spec detection, Claude call, response parsing, design bridge) to Python.
- **Cut over coverage/digest operations**: Move `final_coverage_check()`, `update_coverage_status()`, `populate_coverage()` to Python.
- **Delete dead bash code**: After cutover, remove the now-unused bash implementations from `monitor.sh`, `merger.sh`, `planner.sh`, `digest.sh`.
- **Reduce bash to thin shell**: `dispatcher.sh` keeps only `cmd_start()` (signal traps + exec to Python), `cmd_pause()`, `cmd_resume()` as thin wrappers.

## Capabilities

### New Capabilities
- `orch-monitor-python`: Python monitor loop as the live orchestration engine, replacing bash monitor_loop()
- `orch-merge-python`: Python merge pipeline with full hook support, coverage tracking, and LLM build fix
- `orch-replan-python`: Python auto-replan cycle with no bash circular dependency
- `orch-plan-python`: Python planning orchestration (spec→Claude→plan enrichment)
- `orch-coverage-python`: Python coverage tracking (populate, update, final check)

### Modified Capabilities
- `execution-model`: cmd_start() now execs to Python instead of calling bash monitor_loop()

## Impact

- **Code**: `lib/orchestration/monitor.sh`, `merger.sh`, `planner.sh`, `digest.sh` become thin wrappers or are deleted. `lib/set_orch/engine.py`, `merger.py`, `planner.py`, `digest.py`, `cli.py` become the live implementations.
- **Entry points**: `set-orchestrate start` behavior unchanged externally but internally routes through Python.
- **Testing**: Must validate with a full orchestration run (e.g., minishop-run) after cutover to catch regressions.
- **Risk**: High — this touches the core orchestration loop. Phased rollout recommended (monitor first, then merge, then replan/plan).
