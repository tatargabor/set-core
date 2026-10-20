# design-fidelity-gate Specification

## Purpose
TBD - created by archiving change design-binding-completeness. Update Purpose after archive.

## Requirements

### Requirement: Shell-shadow check phase
The fidelity gate's `run_skeleton_check` SHALL include a shell-shadow detection phase. For each component listed in `manifest.shared`, the phase SHALL scan the agent worktree's `src/components/**/*.tsx` for files that match BOTH heuristics:
- Filename token-overlap with the shell (≥1 shared kebab-case token)
- ≥2 shared shadcn primitive imports

Files matching both heuristics SHALL be reported as `decomposition-shadow` violations with severity WARN.

#### Scenario: Shadow detected on parallel implementation
- **GIVEN** manifest shell `v0-export/components/search-palette.tsx` (imports `CommandDialog`, `CommandInput`, `CommandList`)
- **AND** agent worktree has `src/components/search-bar.tsx` (imports `Command`, `CommandInput`, `CommandList`)
- **WHEN** the shell-shadow phase runs
- **THEN** a `decomposition-shadow` violation is emitted naming both files

#### Scenario: No shadow without heuristic match
- **GIVEN** agent worktree has `src/components/header.tsx` (imports `Sheet`, `SheetTrigger`)
- **AND** manifest shell `search-palette.tsx` (imports `Command*`)
- **WHEN** the shell-shadow phase runs
- **THEN** no violation emitted (no token overlap, no import overlap)

#### Scenario: Shared aliases whitelist legitimate variants
- **GIVEN** `manifest.shared_aliases: {search-mini.tsx: search-palette.tsx}`
- **AND** agent worktree has `src/components/search-mini.tsx`
- **WHEN** the shell-shadow phase runs
- **THEN** no violation for `search-mini.tsx`

### Requirement: Shell-shadow severity is configurable
The default severity for `decomposition-shadow` violations SHALL be WARN (gate result "PASSED with warnings", merge proceeds). The operator SHALL be able to override via `gate_overrides.design-fidelity.shell_shadow_severity: "critical"` in `orchestration.yaml` to make it BLOCK.

#### Scenario: Default WARN does not block merge
- **GIVEN** the fidelity gate emits `decomposition-shadow` WARN
- **AND** all other phases pass
- **THEN** merge proceeds; the violation is in the report

#### Scenario: Override to critical blocks merge
- **WHEN** `gate_overrides.design-fidelity.shell_shadow_severity: "critical"` is set
- **AND** `decomposition-shadow` is emitted
- **THEN** merge is blocked; operator must resolve before retry

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
