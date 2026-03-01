## MODIFIED Requirements

### Requirement: Sentinel exit logic (MODIFIED)
The bash `wt-sentinel` SHALL stop on all clean exit states, not just `done` and `stopped`.

#### Scenario: Time limit state
- **WHEN** `wt-orchestrate start` exits with code 0
- **AND** `orchestration-state.json` has status `time_limit`
- **THEN** the sentinel SHALL stop and exit with code 0

#### Scenario: Any clean exit defaults to stop
- **WHEN** `wt-orchestrate start` exits with code 0
- **AND** the state is not `done`, `stopped`, or `time_limit`
- **THEN** the sentinel SHALL stop and exit with code 0 (safe default)
- **AND** log the unexpected state for debugging

#### Scenario: Only non-zero exit triggers restart
- **WHEN** `wt-orchestrate start` exits with non-zero code
- **THEN** the sentinel SHALL restart with backoff (existing behavior)

### Requirement: Sentinel file logging (ADDED)
The bash sentinel SHALL log to orchestration.log in addition to stdout.

#### Scenario: Log format
- **WHEN** the sentinel logs a message
- **THEN** it SHALL append `[sentinel] <message>` to orchestration.log
- **AND** also write to stdout

### Requirement: Sentinel stale state handling (MODIFIED)
The sentinel SHALL handle checkpoint state in addition to running.

#### Scenario: Checkpoint state before restart
- **WHEN** the sentinel is about to restart and state is `checkpoint`
- **THEN** the sentinel SHALL NOT modify the state (checkpoint persists across restarts)
