## ADDED Requirements

### Requirement: FF exhausted fallback tasks.md generation
The Ralph loop SHALL generate a minimal `tasks.md` when the ff retry limit is exceeded, instead of stalling.

#### Scenario: FF exhausted with proposal.md present
- **WHEN** `ff_attempts` reaches `ff_max_retries`
- **AND** no `tasks.md` exists in the change directory
- **AND** `proposal.md` exists in the change directory
- **THEN** the loop SHALL create a fallback `tasks.md` with a single task referencing the proposal
- **AND** SHALL reset `ff_attempts` to 0
- **AND** SHALL log a warning: "Generated fallback tasks.md from proposal (ff exhausted)"
- **AND** SHALL continue the loop (not stall)

#### Scenario: FF exhausted with existing tasks.md
- **WHEN** `ff_attempts` reaches `ff_max_retries`
- **AND** `tasks.md` already exists in the change directory
- **THEN** the loop SHALL reset `ff_attempts` to 0
- **AND** SHALL continue the loop normally
- **AND** SHALL NOT overwrite the existing `tasks.md`

#### Scenario: FF exhausted without proposal.md
- **WHEN** `ff_attempts` reaches `ff_max_retries`
- **AND** no `proposal.md` exists in the change directory
- **THEN** the loop SHALL stall as before (existing behavior)
