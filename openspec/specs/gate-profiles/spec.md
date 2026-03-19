## ADDED Requirements

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

### Requirement: Built-in gate profiles per change_type
The system SHALL define a `BUILTIN_GATE_PROFILES` dict mapping each of the 6 change_type strings to a GateConfig instance with type-appropriate gate settings.

#### Scenario: Infrastructure profile skips build/test/e2e/smoke
- **WHEN** the built-in profile for `"infrastructure"` is looked up
- **THEN** build, test, e2e, smoke SHALL be `"skip"`, test_files_required SHALL be `False`, review SHALL be `"run"`, scope_check SHALL be `"run"`, spec_verify SHALL be `"soft"`, rules SHALL be `"run"`

#### Scenario: Feature profile enables all gates
- **WHEN** the built-in profile for `"feature"` is looked up
- **THEN** all gate fields SHALL be `"run"`, test_files_required SHALL be `True`

#### Scenario: Schema profile has warn-only tests
- **WHEN** the built-in profile for `"schema"` is looked up
- **THEN** test SHALL be `"warn"`, build SHALL be `"run"`, e2e SHALL be `"skip"`, smoke SHALL be `"skip"`, test_files_required SHALL be `False`

#### Scenario: Foundational profile skips e2e and smoke
- **WHEN** the built-in profile for `"foundational"` is looked up
- **THEN** build and test SHALL be `"run"`, test_files_required SHALL be `True`, e2e SHALL be `"skip"`, smoke SHALL be `"skip"`

#### Scenario: Cleanup-before profile has warn-only tests
- **WHEN** the built-in profile for `"cleanup-before"` is looked up
- **THEN** test SHALL be `"warn"`, test_files_required SHALL be `False`, e2e SHALL be `"skip"`, smoke SHALL be `"skip"`, review SHALL be `"run"`, spec_verify SHALL be `"soft"`

#### Scenario: Cleanup-after profile is lightest
- **WHEN** the built-in profile for `"cleanup-after"` is looked up
- **THEN** test SHALL be `"warn"`, test_files_required SHALL be `False`, review SHALL be `"skip"`, rules SHALL be `"skip"`, e2e SHALL be `"skip"`, smoke SHALL be `"skip"`, spec_verify SHALL be `"soft"`

#### Scenario: Unknown change_type defaults to feature
- **WHEN** an unrecognized change_type string is used
- **THEN** the system SHALL fall back to a default GateConfig equivalent to the feature profile (all gates `"run"`)

### Requirement: Gate config resolution chain
The `resolve_gate_config()` function SHALL resolve a GateConfig for a change by applying 4 layers in order: (1) built-in profile for change_type, (2) profile plugin gate_overrides, (3) per-change skip flags and gate_hints, (4) orchestration directive overrides. Later layers SHALL override earlier ones.

#### Scenario: Built-in only (no overrides)
- **WHEN** resolve_gate_config is called with a Change of type `"infrastructure"` and no profile, no directives
- **THEN** the result SHALL match the built-in infrastructure profile

#### Scenario: Profile plugin overrides built-in
- **WHEN** a profile plugin returns `{"e2e": "run"}` for `"foundational"` type
- **THEN** the resolved GateConfig SHALL have e2e=`"run"` while keeping other fields from the built-in foundational profile

#### Scenario: skip_test maps to GateConfig
- **WHEN** a Change has `skip_test=True`
- **THEN** the resolved GateConfig SHALL have test=`"skip"` and test_files_required=`False`, regardless of built-in or plugin settings

#### Scenario: skip_review maps to GateConfig
- **WHEN** a Change has `skip_review=True`
- **THEN** the resolved GateConfig SHALL have review=`"skip"`, regardless of built-in or plugin settings

#### Scenario: gate_hints override profile
- **WHEN** a Change has `gate_hints={"smoke": "skip"}`
- **THEN** the resolved GateConfig SHALL have smoke=`"skip"`, overriding the built-in profile value

#### Scenario: Directive overrides everything
- **WHEN** orchestration directives contain `gate_overrides: {infrastructure: {build: "run"}}`
- **THEN** the resolved GateConfig for an infrastructure change SHALL have build=`"run"`, overriding built-in `"skip"`

#### Scenario: Resolution logs debug output
- **WHEN** resolve_gate_config completes
- **THEN** it SHALL log a debug message with the change name, type, and key gate field values

### Requirement: Profile plugin gate_overrides extension point
The NullProfile class SHALL include a `gate_overrides(change_type: str) -> dict` method returning an empty dict. The ProjectType ABC in wt-project-base SHALL include the same method with a default empty-dict implementation.

#### Scenario: NullProfile returns empty overrides
- **WHEN** NullProfile.gate_overrides is called with any change_type
- **THEN** it SHALL return an empty dict

#### Scenario: ProjectType subclass can override gates
- **WHEN** a ProjectType subclass implements gate_overrides returning `{"e2e": "run"}` for `"foundational"`
- **THEN** resolve_gate_config SHALL apply those overrides to the built-in profile

### Requirement: Orchestration directive gate_overrides
The config system SHALL support a `gate_overrides` directive in orchestration.yaml as a nested dict keyed by change_type then gate field name.

#### Scenario: Directive parsed from YAML
- **WHEN** orchestration.yaml contains `gate_overrides: {infrastructure: {build: run}}`
- **THEN** the parsed directives SHALL pass these overrides to resolve_gate_config

#### Scenario: Empty directive has no effect
- **WHEN** no `gate_overrides` directive exists in orchestration.yaml
- **THEN** resolve_gate_config SHALL use only built-in and profile overrides

### Requirement: Planning rules document gate profiles
The planning rules text injected into the LLM decomposition prompt SHALL include a section describing what gates each change_type activates, and that gate configuration is automatic from change_type.

#### Scenario: LLM sees gate profile info
- **WHEN** planning rules are rendered for the decompose prompt
- **THEN** the rules text SHALL include a gate profile section listing which gates run/skip/warn for each change_type

#### Scenario: gate_hints documented as optional
- **WHEN** planning rules describe the plan JSON schema
- **THEN** the optional `gate_hints` field SHALL be documented with an example

### Requirement: VERIFY_GATE event includes gate profile info
The VERIFY_GATE event emitted after gate pipeline completion SHALL include `gate_profile` (change_type), `gates_skipped` (list of gate names that were skipped), and `gates_warn_only` (list of gate names in warn/soft mode).

#### Scenario: Infrastructure change event shows skipped gates
- **WHEN** an infrastructure change completes the gate pipeline
- **THEN** the VERIFY_GATE event SHALL include `gates_skipped` containing at least `["build", "test", "e2e", "smoke"]`

#### Scenario: Feature change event shows no skipped gates
- **WHEN** a feature change completes the gate pipeline
- **THEN** the VERIFY_GATE event SHALL have an empty `gates_skipped` list
