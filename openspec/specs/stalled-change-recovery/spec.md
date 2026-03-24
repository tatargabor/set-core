# Stalled Change Recovery

## ADDED Requirements

## IN SCOPE
- Recovery of stalled changes whose loop-state shows "done"
- Adding "stalled" to _poll_suspended_changes() status filter

## OUT OF SCOPE
- Changing the dead agent detector timing or thresholds
- Auto-retry of stalled changes that are genuinely stalled (loop-state != done)

### Requirement: Stalled changes with completed work are recovered
The monitor's `_poll_suspended_changes()` SHALL handle "stalled" status in addition to "paused", "waiting:budget", "budget_exceeded", and "done". When a stalled change has loop-state status "done", the monitor SHALL recover it by setting the change status to "done" and adding it to the merge queue.

#### Scenario: Stalled change with loop-state done is recovered
- **WHEN** a change has orchestration-state status "stalled" AND its loop-state.json shows status "done"
- **THEN** the monitor sets the change status to "done" and adds it to the merge queue for processing

#### Scenario: Stalled change without loop-state done stays stalled
- **WHEN** a change has orchestration-state status "stalled" AND its loop-state.json shows status "stalled" or "running"
- **THEN** the monitor does NOT recover it — it remains stalled for manual intervention
