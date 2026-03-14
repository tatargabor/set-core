## MODIFIED Requirements

### Requirement: Verify gate output parsing uses strict sentinel detection
The verify gate SHALL require the `VERIFY_RESULT: PASS` or `VERIFY_RESULT: FAIL` sentinel line to be present in the output. Missing sentinel SHALL be treated as failure, not pass.

#### Scenario: Sentinel present — PASS
- **WHEN** verify output contains `VERIFY_RESULT: PASS`
- **THEN** spec_coverage_result SHALL be "pass"

#### Scenario: Sentinel present — FAIL
- **WHEN** verify output contains `VERIFY_RESULT: FAIL`
- **THEN** spec_coverage_result SHALL be "fail" and retry SHALL be triggered

#### Scenario: Sentinel missing
- **WHEN** verify output does not contain any `VERIFY_RESULT:` line
- **THEN** spec_coverage_result SHALL be "fail" and retry_context SHALL instruct re-running verify with sentinel requirement

#### Scenario: Sentinel detection scans full output
- **WHEN** verify output exceeds 2000 characters
- **THEN** sentinel detection SHALL search the complete output, not only the first 2000 characters
