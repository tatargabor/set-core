## ADDED Requirements

## IN SCOPE
- Heartbeat emission before and after each long-running monitor operation
- State file mtime touch as a secondary sentinel signal
- Helper function encapsulating heartbeat + touch logic

## OUT OF SCOPE
- Threading or async heartbeat (separate concern, higher complexity)
- Sentinel timeout tuning (180s threshold stays as-is)
- Heartbeat frequency changes for the periodic poll-count-based emit (kept as fallback)

### Requirement: Pre-operation heartbeat emission
The monitor loop SHALL emit a `WATCHDOG_HEARTBEAT` event and touch the state file mtime before each long-running operation (dispatch, merge queue drain, poll active changes, replan).

#### Scenario: Dispatch takes longer than poll interval
- **WHEN** `_dispatch_ready_safe()` takes 120+ seconds to complete
- **THEN** the sentinel's idle timer was reset before the call started, preventing a false-positive kill

#### Scenario: Merge queue drain blocks the loop
- **WHEN** `_drain_merge_then_dispatch()` takes 60+ seconds due to multiple queued merges
- **THEN** a heartbeat was emitted before the call, and the sentinel sees recent activity

### Requirement: Post-operation heartbeat emission
The monitor loop SHALL emit a `WATCHDOG_HEARTBEAT` event after each long-running operation completes, so the sentinel sees continuous activity even across multi-minute operations.

#### Scenario: Back-to-back long operations
- **WHEN** dispatch completes after 90 seconds and merge immediately starts
- **THEN** a heartbeat was emitted between the two operations, keeping the sentinel idle timer well under 180s

### Requirement: Heartbeat helper function
The engine module SHALL provide a helper function that combines event bus heartbeat emission with state file mtime touch into a single call.

#### Scenario: Event bus is None
- **WHEN** the monitor is running without an event bus (e.g., in tests)
- **THEN** the helper still touches the state file mtime without error

#### Scenario: State file does not exist
- **WHEN** the state file path is invalid or the file was removed
- **THEN** the helper logs a warning and continues without raising an exception
