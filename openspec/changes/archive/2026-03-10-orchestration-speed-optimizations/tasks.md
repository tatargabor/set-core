## 1. Watchdog PID Guard

- [x] 1.1 In `watchdog.sh`, add PID-alive check before hash loop escalation (line 116) — if Ralph PID is alive, log warning + emit WATCHDOG_WARN event but skip escalation
- [x] 1.2 Add test: verify watchdog does not escalate when consecutive_same >= threshold AND PID is alive

## 2. Complexity-Aware Dispatch Ordering

- [x] 2.1 In `dispatch_ready_changes()`, after filtering pending+deps_satisfied changes, sort by complexity (L > M > S) before dispatching
- [x] 2.2 Read complexity from state JSON for each pending change; default to "M" if missing
- [x] 2.3 Add test: verify L-complexity change dispatches before M when both are ready

## 3. Post-Merge Worktree Sync

- [x] 3.1 In `merger.sh`, after successful `merge_change()`, iterate all running changes and call `sync_worktree_with_main` for each
- [x] 3.2 Log sync results (synced/already-up-to-date/failed) per worktree
- [x] 3.3 Ensure sync failures are non-blocking (|| true)

## 4. Default max_parallel

- [x] 4.1 Change `DEFAULT_MAX_PARALLEL=2` to `DEFAULT_MAX_PARALLEL=3` in `bin/set-orchestrate`
