## MODIFIED Requirements

### Requirement: total_merge_attempts is always an integer
The merger SHALL ensure `total_merge_attempts` is always read as an integer, never `None`.

#### Scenario: extras field contains None value
- **WHEN** `change.extras.get("total_merge_attempts")` returns `None`
- **THEN** the merger SHALL coerce it to `0` via `int(... or 0)` before arithmetic operations
- **AND** no TypeError SHALL occur

#### Scenario: extras field is missing
- **WHEN** `change.extras` does not contain `total_merge_attempts`
- **THEN** the default value SHALL be `0`

### Requirement: Pre-merge dependency validation in execute_merge_queue
The merge queue SHALL validate that all transitive dependencies of a change have terminal status before running integration gates. NOTE: The `dep-blocked` status already exists in the codebase (set by the dispatcher) — this requirement ADDS the same validation to the merger path.

#### Scenario: All dependencies in terminal status
- **WHEN** a change enters the merge queue in `execute_merge_queue()`
- **AND** all entries in `depends_on` have status in (`merged`, `done`, `skip_merged`, `completed`)
- **THEN** integration gates SHALL proceed normally

#### Scenario: Dependency not yet in terminal status
- **WHEN** a change enters the merge queue
- **AND** one or more `depends_on` entries have status other than `merged`/`done`/`skip_merged`/`completed`
- **THEN** the change SHALL be removed from the merge queue
- **AND** status SHALL be set to `dep-blocked`
- **AND** a log message SHALL identify which dependencies are missing: "Pre-merge dep check: {change} blocked — waiting for {dep1}, {dep2}"

#### Scenario: Dependency merges later triggers re-queue
- **WHEN** a change has status `dep-blocked`
- **AND** all its dependencies transition to terminal status
- **THEN** the engine poll (`_poll_active_changes` or `_retry_merge_queue_safe`) SHALL detect this and set status back to `done`
- **AND** the change SHALL re-enter the merge queue on the next poll cycle

### Requirement: Merge-blocked auto-recovery on issue resolution
The engine poll SHALL detect when blocking issues are resolved and re-queue merge-blocked changes. The link between a change and its blocking issue is found via the issue registry (issues have a `change` field).

#### Scenario: Blocking issue resolved — found via issue registry
- **WHEN** a change has status `merge-blocked`
- **AND** the engine polls the issue registry for issues where `issue.change == change_name`
- **AND** all such issues have state `resolved`, `closed`, or `dismissed`
- **THEN** the engine poll SHALL set the change status to `done`
- **AND** the change SHALL re-enter the merge queue on the next poll cycle

#### Scenario: No issues found for merge-blocked change
- **WHEN** a change has status `merge-blocked`
- **AND** no issues in the registry reference that change
- **THEN** the engine poll SHALL treat it as an unblocked change
- **AND** SHALL set status to `done` for re-queue

#### Scenario: Blocking issue still active
- **WHEN** a change has status `merge-blocked`
- **AND** at least one issue with `issue.change == change_name` has state `open`, `investigating`, or `diagnosed`
- **THEN** the change SHALL remain `merge-blocked`
- **AND** no status change SHALL occur
