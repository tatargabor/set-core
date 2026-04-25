## ADDED Requirements

## IN SCOPE
- New phase in `v0_fidelity_gate.py::run_skeleton_check`: detect parallel implementation of known shell components.
- Heuristic match: filename token-overlap + similar shadcn primitive imports.
- Severity WARN (not BLOCK) due to heuristic nature.
- Operator escape valve via `manifest.shared_aliases` (existing field).

## OUT OF SCOPE
- AST-level semantic equivalence detection (too complex, false positives).
- Cross-language shell detection (TSX-only).
- Pixel-level rendered comparison (covered by fidelity gate's pixel-diff phase).

### Requirement: Shell-shadow check phase in fidelity gate
The fidelity gate's `run_skeleton_check` SHALL include a phase that, for each component listed in `manifest.shared`, scans the agent worktree's `src/components/**/*.tsx` for files whose:
- filename token-overlaps with the shell (≥1 shared token, e.g. `search-bar.tsx` ↔ `search-palette.tsx`)
- imports overlap with the shell's shadcn primitives (≥2 shared shadcn imports)

Files matching both heuristics are reported as `decomposition-shadow` violations.

#### Scenario: Agent creates parallel implementation of search-palette
- **GIVEN** manifest has `v0-export/components/search-palette.tsx` in `shared` (uses `CommandDialog`, `CommandInput`, `CommandList`)
- **AND** agent worktree has `src/components/search-bar.tsx` (uses `Command`, `CommandInput`)
- **WHEN** the fidelity gate's shell-shadow phase runs
- **THEN** a `decomposition-shadow` violation is emitted with severity WARN
- **AND** the message names both files and suggests mounting the shell directly

#### Scenario: Legitimate variant — operator whitelisting
- **GIVEN** agent worktree has `src/components/search-mini.tsx` legitimately (different feature)
- **AND** the previous run generated a WARN that operator deems false-positive
- **WHEN** operator adds `search-mini.tsx: search-palette.tsx` to `manifest.shared_aliases`
- **AND** the fidelity gate runs again
- **THEN** no shell-shadow violation is emitted for `search-mini.tsx`

#### Scenario: No shadow detection without filename overlap
- **GIVEN** agent worktree has `src/components/header.tsx` (does NOT share name tokens with `search-palette.tsx`)
- **WHEN** the shell-shadow phase runs
- **THEN** no violation emitted for `header.tsx`

### Requirement: Severity tier and gate effect
The `decomposition-shadow` violation SHALL be severity WARN (not CRITICAL) by default. WARN-severity violations SHALL be added to the gate report but SHALL NOT block merge.

#### Scenario: WARN does not block merge
- **GIVEN** the fidelity gate emits a `decomposition-shadow` WARN
- **AND** all other gate phases pass
- **THEN** the gate result is "PASSED with warnings"
- **AND** the change can be merged

#### Scenario: Operator can promote to BLOCKING via directive
- **WHEN** an operator sets `gate_overrides.design-fidelity.shell_shadow_severity: "critical"` in `orchestration.yaml`
- **THEN** the next run treats `decomposition-shadow` as BLOCK
- **AND** changes with parallel implementations cannot merge until resolved
