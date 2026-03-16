## ADDED Requirements

### Requirement: Test output is parsed for structured results
The verifier SHALL parse test runner output (from unit tests, E2E, and smoke commands) to extract structured pass/fail counts using framework-specific regex patterns. Parsed results SHALL be stored in change state alongside raw output.

#### Scenario: Jest/Vitest output is parsed
- **WHEN** test output contains Jest or Vitest result patterns (e.g., "Tests: N passed, M failed")
- **THEN** the parser SHALL extract passed, failed, and total counts
- **AND** store them in change state as `test_parsed: {passed: N, failed: M, total: T}`

#### Scenario: Playwright output is parsed
- **WHEN** test output contains Playwright result patterns (e.g., "N passed", "M failed")
- **THEN** the parser SHALL extract passed, failed, and total counts
- **AND** store them in change state as `e2e_parsed: {passed: N, failed: M, total: T}`

#### Scenario: Clean test run without failures
- **WHEN** test output shows only passed count with zero failures (e.g., "5 passed (3s)" with no "failed" text)
- **THEN** the parser SHALL extract the passed count and set failed to 0
- **AND** total SHALL equal the passed count

#### Scenario: Unrecognized output format falls back gracefully
- **WHEN** test output does not match any known framework pattern
- **THEN** the parser SHALL return a fallback result with only the exit code
- **AND** no error SHALL be raised

#### Scenario: Parsed results do not change gate behavior
- **WHEN** parsed results are extracted from test output
- **THEN** gate pass/fail decisions SHALL continue to be based on exit codes
- **AND** parsed results SHALL be informational only (stored in state for diagnostics and reporting)
