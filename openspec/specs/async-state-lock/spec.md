# Async State Lock Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Async-safe state file locking

The API server's state file lock acquisition MUST NOT block the async event loop. The `_with_state_lock()` helper SHALL use `asyncio.sleep()` for retry delays instead of `time.sleep()`, and all call sites SHALL `await` the async lock function.

#### Scenario: Lock acquired immediately
- **WHEN** the API server attempts to acquire the state file lock and no other process holds it
- **THEN** the lock is acquired without delay and the callback executes

#### Scenario: Lock contended with eventual release
- **WHEN** another process holds the state file lock and releases it within the 10-second deadline
- **THEN** the API server acquires the lock after async retry delays without blocking the event loop

#### Scenario: Lock contention exceeds deadline
- **WHEN** the state file lock is held by another process for longer than 10 seconds
- **THEN** the API server returns HTTP 503 "State file locked, try again"

#### Scenario: Event loop remains responsive during lock retry
- **WHEN** the API server retries lock acquisition via `asyncio.sleep()`
- **THEN** other HTTP requests and event loop tasks continue to be serviced during the wait
