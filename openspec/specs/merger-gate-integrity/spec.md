## MODIFIED Requirements

### Requirement: Integration e2e smoke phase blocks the merge by default
The merger's two-phase integration e2e gate SHALL treat a smoke-phase failure as blocking when the directive `integration_smoke_blocking` is `True` (the default). A blocking smoke failure SHALL set the change's status to `"integration-e2e-failed"` and trigger a redispatch via the same path that own-test-phase failures use, without running Phase 2 (own tests).

#### Scenario: Smoke failure blocks merge (default behavior)
- **GIVEN** a change whose own tests are correct but whose new code pollutes shared state
- **AND** `integration_smoke_blocking` is `True` (default)
- **WHEN** the merger runs Phase 1 (smoke) and at least one inherited spec fails
- **THEN** the merger SHALL set `change.status = "integration-e2e-failed"`
- **AND** the merger SHALL NOT run Phase 2 (own tests)
- **AND** the merger SHALL return `False` (gate failed)
- **AND** the retry context SHALL name the failing sibling spec files

#### Scenario: Smoke pass lets merge proceed
- **WHEN** the smoke phase passes
- **THEN** Phase 2 runs as before
- **AND** a Phase 2 pass returns `True` (merge proceeds)

#### Scenario: Directive override preserves old non-blocking behavior
- **GIVEN** the operator sets `integration_smoke_blocking: false` in orchestration config
- **AND** the smoke phase fails
- **WHEN** the merger processes the gate
- **THEN** Phase 2 runs despite the smoke failure
- **AND** a Phase 2 pass returns `True` (merge proceeds, old behavior)
- **AND** a WARNING is logged mentioning the smoke failure and the sibling files

### Requirement: Directive `integration_smoke_blocking` controls smoke-phase blocking
The `Directives` dataclass in `lib/set_orch/engine.py` SHALL include a field `integration_smoke_blocking: bool` defaulting to `True`. The merger's `_run_integration_gates` SHALL read this field from `state.extras["directives"]` and honor it when deciding how to handle a smoke failure.

#### Scenario: Default is True
- **WHEN** `Directives()` is instantiated without an explicit `integration_smoke_blocking`
- **THEN** the field value is `True`

#### Scenario: Parsed from raw JSON directives
- **GIVEN** `raw = {"integration_smoke_blocking": False}`
- **WHEN** `parse_directives(raw)` is called
- **THEN** the resulting dataclass has `integration_smoke_blocking == False`

### Requirement: Smoke-failure retry context helps the agent
When the merger blocks a merge due to smoke failure, the retry context handed to the agent on redispatch SHALL:
- Begin with a one-sentence explanation that the failure came from sibling tests, not the change's own tests
- List the failing sibling spec files by name
- Include the first ~1500 characters of the smoke run output (pattern-preserving truncation)
- End with a hint about common root causes (shared-state pollution, cleanup, unique names)

#### Scenario: Retry context structure
- **WHEN** smoke blocks a merge and the change is redispatched
- **THEN** `change.retry_context` starts with text identifying it as a smoke-phase failure
- **AND** `change.retry_context` lists at least one sibling spec file
- **AND** `change.retry_context` references the `testing-conventions.md` guidance on test isolation
