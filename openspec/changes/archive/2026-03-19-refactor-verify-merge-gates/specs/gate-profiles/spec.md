## MODIFIED Requirements

### Requirement: GateConfig dataclass
The system SHALL define a `GateConfig` dataclass with fields for each verification gate: `build`, `test`, `test_files_required`, `e2e`, `scope_check`, `review`, `spec_verify`, `rules`, `smoke`. Each gate field SHALL accept string modes: `"run"`, `"skip"`, `"warn"`, `"soft"`. The dataclass SHALL also include optional `max_retries: int`, `review_model: str`, and `review_extra_retries: int` (default 1) override fields.

#### Scenario: Default GateConfig has all gates enabled
- **WHEN** a GateConfig is created with no arguments
- **THEN** all gate fields SHALL be `"run"`, `test_files_required` SHALL be `True`, `max_retries` SHALL be `None`, `review_model` SHALL be `None`, `review_extra_retries` SHALL be `1`

#### Scenario: GateConfig mode helpers
- **WHEN** `should_run(gate_name)` is called
- **THEN** it SHALL return `True` for modes `"run"`, `"warn"`, `"soft"` and `False` for `"skip"`

#### Scenario: GateConfig blocking check
- **WHEN** `is_blocking(gate_name)` is called
- **THEN** it SHALL return `True` only for mode `"run"` and `False` for `"warn"`, `"soft"`, `"skip"`

#### Scenario: review_extra_retries controls review retry budget
- **WHEN** GateConfig has `review_extra_retries=2`
- **THEN** the review gate retry limit SHALL be `max_retries + 2`
