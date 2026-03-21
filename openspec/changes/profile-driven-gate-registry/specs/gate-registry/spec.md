## IN SCOPE
- GateDefinition dataclass for declaring gates with executor, position, defaults
- Dynamic GateConfig (dict-based instead of fixed dataclass fields)
- Profile.register_gates() interface on ProjectType ABC
- resolve_gate_config uses universal + profile gates
- Pipeline registration from gate registry instead of hardcoded list
- Universal gate defaults per change_type (replaces BUILTIN_GATE_PROFILES)
- GateContext dataclass for standardized executor parameters

## OUT OF SCOPE
- Changing GatePipeline execution engine (register + run stays the same)
- Dynamic gate ordering at runtime (position hints resolved at registration)
- Post-merge smoke pipeline restructuring (stays in merger.py, uses same GateDefinition)

### Requirement: Gates shall be declared via GateDefinition
The system SHALL provide a `GateDefinition` dataclass in `gate_runner.py` with fields: name, executor, position, phase, defaults (per change_type), own_retry_counter, extra_retries.

#### Scenario: Universal gate definition
- **GIVEN** a universal gate "build" with executor and own_retry_counter
- **WHEN** defined as GateDefinition
- **THEN** it SHALL be usable by GatePipeline.register()

### Requirement: GateConfig shall support arbitrary gate names
GateConfig SHALL store gate modes as a `dict[str, str]` instead of fixed dataclass fields. `should_run()`, `is_blocking()`, and `is_warn_only()` SHALL work with any gate name.

#### Scenario: Profile-registered gate checked
- **GIVEN** a profile registers gate "e2e" with mode "run"
- **WHEN** `gc.should_run("e2e")` is called
- **THEN** it SHALL return True

#### Scenario: Unknown gate defaults to "run"
- **GIVEN** a gate name not in the config
- **WHEN** `gc.should_run("unknown")` is called
- **THEN** it SHALL return True (default mode is "run")

### Requirement: Profiles shall register domain-specific gates
ProjectType ABC SHALL define `register_gates() -> list[GateDefinition]` returning empty list by default. CoreProfile inherits this default. Domain profiles (web, python) override to provide their gates.

#### Scenario: Web profile registers e2e + lint + smoke
- **WHEN** WebProjectType.register_gates() is called
- **THEN** it SHALL return GateDefinitions for e2e, lint, and smoke gates
- **AND** each SHALL include an executor callable and change_type defaults

#### Scenario: NullProfile registers no extra gates
- **WHEN** NullProfile.register_gates() is called
- **THEN** it SHALL return empty list

### Requirement: resolve_gate_config shall merge universal and profile gates
The resolution chain SHALL be: (1) universal gate defaults, (2) universal change_type defaults, (3) profile gate registration with defaults, (4) profile gate_overrides(), (5) per-change overrides, (6) directive overrides.

#### Scenario: Web feature change gets all gates
- **GIVEN** profile is WebProjectType, change_type is "feature"
- **WHEN** resolve_gate_config runs
- **THEN** result SHALL have build, test, scope_check, test_files, review, rules, spec_verify (universal) AND e2e, lint (web) all with mode "run"

#### Scenario: Infrastructure change skips domain gates
- **GIVEN** profile is WebProjectType, change_type is "infrastructure"
- **WHEN** resolve_gate_config runs
- **THEN** universal gates SHALL have infrastructure defaults (build=skip, test=skip)
- **AND** web gates SHALL have infrastructure defaults (e2e=skip, lint=skip)

### Requirement: Pipeline shall register gates from registry
handle_change_done SHALL collect universal gates + profile gates, resolve ordering via position hints, and register them with GatePipeline in the resolved order.

#### Scenario: Gates execute in position order
- **GIVEN** universal gates (build→test→scope→test_files→review→rules→spec_verify) and profile gates (e2e after:test, lint after:test_files)
- **WHEN** pipeline runs
- **THEN** execution order SHALL be: build, test, e2e, scope_check, test_files, lint, review, rules, spec_verify
