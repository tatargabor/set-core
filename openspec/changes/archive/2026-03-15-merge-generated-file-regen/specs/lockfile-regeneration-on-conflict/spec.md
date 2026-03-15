## ADDED Requirements

### Requirement: Lock file regeneration after conflict resolution
When a lock file conflict is resolved by accepting the target branch version, the system SHALL regenerate the lock file by running the appropriate package manager install command. This ensures the merged `package.json` (which may contain dependencies from both branches) produces a consistent lock file.

#### Scenario: Lock file conflict triggers regeneration
- **WHEN** `auto_resolve_generated_files()` resolves a lock file conflict (e.g., `pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`) by accepting "ours"
- **THEN** the system SHALL detect the package manager from the lock file name using `profile.lockfile_pm_map()` with hardcoded fallback, run the install command, and stage the regenerated lock file

#### Scenario: Profile provides lockfile-to-PM mapping
- **WHEN** a project profile is loaded and `profile.lockfile_pm_map()` returns a non-empty mapping
- **THEN** the system SHALL use the profile mapping to determine which install command to run for the conflicted lock file

#### Scenario: No profile available, fallback mapping used
- **WHEN** no project profile is loaded (NullProfile) or `lockfile_pm_map()` returns empty
- **THEN** the system SHALL fall back to a hardcoded map: `pnpm-lock.yaml` -> `pnpm install`, `yarn.lock` -> `yarn install`, `package-lock.json` -> `npm install`

#### Scenario: Regeneration failure does not block merge
- **WHEN** the install command fails (network error, corrupted manifest, timeout)
- **THEN** the system SHALL log a warning and continue with the "ours" lock file version, allowing the merge to proceed

### Requirement: Machine-readable conflict metadata in merge output
When lock file conflicts are auto-resolved, the merge script SHALL emit a machine-readable marker in stdout so the orchestrator can detect that a lock file was in the conflict set.

#### Scenario: Lock file conflict marker emitted
- **WHEN** `auto_resolve_generated_files()` resolves a lock file conflict
- **THEN** the merge script SHALL emit a line matching `LOCKFILE_CONFLICTED=<filename>` to stdout for each resolved lock file

#### Scenario: No lock file in conflict set
- **WHEN** `auto_resolve_generated_files()` resolves only non-lock-file generated files (e.g., `.tsbuildinfo`)
- **THEN** no `LOCKFILE_CONFLICTED` marker SHALL be emitted

### Requirement: Regeneration in worktree sync
When `sync_worktree_with_main()` auto-resolves lock file conflicts in a worktree, it SHALL also regenerate the lock file using the same profile-aware logic.

#### Scenario: Worktree sync lock file regeneration
- **WHEN** `sync_worktree_with_main()` detects lock file conflicts and resolves them with "ours"
- **THEN** the system SHALL run the install command in the worktree directory to regenerate the lock file before committing the merge
