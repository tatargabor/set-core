## ADDED Requirements

### Requirement: Checkpoint triggers
The system SHALL pause execution at configurable intervals for developer review.

#### Scenario: Every-N-changes checkpoint
- **WHEN** the `checkpoint_every` directive is set to N
- **AND** N changes have transitioned to "done" or "merged" since the last checkpoint
- **THEN** the system SHALL pause the orchestration loop
- **AND** set orchestration status to "checkpoint"

#### Scenario: Failure checkpoint
- **WHEN** any change transitions to "stalled" or "failed"
- **THEN** the system SHALL trigger a checkpoint regardless of the `checkpoint_every` count

#### Scenario: Completion checkpoint
- **WHEN** all changes in the plan have status "done" or "merged"
- **THEN** the system SHALL trigger a final checkpoint

### Requirement: Progress summary generation
The system SHALL generate a human-readable progress summary at each checkpoint.

#### Scenario: Summary file creation
- **WHEN** a checkpoint is triggered
- **THEN** the system SHALL write `orchestration-summary.md` in the project root
- **AND** the file SHALL contain:
  - Timestamp
  - Completed changes with test results (pass/fail)
  - Active changes with iteration progress and token usage
  - Pending changes and their blocked-by dependencies
  - Merge queue (changes awaiting merge)
  - Total token consumption across all changes

#### Scenario: Summary format
- **WHEN** the summary is generated
- **THEN** it SHALL use markdown with a table for per-change status:
  ```
  | Change | Status | Progress | Tokens | Tests |
  ```

### Requirement: Desktop notifications
The system SHALL send desktop notifications when checkpoints are triggered.

#### Scenario: Checkpoint notification
- **WHEN** a checkpoint is triggered
- **AND** the `notification` directive is "desktop"
- **THEN** the system SHALL invoke `notify-send "wt-orchestrate" "<summary>"` with a one-line summary
- **AND** the notification SHALL include: number of changes done, number active, action needed

#### Scenario: Failure notification
- **WHEN** a change fails or stalls
- **AND** the `notification` directive is "desktop"
- **THEN** the system SHALL send an urgent notification: `notify-send -u critical "wt-orchestrate" "Change <name> <stalled|failed>"`

#### Scenario: Notification disabled
- **WHEN** the `notification` directive is "none"
- **THEN** the system SHALL NOT invoke notify-send
- **AND** SHALL still write the summary file

### Requirement: Approval gate
The system SHALL block at checkpoints until the developer provides approval.

#### Scenario: Wait for approval
- **WHEN** the orchestrator enters "checkpoint" status
- **THEN** it SHALL poll `orchestration-state.json` every 5 seconds for an approval signal
- **AND** display "Waiting for approval. Run 'wt-orchestrate approve' to continue."

#### Scenario: Approve command
- **WHEN** the developer runs `wt-orchestrate approve`
- **THEN** the system SHALL write `"approved": true` to the latest checkpoint entry
- **AND** the orchestration loop SHALL resume

#### Scenario: Approve with merge
- **WHEN** the developer runs `wt-orchestrate approve --merge`
- **THEN** the system SHALL approve the checkpoint
- **AND** execute all queued merges before resuming

#### Scenario: Approve timeout
- **WHEN** the orchestrator has been in "checkpoint" status for more than 24 hours without approval
- **THEN** the system SHALL send a reminder notification
- **AND** remain in checkpoint status (no auto-timeout)

### Deferred

- **24-hour checkpoint reminder**: The scenario above (Approve timeout) is not yet implemented. The orchestrator currently waits indefinitely without sending reminders.

### Requirement: GUI dashboard integration
The wt-control GUI SHALL display orchestration status when a plan is active.

#### Scenario: Orchestrator panel visibility
- **WHEN** `orchestration-state.json` exists in a registered project
- **THEN** the wt-control GUI SHALL display an orchestrator status indicator in the project row

#### Scenario: Status data source
- **WHEN** the GUI reads orchestration status
- **THEN** it SHALL parse `orchestration-state.json` for overall status and per-change progress
- **AND** combine with per-worktree `loop-state.json` for iteration-level detail

#### Scenario: Approve from GUI
- **WHEN** the orchestrator is in "checkpoint" status
- **AND** the developer clicks an "Approve" button in the GUI
- **THEN** the GUI SHALL write the approval signal to `orchestration-state.json`
- **AND** the orchestrator monitor loop SHALL detect it on the next poll
