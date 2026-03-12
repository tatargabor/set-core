### Requirement: OpenSpec verify output parsing
The verify gate SHALL parse the `/opsx:verify` output for a structured result sentinel, not just the Claude CLI exit code.

#### Scenario: Verify output contains PASS sentinel
- **WHEN** the `/opsx:verify` output contains a line matching `VERIFY_RESULT: PASS`
- **THEN** the gate SHALL treat the verify step as passed
- **AND** set `spec_coverage_result` to `"pass"` on the change state

#### Scenario: Verify output contains FAIL sentinel
- **WHEN** the `/opsx:verify` output contains a line matching `VERIFY_RESULT: FAIL`
- **THEN** the gate SHALL treat the verify step as failed
- **AND** set `spec_coverage_result` to `"fail"` on the change state
- **AND** follow the existing retry pattern: increment `verify_retry_count`, create `retry_context` with the verify output (truncated to 2000 chars), and call `resume_change()`

#### Scenario: Verify output missing sentinel line (fail-closed)
- **WHEN** the `/opsx:verify` output does NOT contain any `VERIFY_RESULT:` line
- **THEN** the gate SHALL treat the verify step as failed
- **AND** the retry context SHALL note that the verify output was unparseable and request the agent to re-run verify

#### Scenario: Verify retry exhausted
- **WHEN** the verify step fails and `verify_retry_count` >= `max_verify_retries`
- **THEN** the gate SHALL mark the change status as `"failed"`
- **AND** send a critical notification

### Requirement: Verify skill structured output
The `/opsx:verify` skill SHALL emit a machine-readable sentinel line after the human-readable report.

#### Scenario: No CRITICAL issues
- **WHEN** the verify report finds zero CRITICAL issues
- **THEN** the skill SHALL append `VERIFY_RESULT: PASS` as the final line of output

#### Scenario: CRITICAL issues found
- **WHEN** the verify report finds one or more CRITICAL issues
- **THEN** the skill SHALL append `VERIFY_RESULT: FAIL critical=N warning=M` as the final line of output
- **WHERE** N is the count of CRITICAL issues and M is the count of WARNING issues

### Requirement: Review enabled by default
The `review_before_merge` directive SHALL default to `true`.

#### Scenario: No review_before_merge in config
- **WHEN** `review_before_merge` is not set in orchestration.yaml
- **THEN** the orchestrator SHALL default to `true` and run the LLM code review

#### Scenario: Explicit opt-out
- **WHEN** `review_before_merge: false` is explicitly set in orchestration.yaml
- **THEN** the orchestrator SHALL skip the LLM code review

### Requirement: VERIFY_GATE event includes all gate results
The VERIFY_GATE event SHALL include scope check and test file existence results for post-mortem analysis.

#### Scenario: Event fields include scope and test file data
- **WHEN** the VERIFY_GATE event is emitted
- **THEN** the event JSON SHALL include:
  - `scope_check`: `"pass"` or `"fail"` (from `verify_implementation_scope`)
  - `has_tests`: `true` or `false` (from test file existence check)
  - `spec_coverage`: `"pass"`, `"fail"`, or `"skipped"` (from verify output parsing)
  - All existing fields (`test`, `test_ms`, `build_ms`, `review_ms`, `verify_ms`, `total_ms`, `retries`, `retry_tokens`)
