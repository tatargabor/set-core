## ADDED Requirements

### Requirement: Monitor loop self-watchdog detects all-idle stalls
The monitor loop SHALL track a `last_progress_ts` timestamp and detect when no meaningful progress has occurred within `MONITOR_IDLE_TIMEOUT` seconds (default 300).

#### Scenario: Normal operation resets progress timestamp
- **WHEN** a change transitions status, a merge completes, a dispatch happens, or a gate produces a result
- **THEN** the monitor loop SHALL update `last_progress_ts` to the current time

#### Scenario: Idle timeout triggers recovery
- **WHEN** `now - last_progress_ts` exceeds `MONITOR_IDLE_TIMEOUT`
- **THEN** the monitor loop SHALL attempt recovery by retrying the merge queue, checking for orphaned "done" changes, and logging a warning event

#### Scenario: Persistent idle triggers notification
- **WHEN** recovery attempt does not produce progress AND another `MONITOR_IDLE_TIMEOUT` period elapses
- **THEN** the monitor loop SHALL emit a "MONITOR_STALL" event and send a sentinel notification
