# design-fidelity-gate — Delta Spec (v0-design-optional)

## ADDED Requirements

### Requirement: Conditional gate pipeline inclusion
The verifier pipeline SHALL skip registration of the design-fidelity gate when `profile.has_design_pipeline(project_path, directives)` returns `False`. The `register_gates()` method continues to return the GateDefinition unconditionally — filtering happens at the pipeline registration call site in the verifier, where project_path and directives are available.

#### Scenario: Web project with v0-export includes gate in pipeline
- **WHEN** the verifier registers profile gates
- **AND** `has_design_pipeline(project_path, directives)` returns `True`
- **THEN** the design-fidelity gate SHALL be registered in the pipeline

#### Scenario: Web project without v0-export excludes gate from pipeline
- **WHEN** the verifier registers profile gates
- **AND** `has_design_pipeline(project_path, directives)` returns `False`
- **THEN** the design-fidelity gate SHALL NOT be registered in the pipeline

#### Scenario: design_pipeline directive set to none excludes gate
- **WHEN** orchestration directives contain `design_pipeline: "none"`
- **AND** `v0-export/` exists on disk
- **THEN** `has_design_pipeline()` SHALL return `False`
- **AND** the gate SHALL NOT be registered in the pipeline

### Requirement: Runtime skip preserved as defense-in-depth
The existing runtime skip in `execute_design_fidelity_gate()` when no `scaffold.yaml` or `v0-export/` exists SHALL remain unchanged. This covers edge cases where the gate is manually added via gate_overrides or external plugins.

#### Scenario: Gate runs but no v0 source at runtime
- **WHEN** `execute_design_fidelity_gate()` is called
- **AND** neither `scaffold.yaml` nor `v0-export/` exists in the worktree or parents
- **THEN** the gate SHALL return `GateResult` with status `"skipped"` and output `"skipped-no-design-source"`
