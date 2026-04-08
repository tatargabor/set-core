## Context

The web server (`set-orchestrate serve`) runs on Uvicorn (async, single event loop thread). Several API action endpoints use `_with_state_lock()` to safely modify `orchestration-state.json`. The current implementation uses `time.sleep(0.1)` in a blocking retry loop, which freezes the event loop thread — preventing it from processing any I/O (including releasing the lock's file descriptor via `epoll_wait`). This causes deadlocks when the orchestrator and web server contend for the same lock.

## Goals / Non-Goals

**Goals:**
- Make `_with_state_lock()` async-safe so the event loop is never blocked
- Preserve the existing 10-second timeout and 503 error semantics
- Fix the missing `datetime` import in `actions.py`

**Non-Goals:**
- Changing the locking mechanism itself (flock is fine for the use case)
- Changing API endpoint signatures or response formats
- Async-ifying the entire helpers module

## Decisions

**Decision: Convert `_with_state_lock` to `async def` with `asyncio.sleep()`**

Rationale: The simplest fix — replace `time.sleep(0.1)` with `await asyncio.sleep(0.1)` and make the function `async def`. All call sites are in FastAPI route handlers which are already async-compatible (FastAPI runs sync handlers in a thread pool, but making them explicitly `async def` with `await` is the correct pattern when doing async I/O).

Alternative considered: Offloading to `asyncio.to_thread()` — more complex, adds thread-pool dependency, same end result. Rejected.

**Decision: Keep `fcntl.flock` (non-blocking attempt + async retry)**

The initial `LOCK_NB` attempt is fine — it's the retry loop's `time.sleep()` that's the problem. The flock call itself is instant (non-blocking flag), only the sleep between retries needs to yield.

## Risks / Trade-offs

- [Risk] Route handlers calling `_with_state_lock` must be `async def` → Mitigation: all affected handlers are already simple enough; just add `async` keyword and `await`.
- [Risk] Sync callers of `_with_state_lock` would break → Mitigation: grep confirms no sync callers outside `actions.py`.

## Open Questions

None — straightforward fix with clear scope.
