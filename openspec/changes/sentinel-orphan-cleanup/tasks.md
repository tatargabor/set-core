# Tasks: sentinel-orphan-cleanup

## 1. Core cleanup function — engine.py

- [x] 1.1 Add `_cleanup_orphans(state_file: str)` to `lib/set_orch/engine.py` — entry point that calls the three sub-cleaners, logs summary [REQ: log-all-actions]
- [x] 1.2 Implement `_cleanup_stale_pids(state_file)` — for each change with ralph_pid, check `os.kill(pid, 0)`, clear if dead, set step=done for merged/done, set status=stalled for running [REQ: fix-stale-ralph-pid-references]
- [x] 1.3 Implement `_cleanup_stuck_steps(state_file)` — for each merged/done change, if current_step != done → set done [REQ: fix-stuck-current-step-values]
- [x] 1.4 Implement `_cleanup_orphaned_worktrees(state_file)` — list worktrees matching `*-wt-*` pattern, compare against state.changes, remove if orphaned and clean [REQ: clean-orphaned-worktrees-on-startup]
- [x] 1.5 Add safety checks in worktree cleanup — skip if git status dirty, skip if process running in worktree dir (check /proc or lsof), skip if change is running/pending/dispatched [REQ: conservative-safety-rules]

## 2. Integration into monitor_loop

- [x] 2.1 Call `_cleanup_orphans(state_file)` at the start of `monitor_loop()` before entering the poll loop — after state file validation but before first dispatch cycle [REQ: clean-orphaned-worktrees-on-startup]

## 3. Tests

- [x] 3.1 Unit test stale PID cleanup — mock os.kill to simulate dead/alive PIDs, verify state changes [REQ: fix-stale-ralph-pid-references]
- [x] 3.2 Unit test stuck step cleanup — create state with merged+step=integrating, verify step becomes done [REQ: fix-stuck-current-step-values]
- [x] 3.3 Unit test orphan worktree detection — create temp worktrees, verify only orphaned ones are flagged [REQ: clean-orphaned-worktrees-on-startup]
- [x] 3.4 Unit test safety rules — verify dirty worktrees and active changes are never touched [REQ: conservative-safety-rules]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN worktree exists but no state entry THEN it is removed [REQ: clean-orphaned-worktrees-on-startup, scenario: worktree-exists-but-no-state-entry]
- [x] AC-2: WHEN worktree for merged change with clean git THEN removed [REQ: clean-orphaned-worktrees-on-startup, scenario: worktree-exists-for-merged-change]
- [x] AC-3: WHEN worktree has uncommitted changes THEN NOT removed, warning logged [REQ: clean-orphaned-worktrees-on-startup, scenario: worktree-has-uncommitted-changes]
- [x] AC-4: WHEN ralph_pid dead and change merged THEN pid cleared, step=done [REQ: fix-stale-ralph-pid-references, scenario: ralph-pid-points-to-dead-process]
- [x] AC-5: WHEN ralph_pid alive THEN no changes [REQ: fix-stale-ralph-pid-references, scenario: ralph-pid-points-to-live-process]
- [x] AC-6: WHEN running change with dead PID THEN status=stalled [REQ: fix-stale-ralph-pid-references, scenario: ralph-pid-for-running-change-with-dead-process]
- [x] AC-7: WHEN merged change with step=integrating THEN step=done [REQ: fix-stuck-current-step-values, scenario: merged-change-with-non-done-step]
- [x] AC-8: WHEN no orphans exist THEN no modifications, debug log [REQ: conservative-safety-rules, scenario: no-cleanup-needed]
- [x] AC-9: WHEN cleanup runs THEN summary logged: "N worktrees, M PIDs, K steps" [REQ: log-all-actions, scenario: log-all-actions]
