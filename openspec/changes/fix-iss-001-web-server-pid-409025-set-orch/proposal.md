## Why

The `set-orchestrate serve` web server uses `_with_state_lock()` in `helpers.py` which calls `time.sleep(0.1)` in a blocking retry loop. When this runs inside the Uvicorn event loop thread, it blocks `epoll_wait` from dispatching any events, leaving the lock file descriptor open indefinitely. The orchestrator process is then blocked 10+ minutes waiting for the web server to release the lock.

## What Changes

- Replace the synchronous `_with_state_lock()` retry loop (which uses `time.sleep()`) with an async version using `asyncio.sleep()` so the event loop is never blocked
- Update all call sites in `actions.py` to `await` the new async lock function
- Add missing `datetime` import in `actions.py` (causes `NameError` in the `approve_checkpoint` code path)

## Capabilities

### New Capabilities
<!-- none — pure bug fix -->

### Modified Capabilities
<!-- Internal implementation detail; no spec-level requirement changes needed -->

## Impact

- **Affected code**: `lib/set_orch/api/helpers.py`, `lib/set_orch/api/actions.py`
- **No API surface change** — all endpoints keep identical signatures and behavior
- **Risk**: Low — only internal locking mechanism changes; 503 "State file locked" error path preserved
- **Unblocks**: All projects using `set-orchestrate serve` alongside an orchestrator process
