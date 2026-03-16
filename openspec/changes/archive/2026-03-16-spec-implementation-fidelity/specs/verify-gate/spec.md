## MODIFIED Requirements

### Requirement: VG-PIPELINE — Gate pipeline (handle_change_done)
When the spec verify gate output lacks a VERIFY_RESULT sentinel, the result SHALL be treated as `"timeout"` and `verify_ok` SHALL be set to False — NOT auto-passed based on other gates succeeding. The spec verify max-turns SHALL be increased to 20 to reduce timeout frequency.

#### Scenario: Spec verify missing sentinel treated as timeout-fail
- **WHEN** the spec verify gate runs `/opsx:verify` and the output does NOT contain "VERIFY_RESULT: PASS" or "VERIFY_RESULT: FAIL"
- **THEN** spec_coverage_result SHALL be set to `"timeout"`
- **AND** verify_ok SHALL be set to False
- **AND** a warning SHALL be logged: "Spec verify timed out — no VERIFY_RESULT sentinel"
- **AND** the gate SHALL follow normal blocking/retry logic (NOT auto-pass based on other gates)

#### Scenario: Spec verify with increased max-turns
- **WHEN** the spec verify gate invokes `/opsx:verify`
- **THEN** the max-turns parameter SHALL be set to 20 (increased from 15)
- **AND** the prompt SHALL include the memory-safety warning
