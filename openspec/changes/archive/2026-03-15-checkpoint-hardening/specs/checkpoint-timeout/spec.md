## ADDED Requirements

### Requirement: Checkpoint timeout directive
The orchestrator SHALL support a `checkpoint_timeout` directive (integer, seconds) that auto-resumes from checkpoint status after the specified duration. The default value SHALL be `0` (no timeout / wait indefinitely).

#### Scenario: Timeout configured and exceeded
- **WHEN** the orchestrator is in "checkpoint" status
- **AND** the `checkpoint_timeout` directive is set to a positive value (e.g., 3600)
- **AND** the elapsed time since entering checkpoint exceeds `checkpoint_timeout` seconds
- **THEN** the orchestrator SHALL set status to "running"
- **AND** a `CHECKPOINT_TIMEOUT` event SHALL be emitted with the elapsed duration
- **AND** a warning-level log entry SHALL note the timeout and auto-resume

#### Scenario: Timeout not configured (default)
- **WHEN** the orchestrator is in "checkpoint" status
- **AND** the `checkpoint_timeout` directive is `0` (default)
- **THEN** the orchestrator SHALL wait indefinitely for manual approval or auto-approve
- **AND** no timeout check SHALL be performed

#### Scenario: Approved before timeout expires
- **WHEN** the orchestrator is in "checkpoint" status
- **AND** a `checkpoint_timeout` is configured
- **AND** the checkpoint is approved (via API or auto-approve) before the timeout expires
- **THEN** the orchestrator SHALL resume normally via the approval path
- **AND** no `CHECKPOINT_TIMEOUT` event SHALL be emitted

### Requirement: Checkpoint start time tracking
The orchestrator SHALL record the epoch timestamp when entering checkpoint status, stored as `checkpoint_started_at` in state extras. This timestamp is used by the timeout check.

#### Scenario: Timestamp recorded on checkpoint entry
- **WHEN** `trigger_checkpoint()` is called
- **THEN** `checkpoint_started_at` SHALL be set to the current epoch time in state extras

#### Scenario: Timestamp cleared on restart
- **WHEN** the orchestrator restarts or resumes from a stopped state
- **THEN** `checkpoint_started_at` SHALL be cleared from state extras

### Requirement: Checkpoint timeout directive parsing
The `checkpoint_timeout` directive SHALL be parsed from the directives JSON and exposed on the `Directives` dataclass.

#### Scenario: Directive parsed from JSON
- **WHEN** the directives JSON contains `"checkpoint_timeout": 3600`
- **THEN** `Directives.checkpoint_timeout` SHALL equal `3600`

#### Scenario: Directive absent from JSON
- **WHEN** the directives JSON does not contain `checkpoint_timeout`
- **THEN** `Directives.checkpoint_timeout` SHALL equal `0` (default, no timeout)
