## ADDED Requirements

### Requirement: Clear checkpoint-specific state on restart
The orchestrator SHALL clear checkpoint-specific transient fields from state when resuming from a crashed, stopped, or time-limited state. These fields are meaningful only within a single execution context.

#### Scenario: Restart clears checkpoint reason
- **WHEN** the orchestrator enters the resume path
- **AND** the state contains a `checkpoint_reason` field in extras
- **THEN** `checkpoint_reason` SHALL be removed from state extras

#### Scenario: Restart clears checkpoint timer
- **WHEN** the orchestrator enters the resume path
- **AND** the state contains a `checkpoint_started_at` field in extras
- **THEN** `checkpoint_started_at` SHALL be removed from state extras

#### Scenario: Restart resets checkpoint counter
- **WHEN** the orchestrator enters the resume path
- **THEN** `changes_since_checkpoint` SHALL be reset to `0`
- **AND** a log entry SHALL note that checkpoint state was cleaned

#### Scenario: Restart from checkpoint status
- **WHEN** the orchestrator restarts and the state status is "checkpoint"
- **THEN** the status SHALL be changed to "running"
- **AND** checkpoint-specific transient fields SHALL be cleared
- **AND** a log entry SHALL note that stale checkpoint was cleared on restart
