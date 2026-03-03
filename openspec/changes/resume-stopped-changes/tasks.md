## 1. Resume stopped changes on orchestrator restart

- [x] 1.1 Add `resume_stopped_changes()` function in `bin/wt-orchestrate` — iterates changes with status "stopped", checks worktree exists, calls `resume_change()` or sets "pending"
- [x] 1.2 Call `resume_stopped_changes()` in the resume path of `cmd_start()` — after `retry_merge_queue` (line ~2137), before `dispatch_ready_changes`
- [x] 1.3 Also call `resume_stopped_changes()` in the fresh start path — after the cleanup trap setup, before `dispatch_ready_changes` (line ~2235)
- [x] 1.4 Add logging: "Resuming stopped change: {name}" for each resumed, "Resetting stopped change {name} to pending (worktree missing)" for missing worktree
