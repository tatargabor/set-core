## ADDED Requirements

### Requirement: Counter resets after checkpoint trigger
The `changes_since_checkpoint` counter SHALL be reset to `0` when a checkpoint is triggered, so that the next checkpoint triggers after another `checkpoint_every` changes.

#### Scenario: Counter resets on periodic checkpoint
- **WHEN** `changes_since_checkpoint` reaches the `checkpoint_every` threshold
- **AND** `trigger_checkpoint()` is called with reason "periodic"
- **THEN** `changes_since_checkpoint` SHALL be set to `0` in the state file

#### Scenario: Counter resets on token hard limit checkpoint
- **WHEN** the token hard limit is exceeded
- **AND** `trigger_checkpoint()` is called with reason "token_hard_limit"
- **THEN** `changes_since_checkpoint` SHALL be set to `0` in the state file

#### Scenario: Predictable checkpoint cadence
- **WHEN** `checkpoint_every` is set to `3`
- **AND** 3 changes complete, triggering a checkpoint
- **AND** the checkpoint is approved and orchestration resumes
- **AND** 3 more changes complete
- **THEN** a second checkpoint SHALL be triggered (at change 6 total, not change 9)

### Requirement: Checkpoint record created on trigger
The `trigger_checkpoint()` function SHALL append a checkpoint record to the state's `checkpoints` list when triggered, capturing the reason and timestamp.

#### Scenario: Checkpoint record appended
- **WHEN** `trigger_checkpoint()` is called
- **THEN** a new record SHALL be appended to `state.checkpoints` with:
  - `reason`: the trigger reason string
  - `triggered_at`: ISO 8601 timestamp
  - `changes_completed`: count of changes in terminal status at trigger time
  - `approved`: `false` (default, awaiting approval)
