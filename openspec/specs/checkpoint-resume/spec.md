## ADDED Requirements

### Requirement: Resume checks both directive and approval record
The checkpoint resume decision in the monitor loop SHALL check the following sources in order:
1. `checkpoint_auto_approve` directive (if true, resume immediately)
2. Latest checkpoint record `approved` field (if true, resume)
3. Checkpoint timeout (if configured and exceeded, resume with warning)

If none of these conditions are met, the orchestrator remains in checkpoint status.

#### Scenario: Resume via auto-approve directive
- **WHEN** the orchestrator is in "checkpoint" status
- **AND** the `checkpoint_auto_approve` directive is `true`
- **THEN** the orchestrator SHALL set status to "running"
- **AND** log "Checkpoint auto-approved — resuming"

#### Scenario: Resume via API approval record
- **WHEN** the orchestrator is in "checkpoint" status
- **AND** `checkpoint_auto_approve` is `false`
- **AND** the latest checkpoint record has `approved: true`
- **THEN** the orchestrator SHALL set status to "running"
- **AND** log "Checkpoint approved via API — resuming"

#### Scenario: Resume via timeout
- **WHEN** the orchestrator is in "checkpoint" status
- **AND** `checkpoint_auto_approve` is `false`
- **AND** the latest checkpoint is not approved
- **AND** `checkpoint_timeout` is configured and has elapsed
- **THEN** the orchestrator SHALL set status to "running"
- **AND** emit a `CHECKPOINT_TIMEOUT` event
- **AND** log a warning about the timeout auto-resume

#### Scenario: Remain in checkpoint when no resume condition met
- **WHEN** the orchestrator is in "checkpoint" status
- **AND** `checkpoint_auto_approve` is `false`
- **AND** no approval record exists or latest is not approved
- **AND** no timeout is configured or timeout has not elapsed
- **THEN** the orchestrator SHALL remain in "checkpoint" status
- **AND** dispatch and phase advancement SHALL be skipped
- **AND** merge queue retries and completion detection SHALL still run

### Requirement: Merge queue and completion during checkpoint
The orchestrator SHALL continue processing merge queue retries and completion detection while in checkpoint status, even though dispatch and phase advancement are paused.

#### Scenario: Merge queue retried during checkpoint
- **WHEN** the orchestrator is in "checkpoint" status
- **AND** there are entries in the merge queue
- **THEN** merge queue retries SHALL be attempted on each poll cycle

#### Scenario: Completion detected during checkpoint
- **WHEN** the orchestrator is in "checkpoint" status
- **AND** all changes have reached terminal status
- **THEN** the orchestrator SHALL detect completion and exit the monitor loop
