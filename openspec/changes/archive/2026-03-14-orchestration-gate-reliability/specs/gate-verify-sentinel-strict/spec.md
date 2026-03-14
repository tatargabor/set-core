## ADDED Requirements

### Requirement: Missing verify sentinel line is treated as FAIL
The verify gate SHALL treat the absence of a `VERIFY_RESULT: PASS` or `VERIFY_RESULT: FAIL` sentinel line as a verification failure, triggering retry logic.

#### Scenario: Sentinel line present with PASS
- **WHEN** the verify output contains `VERIFY_RESULT: PASS`
- **THEN** the gate SHALL mark spec_coverage_result as "pass"

#### Scenario: Sentinel line present with FAIL
- **WHEN** the verify output contains `VERIFY_RESULT: FAIL critical=N warning=M`
- **THEN** the gate SHALL mark spec_coverage_result as "fail" and trigger retry

#### Scenario: Sentinel line missing
- **WHEN** the verify output does NOT contain any `VERIFY_RESULT:` line
- **THEN** the gate SHALL mark spec_coverage_result as "fail" and set retry_context to instruct the agent to re-run verify with proper sentinel output

### Requirement: Verify sentinel parsed from full output before truncation
The verify gate SHALL search for the `VERIFY_RESULT:` sentinel in the complete verify output before truncating for retry_context storage.

#### Scenario: Sentinel beyond 2000 chars
- **WHEN** verify output is longer than 2000 characters AND the sentinel line is beyond the first 2000 characters
- **THEN** the gate SHALL still detect and parse the sentinel correctly
