## ADDED Requirements

### Requirement: poll_change handles waiting:human
The orchestrator treats `waiting:human` as a distinct state.

#### Scenario: Ralph reports waiting:human
- **WHEN** `poll_change()` reads loop-state.json with status `waiting:human`
- **THEN** update change status to `"waiting:human"` in orchestration-state.json
- **AND** do NOT increment `stall_count`
- **AND** do NOT call `resume_change()`
- **AND** log manual task summary from `manual_tasks` array in loop-state.json

### Requirement: Status display for waiting:human changes
#### Scenario: TUI/log shows human-waiting changes
- **WHEN** a change has status `waiting:human`
- **THEN** display with `⏸ HUMAN` label and the first pending manual task description
- **AND** show hint: `Run: wt-manual show <change-name>`

### Requirement: Resume from waiting:human
#### Scenario: Change resumes after manual input
- **WHEN** `wt-manual resume` updates change status from `waiting:human` back to `"dispatched"`
- **AND** the orchestrator's next poll cycle detects this
- **THEN** resume the Ralph loop for that change (call `resume_change()`)

## MODIFIED Requirements

### Requirement: Change status enum
#### Scenario: New valid status value
- **WHEN** change statuses are checked or displayed
- **THEN** `waiting:human` is a valid status alongside `pending|dispatched|running|verifying|done|merged|failed|stalled|merge-blocked`
