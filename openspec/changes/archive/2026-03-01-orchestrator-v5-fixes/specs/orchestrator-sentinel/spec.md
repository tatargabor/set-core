## ADDED Requirements

### Requirement: Sentinel process wrapper
The `set-sentinel` command SHALL run `set-orchestrate start` in a supervised loop, restarting on crash.

#### Scenario: Clean exit with done state
- **WHEN** `set-orchestrate start` exits with code 0
- **AND** `orchestration-state.json` has status `done`
- **THEN** the sentinel SHALL stop and exit with code 0

#### Scenario: Clean exit with stopped state
- **WHEN** `set-orchestrate start` exits with code 0
- **AND** `orchestration-state.json` has status `stopped`
- **THEN** the sentinel SHALL treat this as a normal stop (user Ctrl+C) and exit with code 0

#### Scenario: Crash recovery
- **WHEN** `set-orchestrate start` exits with a non-zero code
- **AND** the sentinel did not receive SIGINT or SIGTERM
- **THEN** the sentinel SHALL log the exit code and timestamp
- **AND** wait 30 seconds before restarting

#### Scenario: User interrupt propagation
- **WHEN** the sentinel receives SIGINT (Ctrl+C) or SIGTERM
- **THEN** the sentinel SHALL forward the signal to the orchestrator child process
- **AND** SHALL NOT restart after the child exits
- **AND** SHALL exit cleanly

#### Scenario: Max restart limit
- **WHEN** the orchestrator has crashed 5 consecutive times without running for more than 5 minutes
- **THEN** the sentinel SHALL stop, log an error, and exit with code 1

#### Scenario: Restart counter reset on sustained run
- **WHEN** the orchestrator runs for more than 5 minutes before crashing
- **THEN** the sentinel SHALL reset the consecutive crash counter to 0

### Requirement: Stale state cleanup before restart
The sentinel SHALL fix stale orchestration state before restarting.

#### Scenario: State says running but no orchestrator process
- **WHEN** the sentinel is about to restart `set-orchestrate start`
- **AND** `orchestration-state.json` has status `running`
- **THEN** the sentinel SHALL update the status to `stopped` using jq
- **AND** log that stale state was cleaned up

#### Scenario: State is already stopped or done
- **WHEN** `orchestration-state.json` has status `stopped`, `time_limit`, or `done`
- **THEN** the sentinel SHALL not modify the state before restart

### Requirement: Sentinel PID tracking
The sentinel SHALL write its PID to a file for external monitoring.

#### Scenario: PID file creation
- **WHEN** the sentinel starts
- **THEN** it SHALL write its PID to `sentinel.pid` in the current directory

#### Scenario: PID file cleanup
- **WHEN** the sentinel exits (cleanly or after max restarts)
- **THEN** it SHALL remove the `sentinel.pid` file via trap

### Requirement: Sentinel passthrough
The sentinel SHALL pass all arguments to `set-orchestrate start`.

#### Scenario: Argument forwarding
- **WHEN** `set-sentinel --spec docs/v5.md --max-parallel 3` is invoked
- **THEN** the sentinel SHALL invoke `set-orchestrate start --spec docs/v5.md --max-parallel 3`
