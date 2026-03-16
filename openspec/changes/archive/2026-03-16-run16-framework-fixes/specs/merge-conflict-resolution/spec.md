## MODIFIED Requirements

### Requirement: Auto-resolve patterns SHALL cover `.claude/` runtime files
The generated file conflict resolver SHALL auto-resolve (checkout --theirs) any file under the `.claude/` directory prefix, in addition to the existing basename-matched patterns (lockfiles, .tsbuildinfo).

#### Scenario: Merge conflict on `.claude/activity.json`
- **WHEN** a merge conflict occurs on `.claude/activity.json`
- **THEN** the system SHALL auto-resolve by checking out the incoming version (`--theirs`)
- **AND** the system SHALL NOT mark the change as merge-blocked

#### Scenario: Merge conflict on `.claude/logs/iter-001.log`
- **WHEN** a merge conflict occurs on a file under `.claude/logs/`
- **THEN** the system SHALL auto-resolve by checking out the incoming version
- **AND** the basename matching SHALL NOT be used (since `iter-001.log` is not in the pattern set)

#### Scenario: Merge conflict on real source file plus `.claude/*` files
- **WHEN** a merge conflict involves both `.claude/*` files and real source files (e.g., `src/app.ts`)
- **THEN** the system SHALL auto-resolve the `.claude/*` files
- **AND** the system SHALL report the real source file conflicts as non-generated
- **AND** the change SHALL proceed to agent-assisted rebase for the real conflicts

### Requirement: Conflict matching SHALL support both basename and prefix patterns
The `_is_generated_file()` check SHALL match a conflicted file path against:
1. Basename match: `os.path.basename(path)` in the generated patterns set (existing behavior)
2. Prefix match: path starts with a known auto-resolve prefix (`.claude/`)

Either match SHALL qualify the file for auto-resolution.
