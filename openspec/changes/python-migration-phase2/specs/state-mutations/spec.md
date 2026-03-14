## Purpose
Locked state field updates with event emission on status transitions.
## Requirements

## ADDED Requirements

### Requirement: Atomic field updates with file locking
The system SHALL provide `update_state_field(path, field, value)` and `update_change_field(path, change_name, field, value)` functions that atomically read-modify-write the state file under an `fcntl.flock` advisory lock.

#### Scenario: Update top-level state field
- **WHEN** `update_state_field(path, "status", "stopped")` is called
- **THEN** the state file's `status` field is set to `"stopped"` atomically
- **AND** no other concurrent writer can modify the file during the operation

#### Scenario: Update change-level field
- **WHEN** `update_change_field(path, "add-auth", "status", "running")` is called
- **THEN** the change named `add-auth` has its `status` set to `"running"`
- **AND** the modification is written atomically under flock

#### Scenario: Concurrent writers serialize
- **WHEN** two processes call `update_change_field` on the same state file simultaneously
- **THEN** both updates are applied without data loss or corruption
- **AND** the lock file is `<state_file>.lock` adjacent to the state file

### Requirement: Event emission on status transitions
The system SHALL emit `STATE_CHANGE` events via the EventBus when a change's `status` field transitions to a new value. It SHALL emit `TOKENS` events on significant token updates (delta > 10,000).

#### Scenario: Status transition emits STATE_CHANGE
- **WHEN** `update_change_field` changes a change's status from `"pending"` to `"running"`
- **THEN** a `STATE_CHANGE` event is emitted with `data={"from": "pending", "to": "running"}`
- **AND** the event includes the change name

#### Scenario: Same-status update does not emit
- **WHEN** `update_change_field` sets status to the same value it already has
- **THEN** no `STATE_CHANGE` event is emitted

#### Scenario: Token update emits TOKENS event
- **WHEN** `update_change_field` updates `tokens_used` with a delta exceeding 10,000
- **THEN** a `TOKENS` event is emitted with `data={"delta": N, "total": M}`

#### Scenario: Failed status triggers on_fail hook
- **WHEN** a change's status transitions to `"failed"`
- **THEN** the `on_fail` lifecycle hook is invoked (if configured)

### Requirement: State query functions
The system SHALL provide `get_change_status(state, name)`, `get_changes_by_status(state, status)`, and `count_changes_by_status(state, status)` operating on in-memory `OrchestratorState`.

#### Scenario: Get single change status
- **WHEN** `get_change_status(state, "add-auth")` is called
- **THEN** it returns the status string of the named change (e.g., `"running"`)

#### Scenario: Filter changes by status
- **WHEN** `get_changes_by_status(state, "pending")` is called
- **THEN** it returns a list of change names with status `"pending"`

#### Scenario: Count changes by status
- **WHEN** `count_changes_by_status(state, "merged")` is called
- **THEN** it returns the integer count of changes with status `"merged"`

### Requirement: Locked state context manager
The system SHALL provide a `locked_state(path)` context manager that loads the state under flock, yields it for modification, and saves atomically on exit.

#### Scenario: Context manager usage
- **WHEN** code uses `with locked_state(path) as state: state.status = "stopped"`
- **THEN** the state is loaded, modified, and saved atomically under a single lock acquisition
- **AND** the lock is released when the context manager exits (including on exception)
