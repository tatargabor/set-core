## IN SCOPE
- GateDefinition dataclass for declaring gates with executor, position, defaults
- Dynamic GateConfig (dict-based instead of fixed dataclass fields)
- Profile.register_gates() interface on ProjectType ABC
- resolve_gate_config uses universal + profile gates
- Pipeline registration from gate registry instead of hardcoded list
- Universal gate defaults per change_type (replaces BUILTIN_GATE_PROFILES)
- Merge queue simplification: integrate-then-ff, serialized per change
- commit_results dynamic field mapping via GateDefinition.result_fields

## OUT OF SCOPE
- GateContext dataclass (separate change — too much blast radius)
- Changing GatePipeline execution engine (register + run stays the same)
- Dynamic gate ordering at runtime (position hints resolved at registration)

### Requirement: Gates shall be declared via GateDefinition
The system SHALL provide a `GateDefinition` dataclass in `gate_runner.py` with fields: name, executor, position, phase, defaults (per change_type), own_retry_counter, extra_retries, result_fields.

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

#### Scenario: Web profile registers e2e + lint
- **WHEN** WebProjectType.register_gates() is called
- **THEN** it SHALL return GateDefinitions for e2e and lint gates
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

### Requirement: Merge queue shall serialize integration
The merge queue SHALL process changes sequentially. For each change: (1) integrate current main into branch with checked result, (2) ff-only merge branch into main. Each subsequent change integrates against the fresh main that includes the previous merge.

#### Scenario: Sequential merge — each sees fresh main
- **GIVEN** changes A and B both in merge queue, both previously integrated with old main
- **WHEN** merge queue processes
- **THEN** A SHALL integrate main and ff-merge first
- **AND** B SHALL integrate main (now including A) and ff-merge second
- **AND** both SHALL succeed without re-running gate pipelines

#### Scenario: Integration conflict blocks merge
- **GIVEN** change C has conflicts when integrating current main
- **WHEN** merge queue processes C
- **THEN** C SHALL be marked merge-blocked
- **AND** queue SHALL continue to next change
- **AND** retry_merge_queue can retry C later (conflicts may resolve after other merges)
