## ADDED Requirements

### Requirement: safe_jq_update validates output before overwriting
The system SHALL provide a `safe_jq_update()` function that validates jq output is non-empty before performing the atomic mv. If jq fails or produces empty output, the original file MUST remain untouched and the function MUST return non-zero.

#### Scenario: Successful jq update
- **WHEN** `safe_jq_update "$file" '.status = "done"'` is called with valid JSON in `$file`
- **THEN** the file is updated atomically (via mktemp + mv) and the function returns 0

#### Scenario: jq filter error
- **WHEN** `safe_jq_update "$file" '.invalid[['` is called with an invalid jq filter
- **THEN** the original file remains unchanged, an error is logged, and the function returns 1

#### Scenario: Source file contains invalid JSON
- **WHEN** `safe_jq_update "$file" '.status = "done"'` is called and `$file` contains invalid JSON
- **THEN** the original file remains unchanged, an error is logged, and the function returns 1

#### Scenario: Temp file cleanup on failure
- **WHEN** `safe_jq_update` fails for any reason
- **THEN** the temporary file created by mktemp SHALL be removed (via trap RETURN)

### Requirement: with_state_lock serializes state file access
The system SHALL provide a `with_state_lock()` function that acquires an exclusive flock on `${STATE_FILENAME}.lock` before executing the wrapped command, with a configurable timeout.

#### Scenario: Uncontended lock acquisition
- **WHEN** `with_state_lock update_state_field "status" '"done"'` is called and no other process holds the lock
- **THEN** the lock is acquired, the command executes, and the lock is released

#### Scenario: Contended lock with timeout
- **WHEN** `with_state_lock` is called while another process holds the lock and the timeout (default 10s) expires
- **THEN** the function logs an error and returns 1 without executing the wrapped command

#### Scenario: Lock release on command failure
- **WHEN** the wrapped command fails (returns non-zero)
- **THEN** the lock SHALL still be released (flock subshell exits)

### Requirement: update_state_field uses safe_jq_update with locking
The `update_state_field()` function SHALL internally use `safe_jq_update` for the write and acquire the state lock for the duration of the operation.

#### Scenario: State field update with locking
- **WHEN** `update_state_field "status" '"paused"'` is called
- **THEN** the state lock is acquired, jq output is validated, the file is updated atomically, and the lock is released

### Requirement: update_change_field uses safe_jq_update with locking
The `update_change_field()` function SHALL internally use `safe_jq_update` for the write and acquire the state lock for the entire read-old-status + write + emit-event sequence.

#### Scenario: Status change with event emission under lock
- **WHEN** `update_change_field "my-change" "status" '"merged"'` is called
- **THEN** the state lock is held from the initial status read through the write and event emission, preventing interleaved updates

### Requirement: All orchestration jq writes use safe_jq_update
Every `mktemp` + `jq` + `mv` pattern in `lib/orchestration/` SHALL be replaced with a call to `safe_jq_update`. No direct `jq ... > "$tmp" && mv "$tmp"` patterns SHALL remain in orchestration code.

#### Scenario: No raw jq write patterns remain
- **WHEN** the codebase is searched for `mktemp` followed by `jq ... > "$tmp" && mv` in `lib/orchestration/`
- **THEN** zero matches are found (all converted to safe_jq_update calls)
