## 1. Convert `_with_state_lock` to async

- [x] 1.1 Add `import asyncio` to `lib/set_orch/api/helpers.py` [REQ: async-safe-state-file-locking]
- [x] 1.2 Convert `_with_state_lock()` from `def` to `async def`, replace `time.sleep(0.1)` with `await asyncio.sleep(0.1)` [REQ: async-safe-state-file-locking]

## 2. Update call sites in actions.py

- [x] 2.1 Make `approve_checkpoint()` async and `await _with_state_lock()` [REQ: async-safe-state-file-locking]
- [x] 2.2 Make `stop_orchestration()` async and `await _with_state_lock()` [REQ: async-safe-state-file-locking]
- [x] 2.3 Make `stop_change()` async and `await _with_state_lock()` [REQ: async-safe-state-file-locking]
- [x] 2.4 Make `skip_change()` async and `await _with_state_lock()` [REQ: async-safe-state-file-locking]
- [x] 2.5 Make `stop_all_processes()` async and `await _with_state_lock()` [REQ: async-safe-state-file-locking]

## 3. Fix missing import

- [x] 3.1 Add `from datetime import datetime, timezone` import to `actions.py` for the `approve_checkpoint` code path [REQ: async-safe-state-file-locking]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the API server attempts to acquire the state file lock and no other process holds it THEN the lock is acquired without delay and the callback executes [REQ: async-safe-state-file-locking, scenario: lock-acquired-immediately]
- [x] AC-2: WHEN another process holds the lock and releases it within 10 seconds THEN the API server acquires it after async retry delays without blocking the event loop [REQ: async-safe-state-file-locking, scenario: lock-contended-with-eventual-release]
- [x] AC-3: WHEN the lock is held for longer than 10 seconds THEN the API server returns HTTP 503 [REQ: async-safe-state-file-locking, scenario: lock-contention-exceeds-deadline]
- [x] AC-4: WHEN the API server retries lock acquisition via asyncio.sleep() THEN other HTTP requests continue to be serviced [REQ: async-safe-state-file-locking, scenario: event-loop-remains-responsive-during-lock-retry]
