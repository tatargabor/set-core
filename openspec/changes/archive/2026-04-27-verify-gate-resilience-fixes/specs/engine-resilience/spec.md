## ADDED Requirements

### Requirement: No silent gate-failure returns
The framework SHALL ensure that every gate-failure code path in `merger.py` and `verifier.py` either dispatches the agent (`resume_change` with retry context) or emits a terminal-failure event. Silent returns of `False` / fail-status without one of these actions are forbidden and SHALL be detected by an AST-level regression test.

#### Scenario: Integration-test-fail dispatches agent with retry_context
- **WHEN** the integration-test gate fails for a change
- **THEN** the merger calls `resume_change(state_file, change_name)` with a populated `retry_context` describing the test output
- **AND** sets `status = "integration-e2e-failed"`
- **AND** increments `integration_e2e_retry_count`

#### Scenario: Regression test catches new silent path
- **WHEN** a developer adds a new gate-failure return path without a dispatch call
- **THEN** `tests/unit/test_gate_failure_dispatch.py` fails at CI time with the function name and source line
