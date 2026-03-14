## Purpose
Crash recovery by replaying events JSONL to reconstruct consistent state.
## Requirements

## ADDED Requirements

### Requirement: State reconstruction from events
The system SHALL provide `reconstruct_state_from_events(state_path, events_path)` that rebuilds the state file by replaying `STATE_CHANGE` and `TOKENS` events from the JSONL audit trail. It SHALL preserve plan-origin fields (scope, complexity, depends_on) from the existing state file and only update runtime fields.

#### Scenario: Replay status transitions
- **WHEN** the events file contains `STATE_CHANGE` events for change `add-auth` going `pending→running→done`
- **THEN** after reconstruction, `add-auth` has status `"done"`

#### Scenario: Replay token updates
- **WHEN** the events file contains `TOKENS` events with increasing totals for a change
- **THEN** the change's `tokens_used` field reflects the last recorded total

#### Scenario: Running changes become stalled
- **WHEN** reconstruction finds changes with status `"running"` (process crashed mid-execution)
- **THEN** those changes are set to `"stalled"` (no live process to back the running status)

#### Scenario: Derive orchestrator status
- **WHEN** all changes have terminal status after replay
- **THEN** the orchestrator status is set to `"done"`

#### Scenario: Derive orchestrator status — mixed
- **WHEN** some changes have non-terminal status after replay
- **THEN** the orchestrator status is set to `"stopped"`

#### Scenario: No events file
- **WHEN** the events JSONL file does not exist
- **THEN** reconstruction fails gracefully and returns `False`

#### Scenario: Emit reconstruction event
- **WHEN** reconstruction completes successfully
- **THEN** a `STATE_RECONSTRUCTED` event is emitted with event count and final status
