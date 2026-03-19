## Tasks

### `run_with_lock()` stale lock recovery

- [x] Add `is_lock_stale()` helper function that checks:
  - If `<lock_dir>/pid` exists and PID is dead (`! kill -0 $pid 2>/dev/null`) → stale
  - If no pid file but lock dir age > 60s (`find` or `stat` based) → stale
  - Otherwise → not stale
- [x] Add `remove_stale_lock()` helper that removes lock dir + pid file with stderr warning
- [x] Modify `run_with_lock()`: before entering wait loop, call `is_lock_stale()` and auto-remove if stale
- [x] Modify `run_with_lock()`: on timeout (10s), call `is_lock_stale()` once more and retry if stale was found
- [x] Write PID file (`echo $$ > "$lock_dir/pid"`) immediately after successful `mkdir`
- [x] Update cleanup: `rm -f "$lock_dir/pid"; rmdir "$lock_dir"` in both explicit cleanup and EXIT trap

### Testing

- [x] Manual test: create orphaned lock dir (no pid file, age > 60s), verify `set-memory status` succeeds
- [x] Manual test: create orphaned lock dir with dead PID file, verify auto-recovery
- [x] Manual test: create lock dir with own PID (simulating active lock), verify timeout still works
