## ADDED Requirements

### Requirement: Monitor loop checks API approval records
The monitor loop SHALL check the approval record on the latest checkpoint entry when determining whether to resume from checkpoint status. This check is in addition to the existing `checkpoint_auto_approve` directive check.

#### Scenario: Checkpoint approved via API
- **WHEN** the orchestrator is in "checkpoint" status
- **AND** `checkpoint_auto_approve` is `false`
- **AND** the latest checkpoint record has `approved: true`
- **THEN** the orchestrator SHALL set status to "running"
- **AND** a log entry SHALL note "Checkpoint approved via API — resuming"

#### Scenario: Checkpoint not approved and auto-approve disabled
- **WHEN** the orchestrator is in "checkpoint" status
- **AND** `checkpoint_auto_approve` is `false`
- **AND** the latest checkpoint record does not have `approved: true`
- **THEN** the orchestrator SHALL remain in "checkpoint" status
- **AND** dispatch and phase advancement SHALL be skipped

#### Scenario: Auto-approve takes precedence over API record
- **WHEN** the orchestrator is in "checkpoint" status
- **AND** `checkpoint_auto_approve` is `true`
- **THEN** the orchestrator SHALL resume regardless of the approval record state
- **AND** the approval record check SHALL not be evaluated

#### Scenario: No checkpoint records exist
- **WHEN** the orchestrator is in "checkpoint" status
- **AND** the state has no checkpoint records (empty list)
- **AND** `checkpoint_auto_approve` is `false`
- **THEN** the orchestrator SHALL remain in "checkpoint" status
- **AND** no error SHALL be raised
