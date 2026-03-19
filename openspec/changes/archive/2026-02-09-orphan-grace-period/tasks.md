## 1. Grace Period Tracking in wt-status

- [x] 1.1 Add helper function `orphan_marker_dir()` that returns `$wt_path/.set-core/orphan-detect` and ensures the directory exists
- [x] 1.2 Add helper function `cleanup_stale_markers()` that removes marker files for PIDs that no longer exist (`kill -0`)
- [x] 1.3 Add helper function `record_orphan_detection()` that creates/updates marker file with `<timestamp>:<count>` — creates new with count=1 or increments existing count
- [x] 1.4 Add helper function `should_kill_orphan()` that reads marker file and returns 0 (true) only if count >= 3 AND (now - first_seen) >= 15
- [x] 1.5 Add helper function `reset_orphan_marker()` that deletes the marker file for a given PID

## 2. Integrate Grace Period into cleanup_orphan_agents()

- [x] 2.1 At the start of `cleanup_orphan_agents()`, call `cleanup_stale_markers()` to remove dead PID markers
- [x] 2.2 When editor is open or ralph loop is active (early return path), reset all markers for agents in that worktree
- [x] 2.3 Replace the immediate `kill` in the "waiting" orphan branch with grace period logic: call `record_orphan_detection()`, then only kill if `should_kill_orphan()` returns true
- [x] 2.4 When a waiting agent passes the TTY+shell safety check, call `reset_orphan_marker()` for that PID
- [x] 2.5 When an agent is running/compacting (kept in else branch), call `reset_orphan_marker()` for that PID

## 3. Testing

- [x] 3.1 Manual test: start a Claude agent in Zed worktree, open a new terminal tab — verify agent survives
- [x] 3.2 Manual test: close terminal with a waiting agent, verify it gets killed after ~15s (not immediately)
- [x] 3.3 Manual test: close terminal with a waiting agent, reopen editor within 15s — verify agent survives and marker resets
