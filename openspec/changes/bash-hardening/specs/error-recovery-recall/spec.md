## MODIFIED Requirements

### Requirement: jq errors in state operations are visible
State manipulation functions SHALL NOT suppress jq errors with `2>/dev/null`. When a jq operation fails, the error message SHALL be logged via `log_error` before returning non-zero.

#### Scenario: jq parse error is logged
- **WHEN** jq encounters invalid JSON in state.json
- **THEN** the error is logged with the function name and jq error message, and the function returns 1

#### Scenario: jq filter error is logged
- **WHEN** jq receives an invalid filter expression
- **THEN** the error is logged and the function returns 1

### Requirement: State corruption detection
The system SHALL detect and report when state.json contains invalid JSON, rather than silently returning empty/null values.

#### Scenario: Corrupted state file on read
- **WHEN** `get_change_status` or `get_changes_by_status` is called and state.json contains invalid JSON
- **THEN** an error is logged and the function returns 1 (not an empty string)
