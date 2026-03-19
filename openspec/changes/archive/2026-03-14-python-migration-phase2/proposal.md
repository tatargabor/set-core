## Why

Phase 1 established the Python infrastructure (`logging_config.py`, `subprocess_utils.py`, `config.py`, `events.py`) and the typed state schema (`state.py` with dataclasses). However, `lib/orchestration/state.sh` (997 lines) still contains all the runtime state mutation logic: field updates with locking, dependency graph operations, phase management, crash recovery, notifications, and status commands — all implemented as bash+jq pipelines. These functions are the most fragile part of the orchestrator (jq filter injection, quoting issues, `set -e` traps). Phase 2 migrates them to Python, completing the state engine.

## What Changes

- Migrate state mutation functions from `state.sh` to `state.py`: `update_state_field`, `update_change_field` (with event emission), `get_change_status`, `get_changes_by_status`, `count_changes_by_status`
- Migrate dependency operations: `deps_satisfied`, `deps_failed`, `cascade_failed_deps`, `topological_sort`
- Migrate phase management: `_init_phase_state`, `apply_phase_overrides`, `all_phase_changes_terminal`, `advance_phase`
- Migrate crash recovery: `reconstruct_state_from_events`
- Migrate notification system: `send_notification` (desktop + email channels)
- Migrate hook runner: `run_hook` (lifecycle hook execution with blocking semantics)
- Add file-level locking to `save_state` using `fcntl.flock` (replacing bash `with_state_lock`)
- Add `set-orch-core state` CLI subcommands for each migrated function so bash callers can use them during transition
- Migrate `cmd_status` display logic to Python (formatted table output)

## Capabilities

### New Capabilities
- `state-mutations`: Locked state field updates with event emission on status transitions
- `state-dependencies`: Dependency graph operations — satisfaction check, failure cascade, topological sort
- `state-phases`: Phase lifecycle — init, advance, override, terminal check
- `state-recovery`: Crash recovery by replaying events JSONL to reconstruct consistent state
- `state-notifications`: Desktop (notify-send) and email (Resend API) notification dispatch

### Modified Capabilities
- `typed-state`: Extended with mutation methods, file locking, dependency graph, and phase management

## Impact

- `lib/set_orch/state.py` — major extension (~400 LOC added)
- `lib/orchestration/state.sh` — functions replaced by `set-orch-core state <subcommand>` calls (bash wrappers shrink to ~50 LOC each)
- `lib/set_orch/cli.py` — new `state` subcommands registered
- `lib/set_orch/events.py` — consumed by mutation functions for event emission
- `tests/unit/test_state.py` — extended with mutation, locking, dependency, phase, recovery tests
