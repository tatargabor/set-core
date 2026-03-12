## 1. Fix dependency deadlock (#16)

- [x] 1.1 Move `cascade_failed_deps()` call before `dispatch_ready_changes()` in monitor.sh monitor loop
- [x] 1.2 Add test: change with failed dependency gets cascaded to failed before dispatch attempt

## 2. Fix active_seconds timer (#17)

- [x] 2.1 Add "verifying" status to `any_loop_active()` check in utils.sh (alongside "running")
- [x] 2.2 Add test: `any_loop_active()` returns true when a change has status "verifying"

## 3. Fix digest replan failure (#21)

- [x] 3.1 Add redundant hash recomputation in planner.sh auto-re-digest trigger — skip re-digest if source hash matches stored hash
- [x] 3.2 Add test: replan with unchanged spec skips re-digest
