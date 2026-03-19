### Requirement: Post-merge build verification
After a successful merge to main, the orchestrator SHALL verify that the main branch still builds correctly.

#### Scenario: Build verification after merge
- **WHEN** `merge_change()` succeeds via `set-merge`
- **AND** a test_command or build script exists
- **THEN** the orchestrator SHALL run the build command on the main worktree
- **AND** log the result (pass/fail)

#### Scenario: Post-merge build failure
- **WHEN** post-merge build verification fails
- **THEN** the orchestrator SHALL send a critical notification: "Post-merge build broken after {change_name} merge! Manual fix needed."
- **AND** save a Decision memory: "Post-merge build failed after merging {change_name}"
- **AND** the merge SHALL NOT be reverted (manual intervention required)

#### Scenario: Post-merge build success
- **WHEN** post-merge build verification passes
- **THEN** the orchestrator SHALL log "Post-merge: build passed on main"

### Requirement: Post-merge dependency install
After a successful merge, the orchestrator SHALL install dependencies if package.json changed between the pre-merge state and the current HEAD.

#### Scenario: Package.json changed in multi-commit merge
- **WHEN** `merge_change()` succeeds
- **AND** `git diff {pre_merge_sha}..HEAD --name-only` includes `package.json`
- **THEN** the orchestrator SHALL detect the package manager (pnpm/yarn/npm via lockfile)
- **AND** run the appropriate install command
- **AND** log success or failure (non-blocking)

#### Scenario: Pre-merge SHA available
- **WHEN** `merge_change()` is called
- **THEN** the merger SHALL capture `git rev-parse HEAD` before running `set-merge`
- **AND** pass this SHA to `_post_merge_deps_install()` as `pre_merge_sha`

#### Scenario: Pre-merge SHA not available (fallback)
- **WHEN** `_post_merge_deps_install()` is called without `pre_merge_sha`
- **THEN** the function SHALL fall back to `git diff HEAD~1 --name-only`

#### Scenario: Package.json unchanged
- **WHEN** `merge_change()` succeeds
- **AND** package.json was not modified between pre-merge SHA and HEAD
- **THEN** no dependency install SHALL be triggered

### Requirement: Base build cache invalidation
The orchestrator SHALL invalidate the cached base build status after each successful merge, since main has changed.

#### Scenario: Cache invalidated on merge
- **WHEN** `merge_change()` succeeds
- **THEN** `BASE_BUILD_STATUS` and `BASE_BUILD_OUTPUT` SHALL be set to empty strings
- **AND** the next build verification SHALL run a fresh check

