# orchestration-engine Delta Spec

## MODIFIED Requirements

### Requirement: Dependency satisfaction check
The `deps_satisfied()` function SHALL return true (0) when ALL dependencies of a change have status "merged" OR "skipped". A dependency with status "skipped" SHALL be treated as satisfied for dispatch purposes.

#### Scenario: All dependencies merged
- **WHEN** `deps_satisfied` is called for a change
- **AND** all its `depends_on` entries have status "merged"
- **THEN** it SHALL return 0 (satisfied)

#### Scenario: All dependencies skipped or merged
- **WHEN** `deps_satisfied` is called for a change
- **AND** some dependencies have status "merged" and others have status "skipped"
- **THEN** it SHALL return 0 (satisfied)

#### Scenario: All dependencies skipped
- **WHEN** `deps_satisfied` is called for a change
- **AND** all its `depends_on` entries have status "skipped"
- **THEN** it SHALL return 0 (satisfied)

#### Scenario: Some dependencies still pending
- **WHEN** `deps_satisfied` is called for a change
- **AND** at least one dependency has a non-terminal status (not "merged" and not "skipped")
- **THEN** it SHALL return 1 (not satisfied)

### Requirement: Dependency failure detection
The `deps_failed()` function SHALL NOT treat "skipped" as a failed status. Only "failed" and "merge-blocked" SHALL be considered dependency failures.

#### Scenario: Dependency is skipped
- **WHEN** `deps_failed` is called for a change
- **AND** a dependency has status "skipped"
- **THEN** it SHALL NOT return 0 (skipped is not a failure)

#### Scenario: Dependency is failed
- **WHEN** `deps_failed` is called for a change
- **AND** a dependency has status "failed"
- **THEN** it SHALL return 0 (dependency has failed)

### Requirement: Monitor completion detection
The monitor loop SHALL include "skipped" in the set of terminal statuses when determining if all changes are resolved. The `truly_complete` count SHALL include skipped changes alongside done/merged. The `all_resolved` count SHALL include skipped.

#### Scenario: All changes resolved with some skipped
- **WHEN** the monitor checks completion
- **AND** some changes are "merged", some are "skipped", none are active
- **THEN** the orchestration SHALL be considered complete
- **AND** the completion message SHALL include the skipped count

#### Scenario: Mixed terminal states
- **WHEN** the monitor checks completion
- **AND** changes include merged, skipped, and failed statuses
- **AND** no changes are in active statuses (pending, running, verifying, stalled)
- **THEN** the orchestration SHALL be considered complete
