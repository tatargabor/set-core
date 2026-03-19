## 1. Extend recover_orphaned_changes() with PID liveness check

- [x] 1.1 In `lib/set_orch/dispatcher.py` `recover_orphaned_changes()`: after the existing worktree-exists skip (line 342), add PID liveness check — if worktree exists but PID is dead/missing, set status to "stopped" and clear ralph_pid. Emit CHANGE_RECONCILED event with reason "dead_pid_live_worktree" or "no_pid_live_worktree"
- [x] 1.2 Add logging: log each reconciled change name and previous status, plus summary count

## 2. Clear stale audit/E2E results on resume

- [x] 2.1 In `lib/orchestration/dispatcher.sh` cmd_start() resume path (after line 370 `update_state_field "status" '"running"'`): clear `phase_audit_results` to `[]` and `phase_e2e_results` to `[]` with `update_state_field`. Add log entry noting stale results cleared
- [x] 2.2 Verify the replan path in `lib/orchestration/planner.sh` (lines 907-928) still preserves audit/e2e results correctly — no changes needed, just confirm no regression

## 3. Tests

- [x] 3.1 Add unit test for `recover_orphaned_changes()`: change with existing worktree dir but dead PID gets status set to "stopped" and CHANGE_RECONCILED event emitted
- [x] 3.2 Add unit test for `recover_orphaned_changes()`: change with existing worktree dir and live PID is left unchanged
- [x] 3.3 Add unit test for `recover_orphaned_changes()`: change with existing worktree dir and no PID (null/0) gets status set to "stopped"
- [x] 3.4 Verify existing orphan recovery tests still pass (no worktree, dead PID → "pending")
