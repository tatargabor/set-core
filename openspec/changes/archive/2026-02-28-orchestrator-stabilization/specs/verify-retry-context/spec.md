## MODIFIED Requirements

### Requirement: Stale-running status update before resume
WHEN `poll_change()` detects a stale running change (loop-state.json mtime > 5 minutes), it SHALL update the change status to `"stalled"` BEFORE calling `resume_change()`. This prevents parallel resume calls on consecutive poll cycles.

#### Scenario: Stale running change detected
- **WHEN** a change has status "running" but loop-state.json is stale
- **THEN** status SHALL be set to "stalled" before resume_change is called

#### Scenario: Multiple poll cycles during stall
- **WHEN** the next poll cycle runs before the resume takes effect
- **THEN** the change status SHALL already be "stalled" (not "running"), preventing a duplicate resume_change call

### Requirement: Stall count reset on successful resume
WHEN a stalled change is successfully resumed via `resume_change()`, the `stall_count` field SHALL be reset to 0. This prevents accumulated stall counts from prematurely killing a change that recovered and later stalled for a different reason.

#### Scenario: Change recovers then stalls again
- **WHEN** a change recovers from a stall (status back to "running") and later stalls for a different reason
- **THEN** stall_count SHALL start from 0, giving the change a fresh set of 3 retry attempts

#### Scenario: Resume sets running status
- **WHEN** resume_change() is called
- **THEN** status SHALL be set to "running" AND stall_count SHALL be set to 0
