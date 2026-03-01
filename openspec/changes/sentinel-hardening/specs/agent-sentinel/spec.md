## ADDED Requirements

### Requirement: Sentinel skill command
The `/wt:sentinel` skill SHALL start and supervise an orchestration run as a Claude agent session.

#### Scenario: Start orchestration
- **WHEN** the user invokes `/wt:sentinel` with optional wt-orchestrate arguments
- **THEN** the agent SHALL start `wt-orchestrate start` in background via Bash tool
- **AND** enter a poll loop checking orchestration-state.json every 15 seconds

#### Scenario: Pass arguments through
- **WHEN** the user invokes `/wt:sentinel --spec docs/v5.md --max-parallel 3`
- **THEN** the agent SHALL pass all arguments to `wt-orchestrate start`

### Requirement: Poll loop with event detection
The sentinel poll loop SHALL run in bash, returning control to the agent only when a decision is needed.

#### Scenario: Normal operation
- **WHEN** orchestration-state.json status is `running` and the state file was updated within 120 seconds
- **THEN** the poll loop SHALL continue without invoking the LLM

#### Scenario: Terminal state detected
- **WHEN** status changes to `done`, `stopped`, or `time_limit`
- **THEN** the poll loop SHALL break and return the status to the agent

#### Scenario: Checkpoint detected
- **WHEN** status changes to `checkpoint`
- **THEN** the poll loop SHALL break and return the checkpoint reason to the agent

#### Scenario: Stale state detected
- **WHEN** status is `running` but orchestration-state.json has not been modified for >120 seconds
- **THEN** the poll loop SHALL break and signal staleness to the agent

#### Scenario: Process exit detected
- **WHEN** the orchestrator background process is no longer running
- **THEN** the poll loop SHALL break and return the exit status to the agent

### Requirement: Decision tree
The agent SHALL follow a defined priority order when making decisions.

#### Scenario: Orchestration complete
- **WHEN** state is `done` with exit code 0
- **THEN** the agent SHALL produce a final report and stop

#### Scenario: User stopped
- **WHEN** state is `stopped` with exit code 0
- **THEN** the agent SHALL report "User stopped" and stop

#### Scenario: Time limit reached
- **WHEN** state is `time_limit` with exit code 0
- **THEN** the agent SHALL summarize progress (changes done, tokens used, time elapsed) and stop

#### Scenario: Crash with non-zero exit
- **WHEN** the orchestrator exits with non-zero code
- **THEN** the agent SHALL read the last 50 lines of orchestration.log
- **AND** diagnose whether the error is recoverable or fatal
- **AND** restart if recoverable, stop and report if fatal

#### Scenario: Rapid crash safety limit
- **WHEN** the orchestrator has crashed 5 consecutive times without running for more than 5 minutes
- **THEN** the agent SHALL stop regardless of diagnosis and report the failure

### Requirement: Checkpoint auto-approve
The agent SHALL auto-approve routine checkpoints and escalate non-routine ones.

#### Scenario: Periodic checkpoint
- **WHEN** a checkpoint has reason `periodic`
- **THEN** the agent SHALL approve it by writing `approved: true` and `approved_at` timestamp to state.json
- **AND** log the auto-approval

#### Scenario: Non-periodic checkpoint
- **WHEN** a checkpoint has a reason other than `periodic` (e.g., `budget_exceeded`, `too_many_failures`)
- **THEN** the agent SHALL report the checkpoint reason to the user and wait for input

### Requirement: Crash diagnosis
The agent SHALL analyze log output before deciding to restart after a crash.

#### Scenario: Known recoverable error
- **WHEN** the last log lines contain transient errors (jq parse error, file lock timeout, network timeout)
- **THEN** the agent SHALL restart after 30 second backoff

#### Scenario: Known fatal error
- **WHEN** the last log lines contain fatal errors (missing file, auth failure, dependency not found)
- **THEN** the agent SHALL stop and report the error

#### Scenario: Unknown error
- **WHEN** the error pattern is not recognized
- **THEN** the agent SHALL restart once
- **AND** if the same pattern recurs, stop and report

### Requirement: Stale state investigation
The agent SHALL investigate when orchestration appears stale.

#### Scenario: Stale but process alive
- **WHEN** state is stale (>120s) but the orchestrator PID is still running
- **THEN** the agent SHALL read the last log lines to understand what's happening
- **AND** continue monitoring if work appears in progress

#### Scenario: Stale and process dead
- **WHEN** state is stale and the orchestrator process is no longer running
- **THEN** the agent SHALL treat it as a crash (read logs, decide restart/stop)

### Requirement: Completion report
The agent SHALL produce a summary report on terminal events.

#### Scenario: Report content
- **WHEN** the orchestration reaches a terminal state (done, time_limit, failed, stopped)
- **THEN** the agent SHALL report: status, active duration, wall duration, changes completed/total, total tokens, number of restarts with reasons, and notable errors or warnings
