## MODIFIED Requirements

### Requirement: Monitor safety net covers all non-terminal suspended states
The monitor loop's suspended-change safety net SHALL check changes with status "paused", "waiting:budget", "budget_exceeded", or "done" for completed loop-state, and process them via poll_change when loop-state indicates done.

#### Scenario: Change stuck in "done" status without merge queue entry
- **WHEN** a change has orchestrator status "done" AND its loop-state.json shows status "done" AND it is not in the merge_queue
- **THEN** the safety net SHALL set status to "running" and invoke poll_change to process the done state and queue it for merge

#### Scenario: Existing suspended statuses still handled
- **WHEN** a change has status "paused", "waiting:budget", or "budget_exceeded" AND its loop-state.json shows status "done"
- **THEN** the safety net SHALL process it via poll_change (existing behavior preserved)
