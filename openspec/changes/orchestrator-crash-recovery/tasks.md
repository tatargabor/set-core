## 1. Recovery function

- [x] 1.1 Add `recover_orphaned_changes()` function to dispatcher.sh — iterate all changes with status running/verifying/stalled, check worktree existence + PID liveness, reset to pending if both are gone
- [x] 1.2 Reset recovered changes: status=pending, worktree_path=null, ralph_pid=null, verify_retry_count=0, failure_reason=null
- [x] 1.3 Emit CHANGE_RECOVERED event for each recovered change

## 2. Integration into cmd_start

- [x] 2.1 Call `recover_orphaned_changes()` in cmd_start() resume path — BEFORE resume_stopped_changes() and dispatch_ready_changes()
- [x] 2.2 Handle the "already running" check: if status="running" but no orchestrator PID alive, treat as crashed state and enter resume path instead of exiting

## 3. Tests

- [x] 3.1 Test: orphaned change (status=running, no worktree, dead PID) gets recovered to pending
- [x] 3.2 Test: change with live PID is NOT recovered (skip with warning)
- [x] 3.3 Test: change with existing worktree is NOT recovered
- [x] 3.4 Test: multiple orphaned changes all recovered in single pass
