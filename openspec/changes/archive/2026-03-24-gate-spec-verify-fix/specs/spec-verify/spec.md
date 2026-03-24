## IN SCOPE
- Fix spec_verify gate to return "fail" on explicit VERIFY_RESULT: FAIL
- Retry context with verification output on failure

## OUT OF SCOPE
- Changing verify invocation method
- Making timeout blocking
- Changing what /opsx:verify checks

### Requirement: Spec verify gate shall block on explicit FAIL
When the spec verify output contains `VERIFY_RESULT: FAIL`, the gate SHALL return GateResult with status "fail" and retry_context containing the verification output and original scope.

#### Scenario: VERIFY_RESULT: FAIL blocks merge
- **GIVEN** the spec verify Claude invocation succeeds (exit code 0)
- **AND** output contains "VERIFY_RESULT: FAIL"
- **WHEN** _execute_spec_verify_gate evaluates the result
- **THEN** it SHALL return GateResult("spec_verify", "fail")
- **AND** retry_context SHALL include the last 2000 chars of verify output
- **AND** retry_context SHALL include the original change scope

#### Scenario: VERIFY_RESULT: PASS unchanged
- **GIVEN** output contains "VERIFY_RESULT: PASS"
- **WHEN** _execute_spec_verify_gate evaluates
- **THEN** it SHALL return GateResult("spec_verify", "pass")

#### Scenario: Timeout (no sentinel) stays non-blocking
- **GIVEN** output contains neither PASS nor FAIL sentinel
- **WHEN** _execute_spec_verify_gate evaluates
- **THEN** it SHALL return GateResult("spec_verify", "pass")
- **AND** SHALL log warning about timeout

#### Scenario: CLI error stays non-blocking
- **GIVEN** run_claude returns non-zero exit code
- **WHEN** _execute_spec_verify_gate evaluates
- **THEN** it SHALL return GateResult("spec_verify", "fail") with retry_context
- **AND** retry_context SHALL include verify output tail and original scope
