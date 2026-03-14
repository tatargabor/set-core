## Purpose
Dependency graph operations — satisfaction check, failure cascade, topological sort.
## Requirements

## ADDED Requirements

### Requirement: Dependency satisfaction check
The system SHALL provide `deps_satisfied(state, change_name)` that returns `True` if all `depends_on` entries for the named change have status `"merged"` or `"skipped"`.

#### Scenario: No dependencies
- **WHEN** a change has an empty `depends_on` list
- **THEN** `deps_satisfied` returns `True`

#### Scenario: All dependencies merged
- **WHEN** all changes listed in `depends_on` have status `"merged"`
- **THEN** `deps_satisfied` returns `True`

#### Scenario: Dependency still pending
- **WHEN** any change in `depends_on` has status other than `"merged"` or `"skipped"`
- **THEN** `deps_satisfied` returns `False`

### Requirement: Dependency failure check
The system SHALL provide `deps_failed(state, change_name)` that returns `True` if any `depends_on` entry has status `"failed"`. Note: `"merge-blocked"` is NOT a failure — work is done, only merge is stuck.

#### Scenario: No dependencies
- **WHEN** a change has an empty `depends_on` list
- **THEN** `deps_failed` returns `False`

#### Scenario: Dependency failed
- **WHEN** any change in `depends_on` has status `"failed"`
- **THEN** `deps_failed` returns `True`

#### Scenario: Merge-blocked is not failure
- **WHEN** a dependency has status `"merge-blocked"`
- **THEN** `deps_failed` returns `False`

### Requirement: Cascade failed dependencies
The system SHALL provide `cascade_failed_deps(state)` that marks pending changes as `"failed"` if any of their dependencies have terminally failed. It SHALL return the count of cascaded changes.

#### Scenario: Pending change with failed dependency
- **WHEN** change B depends on change A, and A has status `"failed"`
- **AND** B has status `"pending"`
- **THEN** B's status is set to `"failed"` with `failure_reason` indicating the failed dependency
- **AND** a `CASCADE_FAILED` event is emitted

#### Scenario: No cascading needed
- **WHEN** no pending changes have failed dependencies
- **THEN** `cascade_failed_deps` returns 0 and modifies nothing

### Requirement: Topological sort
The system SHALL provide `topological_sort(changes)` that returns change names in dependency-respecting execution order. It SHALL detect circular dependencies.

#### Scenario: Linear dependency chain
- **WHEN** changes A→B→C form a chain (C depends on B, B depends on A)
- **THEN** topological sort returns `["A", "B", "C"]`

#### Scenario: Independent changes
- **WHEN** changes have no dependencies
- **THEN** topological sort returns them in alphabetical order (deterministic)

#### Scenario: Circular dependency
- **WHEN** changes form a cycle (A→B→A)
- **THEN** topological sort raises an error indicating circular dependency
