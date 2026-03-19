## Why

Continuing the Python migration (phase 5 of 8). `dispatcher.sh` is 1438 lines of bash handling worktree lifecycle, change dispatch, resume/pause, model routing, recovery, and the orchestrator's `cmd_start`/`cmd_pause`/`cmd_resume` command handlers. Migrating to Python enables type safety, structured error handling, and testability — consistent with phases 1-4 (infra, state, reporter, planner).

## What Changes

- New `lib/set_orch/dispatcher.py` module (~800-1000 lines Python) replacing all functions in `lib/orchestration/dispatcher.sh`
- New CLI subcommands in `set-orch-core dispatch *` for bash-to-Python bridge
- `dispatcher.sh` reduced to thin bash wrapper (~50 LOC) calling `set-orch-core dispatch *`
- 1:1 function mapping with source comments tracing back to `dispatcher.sh` line numbers

### Function inventory (17 functions → Python):
- **Worktree prep**: `sync_worktree_with_main`, `bootstrap_worktree`, `prune_worktree_context`
- **Model routing**: `resolve_change_model`
- **Core dispatch**: `dispatch_change`, `dispatch_via_wt_loop`, `dispatch_ready_changes`
- **Lifecycle**: `pause_change`, `resume_change`, `resume_stopped_changes`, `resume_stalled_changes`
- **Recovery**: `recover_orphaned_changes`, `redispatch_change`, `retry_failed_builds`
- **Commands**: `cmd_start`, `cmd_pause`, `cmd_resume`

## Capabilities

### New Capabilities
- `dispatch-worktree`: Worktree preparation — git sync, env bootstrap, context pruning
- `dispatch-core`: Change dispatch engine — model routing, scheduling, wt-loop launch
- `dispatch-lifecycle`: Pause/resume/stall recovery for running changes
- `dispatch-recovery`: Orphan recovery, redispatch, build retry logic

### Modified Capabilities
<!-- No spec-level behavior changes — this is a pure implementation migration -->

## Impact

- **Code**: `lib/orchestration/dispatcher.sh` → `lib/set_orch/dispatcher.py` + CLI extensions in `lib/set_orch/cli.py`
- **Dependencies**: Uses existing `set_orch.state`, `set_orch.events`, `set_orch.process`, `set_orch.config`, `set_orch.templates`
- **External**: `subprocess` calls to `git`, `wt-new`, `wt-loop` (these remain as shell commands)
- **Testing**: `pytest` tests for each capability group
