## ADDED Requirements

### Requirement: Header displays wall clock elapsed time
The TUI header SHALL display elapsed (wall clock) time alongside active time, computed from `started_epoch` in the orchestration state.

#### Scenario: Running orchestration shows live elapsed time
- **WHEN** orchestration status is `running` and `started_epoch` is set
- **THEN** header displays `Elapsed: <duration>` where duration is `now() - started_epoch`, updating every refresh cycle

#### Scenario: Finished orchestration shows final elapsed time
- **WHEN** orchestration status is `done`, `stopped`, or `time_limit`
- **THEN** header displays `Elapsed: <duration>` where duration is `state_file_mtime - started_epoch` (fixed value)

#### Scenario: Missing started_epoch
- **WHEN** `started_epoch` is not present in the state
- **THEN** elapsed time is not displayed in the header
