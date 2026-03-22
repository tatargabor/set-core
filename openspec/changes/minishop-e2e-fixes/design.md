# Design: minishop-e2e-fixes

## Fix 1: Stale orchestrator.lock

**Current**: `engine.py:245` opens lock file, `fcntl.flock(LOCK_EX | LOCK_NB)`. If lock held → error exit.

**Fix**: Sentinel cleans `orchestrator.lock` before starting orchestrator. The sentinel is the single supervisor — if it's starting a new orchestrator, any existing lock is stale by definition.

```
bin/set-sentinel — before starting orchestrator:
  rm -f "$PROJECT_DIR/orchestrator.lock"
```

Also add PID validation: if lock file exists, check if the PID in it is alive before refusing.

## Fix 2: verify_retries counter preservation

**Current**: `resume_change()` (dispatcher.py:1970) doesn't snapshot or preserve `verify_retry_count`. The stall recovery path calls `resume_change()` which starts a fresh set-loop, losing the retry context.

**Fix**: In `resume_stalled_changes()`, before calling `resume_change()`, preserve `verify_retry_count` from the stalled change's state. Don't reset it.

## Fix 3: merge_change() investigation

**Current**: `merge_change()` (merger.py) does pre_merge hook → git merge --ff-only → post_merge hook. The ff-only merge fails silently in some cases.

**Fix**: Add detailed logging to `merge_change()` — log the exact git command, exit code, stdout, stderr. Also check if the branch was already integrated (merge-base check) before attempting ff-only.

## Fix 4: Stale worktree cleanup

**Current**: Failed dispatch creates worktrees with `-2`, `-3` suffixes. These persist across restarts.

**Fix**: In sentinel startup (after history protection check), scan for worktrees with numeric suffixes (`-wt-*-[0-9]+`) where the corresponding change is not in the state or is already merged. Remove them.

## Files Modified

| File | Change |
|------|--------|
| `bin/set-sentinel` | Lock cleanup before orchestrator start, stale worktree scan |
| `lib/set_orch/engine.py` | Lock PID validation |
| `lib/set_orch/dispatcher.py` | Preserve verify_retry_count in resume path |
| `lib/set_orch/merger.py` | Detailed merge logging, merge-base pre-check |
