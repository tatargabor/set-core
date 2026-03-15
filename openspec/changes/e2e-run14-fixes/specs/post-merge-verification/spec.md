## MODIFIED Requirements

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
- **THEN** the merger SHALL capture `git rev-parse HEAD` before running `wt-merge`
- **AND** pass this SHA to `_post_merge_deps_install()` as `pre_merge_sha`

#### Scenario: Pre-merge SHA not available (fallback)
- **WHEN** `_post_merge_deps_install()` is called without `pre_merge_sha`
- **THEN** the function SHALL fall back to `git diff HEAD~1 --name-only`

#### Scenario: Package.json unchanged
- **WHEN** `merge_change()` succeeds
- **AND** package.json was not modified between pre-merge SHA and HEAD
- **THEN** no dependency install SHALL be triggered
