## Purpose
Phase lifecycle — init, advance, override, terminal check.
## Requirements

## ADDED Requirements

### Requirement: Phase state initialization
The system SHALL provide `init_phase_state(state)` that computes unique phases from change `phase` fields, creates a `phases` dict with status tracking, and sets `current_phase` to the lowest phase number.

#### Scenario: Multiple phases
- **WHEN** changes have phase values `[1, 1, 2, 3]`
- **THEN** the state gets `current_phase=1` and `phases={"1": {"status": "running"}, "2": {"status": "pending"}, "3": {"status": "pending"}}`

#### Scenario: Single phase
- **WHEN** all changes have the same phase (or phase is absent)
- **THEN** no `phases` object is created (no phase management needed)

### Requirement: Phase override application
The system SHALL provide `apply_phase_overrides(state, overrides)` that updates change phase assignments from a `{change_name: phase_number}` dict and recalculates the phases object.

#### Scenario: Override changes phase
- **WHEN** `apply_phase_overrides(state, {"add-auth": 2})` is called
- **THEN** the change `add-auth` has its `phase` field set to `2`
- **AND** the phases object is recalculated

#### Scenario: Empty overrides
- **WHEN** overrides dict is empty
- **THEN** no changes are made

### Requirement: Phase terminal check
The system SHALL provide `all_phase_changes_terminal(state, phase)` that returns `True` if every change in the given phase has a terminal status (`"merged"`, `"failed"`, `"skipped"`, `"done"`).

#### Scenario: All terminal
- **WHEN** all changes in phase 1 have status `"merged"` or `"failed"`
- **THEN** `all_phase_changes_terminal(state, 1)` returns `True`

#### Scenario: Still running
- **WHEN** any change in phase 1 has status `"running"`
- **THEN** `all_phase_changes_terminal(state, 1)` returns `False`

### Requirement: Phase advancement
The system SHALL provide `advance_phase(state)` that marks the current phase as `"completed"`, sets `current_phase` to the next phase number, and marks it as `"running"`. It SHALL return `True` if advanced, `False` if no more phases.

#### Scenario: Advance to next phase
- **WHEN** current phase is 1 and phase 2 exists
- **THEN** phase 1 gets `status="completed"` with `completed_at` timestamp
- **AND** `current_phase` becomes 2 and phase 2 gets `status="running"`
- **AND** a `PHASE_ADVANCED` event is emitted with `data={"from": 1, "to": 2}`

#### Scenario: No more phases
- **WHEN** current phase is the last phase
- **THEN** `advance_phase` returns `False`
- **AND** the current phase is marked as `"completed"`
