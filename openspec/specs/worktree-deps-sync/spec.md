## ADDED Requirements

## IN SCOPE
- Detect lockfile/package.json changes during worktree sync with main
- Automatically run package manager install after sync when deps changed
- Support pnpm, yarn, npm detection (existing `_detect_package_manager`)

## OUT OF SCOPE
- Initial worktree bootstrap deps install (already handled by `bootstrap_worktree`)
- Post-merge deps install on main (already handled by `_post_merge_deps_install`)
- Lock file conflict resolution during sync (handled by generated file auto-resolve)

### Requirement: Reinstall deps after worktree sync detects dependency changes
<!-- REQ-DEPS-SYNC -->
When `sync_worktree_with_main()` successfully merges main into a worktree branch, it MUST check whether `package.json` or any lockfile (`pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`) was modified in the merged commits. If so, it MUST run the appropriate package manager install command.

#### Scenario: Master merge includes new dependencies
- **WHEN** a change on main adds a new dependency to `package.json`
- **AND** `sync_worktree_with_main()` merges main into a running worktree
- **THEN** the system SHALL detect that `package.json` changed in the merge diff
- **AND** run `pnpm install` (or appropriate PM) in the worktree
- **AND** log the install result

#### Scenario: Master merge does not change deps
- **WHEN** `sync_worktree_with_main()` merges main into a running worktree
- **AND** no `package.json` or lockfile changed in the merge
- **THEN** no install command SHALL be run (avoid unnecessary overhead)

#### Scenario: Install fails
- **WHEN** the package manager install fails after sync
- **THEN** the sync result SHALL still report success (non-blocking)
- **AND** a warning SHALL be logged
