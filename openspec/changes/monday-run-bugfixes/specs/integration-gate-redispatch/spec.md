## MODIFIED Requirements

### Requirement: Test gate detects no-test-files and skips
The integration gate SHALL EXTEND the existing missing-script detection in `_run_integration_gates()` (merger.py:836-858) with additional patterns for "no test files found" scenarios, treating them as a skip (not a failure).

#### Scenario: vitest exits with "no test files found"
- **WHEN** the test gate runs `pnpm test` (or the configured test command)
- **AND** the exit code is non-zero
- **AND** the output contains one of: `"No test suite found"`, `"no test files found"`, `"No tests found, exiting with code 1"` (case-insensitive)
- **THEN** the gate result SHALL be `skip` (not `fail`)
- **AND** the merge pipeline SHALL continue to the next gate
- **AND** a log message SHALL say: "Integration gate: test skipped for {change} (no test files found)"

#### Scenario: jest exits with no tests
- **WHEN** the test gate runs and jest outputs `"No tests found, exiting with code 1"`
- **AND** the exit code is 1
- **THEN** the gate result SHALL be `skip`

#### Scenario: vitest exits with actual test failure
- **WHEN** the test gate runs and the output contains assertion errors or test failure details (e.g., `"FAIL"`, `"AssertionError"`, `"expected"`)
- **AND** the exit code is non-zero
- **THEN** the gate result SHALL be `fail` as before

#### Scenario: Test gate does not retry on skip
- **WHEN** the test gate result is `skip` (no test files)
- **THEN** the merge pipeline SHALL NOT retry the test gate
- **AND** SHALL proceed to the next gate immediately

### Requirement: Gate retry stops when output is identical
The integration gate pipeline SHALL detect when consecutive retry cycles (across poll iterations) produce identical gate output, and stop retrying.

#### Scenario: Same output persisted across retry cycles
- **WHEN** a gate (test, build, or e2e) fails
- **THEN** the merger SHALL compute a SHA256 hash of the first 2000 characters of gate output
- **AND** SHALL store the hash in `change.extras["gate_output_hashes"]` (a list, appended per retry cycle)

#### Scenario: 3 consecutive identical hashes triggers stop
- **WHEN** `gate_output_hashes` contains 3 or more entries
- **AND** the last 3 hashes are identical
- **THEN** the gate SHALL mark as `fail` with `integration_gate_fail` set to `"{gate}_identical_output"`
- **AND** the change status SHALL be set to `integration-failed`
- **AND** SHALL NOT retry further (regardless of remaining retry budget)

#### Scenario: Different output resets the hash list
- **WHEN** a gate fails with a hash different from the previous entry
- **THEN** the hash list SHALL be reset to contain only the new hash
