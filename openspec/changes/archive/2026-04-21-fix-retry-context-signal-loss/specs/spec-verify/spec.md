## MODIFIED Requirements

### Requirement: Spec verify gate shall distinguish LLM verdict from infrastructure failure

The spec_verify gate SHALL classify each LLM invocation result into one of three categories before mapping to gate status:

1. **LLM verdict**: the LLM produced output containing either `VERIFY_RESULT: PASS` or `VERIFY_RESULT: FAIL`. Exit code from the claude CLI is a secondary signal; the sentinel is authoritative.
2. **Infrastructure failure**: the LLM did not produce a `VERIFY_RESULT` sentinel AND the termination reason parsed from the stream-json output (or the timeout marker on `run_claude_logged`) is one of `max_turns`, `timeout`, or `crash`.
3. **Ambiguous output**: neither a sentinel nor a detectable infrastructure cause — handled by the existing classifier fallback path.

Only category 1 `VERIFY_RESULT: FAIL` (with `CRITICAL_COUNT > 0`) and category 3 confirmed-critical by classifier SHALL map to `GateResult("spec_verify", "fail")` and consume a `verify_retry_count` slot. Category 2 SHALL trigger one retry at doubled `--max-turns` budget (configurable, default: 80). If the retry is also category 2, the gate SHALL return `GateResult("spec_verify", "skipped")` and SHALL emit a `GATE_INFRA_FAIL` event (or an equivalent `infra_fail: true` flag on the existing `VERIFY_GATE` event). Category 2 outcomes SHALL NOT consume a retry slot and SHALL NOT populate `retry_context` with the LLM transcript.

#### Scenario: LLM hits max_turns on both sonnet and opus

- **GIVEN** sonnet spec_verify returns `exit_code=1` with stream-json `terminal_reason: max_turns` and no `VERIFY_RESULT` sentinel
- **AND** opus escalation at default budget returns `exit_code=1` with `terminal_reason: max_turns`
- **WHEN** `_execute_spec_verify_gate` evaluates the result
- **THEN** the gate SHALL retry opus once more with `--max-turns` doubled
- **AND** if the retry also terminates on `max_turns`, the gate SHALL return `GateResult("spec_verify", "skipped")`
- **AND** the change's `verify_retry_count` SHALL NOT be incremented
- **AND** the `retry_context` field on the returned GateResult SHALL be empty
- **AND** an event SHALL be emitted with `type=GATE_INFRA_FAIL` or `type=VERIFY_GATE` with `data.infra_fail=True`

#### Scenario: LLM produces VERIFY_RESULT: FAIL with CRITICAL findings

- **GIVEN** the LLM output contains `VERIFY_RESULT: FAIL` and `CRITICAL_COUNT: 2`
- **WHEN** `_execute_spec_verify_gate` evaluates the result
- **THEN** the gate SHALL return `GateResult("spec_verify", "fail")`
- **AND** retry_context SHALL contain the structured finding list and original scope
- **AND** retry_context SHALL NOT contain the raw stream-json transcript

#### Scenario: LLM produces VERIFY_RESULT: PASS

- **GIVEN** the LLM output contains `VERIFY_RESULT: PASS`
- **WHEN** `_execute_spec_verify_gate` evaluates the result
- **THEN** the gate SHALL return `GateResult("spec_verify", "pass")` — existing behavior preserved
- **AND** the `exit_code` value from the claude CLI SHALL NOT override this verdict

#### Scenario: Run exit is timeout (subprocess timeout, not max_turns)

- **GIVEN** `run_claude_logged` returns with the timeout flag set
- **AND** no `VERIFY_RESULT` sentinel is present in the partial output
- **WHEN** `_execute_spec_verify_gate` evaluates the result
- **THEN** the gate SHALL retry once with the same timeout but doubled `--max-turns`
- **AND** if the retry also times out, the gate SHALL return `GateResult("spec_verify", "skipped")` with `infra_fail=True`

#### Scenario: Legacy "CLI error stays non-blocking" replaced

- **GIVEN** the existing spec (pre-change) mapped `exit_code != 0` unconditionally to `GateResult("spec_verify", "fail")` with retry_context containing the verify output
- **WHEN** the new classification logic is applied
- **THEN** that blanket mapping SHALL be replaced by the three-category classification above
- **AND** the case where exit_code != 0 AND a `VERIFY_RESULT: FAIL` sentinel is present SHALL still yield a fail with structured retry_context (category 1)
- **AND** the case where exit_code != 0 with no sentinel and no parseable infra cause SHALL fall through to the classifier fallback path (category 3)
