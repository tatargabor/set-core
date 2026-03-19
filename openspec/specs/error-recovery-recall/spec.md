## ADDED Requirements

### Requirement: PostToolUseFailure hook for error-based recall
A new hook script `wt-hook-memory-posttool` SHALL run on `PostToolUseFailure` events matching the `Bash` tool. It SHALL parse the error text and recall memories that describe past fixes for similar errors.

#### Scenario: Bash command fails with authentication error
- **WHEN** a Bash command fails with stderr containing "authentication failed", "permission denied", or "access denied"
- **AND** set-memory has memories tagged with error patterns
- **THEN** the hook SHALL recall memories using the error text as query
- **AND** SHALL output JSON with `hookSpecificOutput.additionalContext` containing past fixes
- **AND** the context SHALL be prefixed with `=== MEMORY: Past fix for this error ===`

#### Scenario: Bash command fails with connection error
- **WHEN** a Bash command fails with stderr containing "connection refused", "could not connect", or "timeout"
- **AND** set-memory has relevant memories
- **THEN** the hook SHALL recall memories related to the connection error
- **AND** SHALL inject them via `additionalContext`

#### Scenario: Bash command fails with generic error
- **WHEN** a Bash command fails with any error text
- **AND** the error text is at least 10 characters long
- **THEN** the hook SHALL use the first 300 characters of the error as a recall query
- **AND** SHALL limit results to 3 memories

#### Scenario: Bash command fails due to user interrupt
- **WHEN** a Bash command fails
- **AND** the `is_interrupt` field is `true`
- **THEN** the hook SHALL exit 0 silently with no output

#### Scenario: No relevant memories exist
- **WHEN** a Bash command fails
- **AND** set-memory recall returns no results
- **THEN** the hook SHALL exit 0 silently with no output

#### Scenario: set-memory not available
- **WHEN** a Bash command fails
- **AND** set-memory is not installed or unhealthy
- **THEN** the hook SHALL exit 0 silently with no output

### Requirement: Error recall does not debounce
The PostToolUseFailure hook SHALL recall on every failure without debouncing, because memories may have been saved mid-session that are relevant to repeated errors.

#### Scenario: Same error occurs three times
- **WHEN** the same Bash command fails three times in a session
- **THEN** the hook SHALL recall memories on each failure
- **AND** results may differ if new memories were saved between failures

### Requirement: Hook deployment includes PostToolUseFailure
The `wt-deploy-hooks` script SHALL include `wt-hook-memory-posttool` in a `PostToolUseFailure` hook event with matcher `"Bash"`.

#### Scenario: Deploy adds PostToolUseFailure hook
- **WHEN** `wt-deploy-hooks /path/to/project` is called
- **THEN** settings.json SHALL contain a `PostToolUseFailure` entry matching `"Bash"` with `wt-hook-memory-posttool`
- **AND** the timeout SHALL be 5 seconds
