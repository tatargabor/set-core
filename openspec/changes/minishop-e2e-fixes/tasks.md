# Tasks: minishop-e2e-fixes

## Fix 1: Stale orchestrator lock

- [x] T1: `bin/set-sentinel` — add `rm -f "orchestrator.lock"` before `set-orchestrate start` call (line ~846), using implicit cwd (not $PROJECT_DIR which doesn't exist)
- [x] T2: `lib/set_orch/engine.py` — write `os.getpid()` to lock file after flock acquisition (after line 253), flush immediately
- [x] T3: `lib/set_orch/engine.py` — if flock fails (line 249), read PID from lock file, check `os.kill(pid, 0)`, if dead → remove stale lock and re-acquire with warning

## Fix 2: verify_retries preservation

- [x] T4: `lib/set_orch/dispatcher.py` `recover_orphaned_changes()` (line ~651) — do NOT reset `verify_retry_count` when recovering orphaned changes; this is the actual reset site, not `resume_stalled_changes()`
- [x] T5: `lib/set_orch/dispatcher.py` `resume_change()` — verify that `verify_retry_count` and `redispatch_count` are NOT reset in this path (audit, add test/assertion if needed)

## Fix 3: merge_change logging & diagnostics

- [x] T6: `lib/set_orch/merger.py` `merge_change()` — log git command, exit code, stdout, stderr on ff-merge failure (currently silent)
- [x] T7: `lib/set_orch/merger.py` `merge_change()` — enhance existing merge-base check (line ~362-383) with divergence detail logging when ff-only fails, don't duplicate the existing `--is-ancestor` check

## Fix 4: Stale worktree cleanup on resume path

- [x] T8: `bin/set-sentinel` — in the resume-restart code path (line ~495), call `clean_old_worktrees` or a scoped variant that only removes `-[0-9]+` suffixed worktrees where base change is merged/absent; the existing `clean_old_worktrees()` already handles full cleanup but is NOT called on resume
- [x] T9: `bin/set-sentinel` — ensure scoped cleanup skips worktrees whose change is still active (running/pending/verifying) in state file
