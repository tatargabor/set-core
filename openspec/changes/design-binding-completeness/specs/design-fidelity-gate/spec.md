## ADDED Requirements

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
