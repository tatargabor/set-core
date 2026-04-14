## ADDED Requirements

### Requirement: Unified infra-fail classification

All LLM-backed gates (`spec_verify`, `review`, and any future LLM gate) SHALL classify their CLI invocation outcomes into three categories using a shared helper `classify_gate_outcome(cmd_result, output, gate_name)`:

1. **verdict**: output contains a gate-specific sentinel (e.g., `VERIFY_RESULT: PASS|FAIL` for spec_verify, or a CRITICAL/HIGH block structure for review). Sentinel is authoritative — `exit_code != 0` SHALL NOT override it.
2. **infra**: `cmd_result.timed_out = True` OR stream-JSON `terminal_reason = max_turns` without a sentinel OR subprocess crashed with no output. Infra outcomes SHALL trigger one retry at doubled `--max-turns` budget; if the retry is also infra, the gate SHALL return `status="skipped"` with `infra_fail=True` on the GateResult, and the failing attempt SHALL NOT consume a retry counter.
3. **ambiguous**: neither sentinel nor infra marker — falls back to the existing classifier path.

#### Scenario: exit=1 but VERIFY_RESULT: FAIL present in output tail
- **GIVEN** a spec_verify LLM call returns `exit_code=1` and the last 5KB of output contains `VERIFY_RESULT: FAIL`, `CRITICAL_COUNT: 2`
- **WHEN** `classify_gate_outcome` runs
- **THEN** the classification SHALL be "verdict" (not infra)
- **AND** the gate SHALL honor the sentinel (return fail with 2 critical findings)
- **AND** the retry counter SHALL be consumed as normal

#### Scenario: max_turns without sentinel → infra
- **GIVEN** an LLM call returns `exit_code=1` with stream-JSON `terminal_reason: max_turns` and no VERIFY_RESULT sentinel
- **WHEN** `classify_gate_outcome` runs
- **THEN** classification SHALL be "infra"
- **AND** the gate SHALL retry once at doubled `--max-turns`
- **AND** if the retry is also infra, `GateResult.status="skipped"` with `infra_fail=True`
- **AND** the retry counter SHALL NOT increment

#### Scenario: Review gate infra-fail detection
- **GIVEN** a review gate LLM call timed out (`timed_out=True`)
- **WHEN** `classify_gate_outcome` runs (previously review lacked this)
- **THEN** classification SHALL be "infra"
- **AND** the same retry + abstain behavior SHALL apply as for spec_verify

### Requirement: Config drift warning

On engine startup, the engine SHALL compare the mtime of `set/orchestration/config.yaml` against `set/orchestration/directives.json`. If `config.yaml` is newer (the user edited it after directives were generated), a `CONFIG_DRIFT` event SHALL be emitted with `{yaml_mtime, directives_mtime, delta_secs}` and a WARNING log line SHALL note that the edit is not active until orchestrator restart or manual regeneration.

#### Scenario: User edited yaml after orchestrator start
- **GIVEN** `directives.json` was written at `T0` and `config.yaml` was edited at `T0 + 3600` seconds
- **WHEN** the engine starts a new supervisor at `T0 + 7200`
- **THEN** `CONFIG_DRIFT` event SHALL be emitted
- **AND** a WARNING log SHALL read: "config.yaml is 3600s newer than directives.json — changes not active until regenerated"

#### Scenario: No drift
- **GIVEN** `directives.json` was written after the latest `config.yaml` edit
- **WHEN** the engine starts
- **THEN** no `CONFIG_DRIFT` event SHALL be emitted

#### Scenario: Missing directives.json (fresh init)
- **GIVEN** `directives.json` does not exist
- **WHEN** the engine starts
- **THEN** no `CONFIG_DRIFT` event SHALL be emitted (directives will be generated from yaml)
