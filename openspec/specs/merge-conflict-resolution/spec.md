# Merge Conflict Resolution Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Post-merge dependency install
After a successful merge, the orchestrator SHALL check whether `package.json` was modified in the merged diff OR whether a lock file was in the conflict set. If either condition is true, it SHALL run the project's package manager install command (detected via `profile.post_merge_install()` with legacy fallback). The install runs synchronously before the next merge or verify gate. Install failure SHALL be logged as a warning but SHALL NOT revert the merge.

#### Scenario: Merge adds new dependency
- **WHEN** a change that adds a new package to `package.json` is successfully merged
- **THEN** the orchestrator runs the package manager install command on main so the dependency is available for subsequent builds

#### Scenario: Lock file was in conflict set
- **WHEN** a merge succeeds and a lock file was auto-resolved during conflict resolution (indicated by `LOCKFILE_CONFLICTED` marker in merge output)
- **THEN** the orchestrator runs the package manager install command unconditionally, regardless of whether `package.json` changed

#### Scenario: Merge does not change dependencies and no lock file conflict
- **WHEN** a change that does not modify `package.json` is successfully merged AND no lock file was in the conflict set
- **THEN** the orchestrator skips the install step

#### Scenario: Install fails after merge
- **WHEN** the post-merge install command fails (network error, corrupted lockfile)
- **THEN** the orchestrator logs a warning but the merge status remains `merged`

---

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
