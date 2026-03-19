## 1. File Locking Infrastructure

- [x] 1.1 Add `locked_state(path)` context manager to `state.py` using `fcntl.flock` on `<path>.lock` — loads state, yields for modification, saves atomically on exit
- [x] 1.2 Update `save_state()` to acquire flock before write and release after rename
- [x] 1.3 Add tests for concurrent locking (two threads writing simultaneously, both succeed without corruption)

## 2. State Mutation Functions

- [x] 2.1 Add `update_state_field(path, field, value, event_bus=None)` — read-modify-write under lock
- [x] 2.2 Add `update_change_field(path, change_name, field, value, event_bus=None)` — with STATE_CHANGE event emission on status transitions, TOKENS event on large deltas, on_fail hook trigger
- [x] 2.3 Add `get_change_status(state, name)` returning status string
- [x] 2.4 Add `get_changes_by_status(state, status)` returning list of change names
- [x] 2.5 Add `count_changes_by_status(state, status)` returning int count
- [x] 2.6 Add tests for all mutation functions including event emission verification

## 3. Dependency Graph Operations

- [x] 3.1 Add `deps_satisfied(state, change_name)` — True if all depends_on are merged/skipped
- [x] 3.2 Add `deps_failed(state, change_name)` — True if any depends_on is failed (merge-blocked is NOT failure)
- [x] 3.3 Add `cascade_failed_deps(state, event_bus=None)` — mark pending changes failed if deps failed, return count
- [x] 3.4 Add `topological_sort(changes)` — return names in dependency order, raise on circular deps
- [x] 3.5 Add tests for dependency operations: no deps, satisfied, unsatisfied, failed, cascade, circular detection

## 4. Phase Management

- [x] 4.1 Add `init_phase_state(state)` — compute unique phases, create phases dict, set current_phase
- [x] 4.2 Add `apply_phase_overrides(state, overrides)` — update change phase fields and recalculate phases
- [x] 4.3 Add `all_phase_changes_terminal(state, phase)` — check if all changes in phase are terminal
- [x] 4.4 Add `advance_phase(state, event_bus=None)` — mark current completed, advance to next, emit PHASE_ADVANCED
- [x] 4.5 Add tests for phase lifecycle: init, override, terminal check, advance, no-more-phases

## 5. Crash Recovery

- [x] 5.1 Add `reconstruct_state_from_events(state_path, events_path, event_bus=None)` — replay STATE_CHANGE and TOKENS events, set running→stalled, derive orchestrator status
- [x] 5.2 Add tests: replay status transitions, replay tokens, running→stalled, all-done→done, missing events file

## 6. Notifications & Hooks

- [x] 6.1 Create `lib/set_orch/notifications.py` with `send_notification(title, body, urgency, channels)` — desktop via notify-send subprocess, email via Resend API
- [x] 6.2 Add `run_hook(hook_name, hook_script, change_name, status, wt_path, event_bus=None)` to state.py — execute script, capture stderr, return bool, emit HOOK_BLOCKED on failure
- [x] 6.3 Add tests for notifications (mock subprocess/requests) and hook runner (mock script execution)

## 7. CLI Bridge Subcommands

- [x] 7.1 Add `set-orch-core state update-field` subcommand
- [x] 7.2 Add `set-orch-core state update-change` subcommand
- [x] 7.3 Add `set-orch-core state get-status` and `count-by-status` subcommands
- [x] 7.4 Add `set-orch-core state deps-satisfied` and `cascade-failed` subcommands
- [x] 7.5 Add `set-orch-core state topo-sort` subcommand
- [x] 7.6 Add `set-orch-core state advance-phase` and `reconstruct` subcommands
- [x] 7.7 Add CLI integration tests verifying subcommand exit codes and output format

## 8. Bash Wrapper Migration

- [x] 8.1 Replace `state.sh` mutation functions with `set-orch-core state` calls (update_state_field, update_change_field, get_change_status, get_changes_by_status, count_changes_by_status)
- [x] 8.2 Replace `state.sh` dependency functions with CLI calls (deps_satisfied, deps_failed, cascade_failed_deps, topological_sort)
- [x] 8.3 Replace `state.sh` phase functions with CLI calls (apply_phase_overrides, _init_phase_state, all_phase_changes_terminal, advance_phase)
- [x] 8.4 Replace `state.sh` reconstruct_state_from_events with CLI call
- [x] 8.5 Verify orchestrator end-to-end with replaced functions (run existing test suite)
