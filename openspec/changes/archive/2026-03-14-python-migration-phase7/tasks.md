## 1. Merger Module

- [x] 1.1 Create `lib/set_orch/merger.py` with `MergeResult` dataclass and module constants (MAX_MERGE_RETRIES=5, MILESTONE_WORKTREE_DIR)
- [x] 1.2 Implement `archive_change(change_name)` — move openspec dir to dated archive, git add+commit
- [x] 1.3 Implement `_collect_smoke_screenshots(change_name, state_file)` — copy test-results to attempt-N subdirs
- [x] 1.4 Implement `_archive_worktree_logs(change_name, wt_path)` — copy .claude/logs to orchestration archive
- [x] 1.5 Implement `cleanup_worktree(change_name, wt_path)` — archive logs, wt-close with fallback manual removal
- [x] 1.6 Implement `cleanup_all_worktrees(state_file)` — iterate merged/done changes, call cleanup_worktree
- [x] 1.7 Implement `_sync_running_worktrees(merged_change, state_file)` — sync all running worktrees after merge
- [x] 1.8 Implement `merge_change(change_name, state_file)` — full merge pipeline: pre-merge hook, branch check, wt-merge, post-merge deps/build/scope/smoke, agent rebase on conflict
- [x] 1.9 Implement `execute_merge_queue(state_file)` — drain merge queue
- [x] 1.10 Implement `_try_merge(name, state_file)` — single attempt with conflict fingerprint dedup
- [x] 1.11 Implement `retry_merge_queue(state_file)` — retry queue items + merge-blocked changes

## 2. Milestone Module

- [x] 2.1 Create `lib/set_orch/milestone.py` with constants and imports
- [x] 2.2 Implement `_enforce_max_milestone_worktrees(max_wts, state_file)` — kill servers, remove oldest worktrees
- [x] 2.3 Implement `_send_milestone_email(phase, port, pid, state_file)` — HTML email with phase stats
- [x] 2.4 Implement `run_milestone_checkpoint(phase, base_port, max_worktrees, state_file)` — full pipeline: tag, worktree, deps, server, email, event
- [x] 2.5 Implement `cleanup_milestone_servers(state_file)` — kill all milestone PIDs
- [x] 2.6 Implement `cleanup_milestone_worktrees()` — remove all milestone worktree dirs

## 3. Engine Module

- [x] 3.1 Create `lib/set_orch/engine.py` with `Directives` dataclass for ~40 directive fields with defaults
- [x] 3.2 Implement `_parse_directives(directives_json)` — JSON to Directives dataclass
- [x] 3.3 Implement `monitor_loop(directives_json, state_file)` — main while-loop: poll interval, active time tracking, time limit, status checks
- [x] 3.4 Implement poll active changes section — iterate running+verifying changes, call poll_change+watchdog_check
- [x] 3.5 Implement poll suspended changes section — check paused/waiting/done for completed loop-state, orphaned done recovery
- [x] 3.6 Implement token budget section — soft budget (pause dispatch), hard limit (trigger checkpoint)
- [x] 3.7 Implement verify-failed recovery — resume with retry_context, rebuild from stored build_output
- [x] 3.8 Implement completion detection — all-terminal check, phase-end E2E, post-phase audit, auto-replan with cycle limits
- [x] 3.9 Implement self-watchdog — idle stall detection with escalation (recovery → notification)
- [x] 3.10 Implement phase milestone integration — check phase completion, run checkpoint, advance phase

## 4. CLI Bridge

- [x] 4.1 Add `merge` subcommand group to `lib/set_orch/cli.py` with argparse for all merge subcommands
- [x] 4.2 Add `milestone` subcommand group to `lib/set_orch/cli.py` with argparse for all milestone subcommands
- [x] 4.3 Add `engine` subcommand group to `lib/set_orch/cli.py` with argparse for monitor subcommand

## 5. Bash Wrappers

- [x] 5.1 Replace `lib/orchestration/merger.sh` with thin wrappers delegating to `set-orch-core merge *`
- [x] 5.2 Replace `lib/orchestration/milestone.sh` with thin wrappers delegating to `set-orch-core milestone *`
- [x] 5.3 Replace `lib/orchestration/monitor.sh` with thin wrapper delegating to `set-orch-core engine monitor`

## 6. Tests

- [x] 6.1 Create `tests/unit/test_merger.py` — test archive_change, cleanup_worktree, _collect_smoke_screenshots, _try_merge retry logic, conflict fingerprint dedup
- [x] 6.2 Create `tests/unit/test_milestone.py` — test _enforce_max_milestone_worktrees, _send_milestone_email, cleanup functions
- [x] 6.3 Create `tests/unit/test_engine.py` — test _parse_directives with defaults, token budget logic, time limit calculation, completion detection
- [x] 6.4 Run full test suite to verify no regressions (existing dispatcher + verifier tests still pass)
