## MODIFIED Requirements

### Requirement: Single default constant for e2e_retry_limit
A module-level constant `DEFAULT_E2E_RETRY_LIMIT` SHALL exist in `lib/set_orch/engine.py` and SHALL be the single source of truth for the default integration e2e retry limit.

#### Scenario: Directives default reads the constant
- **WHEN** the `Directives` dataclass is instantiated without an explicit `e2e_retry_limit`
- **THEN** the field value equals `DEFAULT_E2E_RETRY_LIMIT`

#### Scenario: Merger fallback reads the constant
- **WHEN** `merger.py` computes the integration e2e retry limit and the directives dict has no `e2e_retry_limit` key
- **THEN** the fallback value equals `DEFAULT_E2E_RETRY_LIMIT`
- **AND** the constant is imported from `engine` (or a shared module), not duplicated as a literal

#### Scenario: Explicit directive override still honored
- **WHEN** a consumer project sets `e2e_retry_limit: 5` in its orchestration config
- **THEN** both the directive read path AND the merger fallback path use `5`, not the default

### Requirement: Default lowered from 5 to 3
The `DEFAULT_E2E_RETRY_LIMIT` constant SHALL be `3`.

#### Scenario: Unchanged default in new runs
- **WHEN** a new orchestration starts without an explicit `e2e_retry_limit` directive
- **THEN** `Directives.e2e_retry_limit == 3`
- **AND** the integration e2e gate allows at most 3 redispatch attempts before marking the change as `failed`

#### Scenario: Override compatibility
- **WHEN** a project needs more retries due to known test flakiness
- **THEN** setting `e2e_retry_limit: 5` in orchestration.yaml (or equivalent) overrides the default without code changes
