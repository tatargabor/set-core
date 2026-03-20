# Spec: ff-only-merge

## ADDED Requirements

## IN SCOPE
- Fast-forward-only merge from feature branch to main after gates pass
- Retry loop when ff-only fails due to main advancing during gate execution
- Re-integration of main into branch before re-running gates on retry
- Maximum retry limit to prevent infinite loops
- Removal of post-merge build check and build_broken_on_main flag
- Removal of smoke_fix_scoped from the post-merge pipeline
- CLI support for --ff-only mode in set-merge

## OUT OF SCOPE
- Changes to the LLM conflict resolution logic in set-merge (kept for manual use)
- Changes to smoke test configuration or gate profiles
- Changes to worktree creation, dispatch, or agent loop behavior
- Changes to the archive or cleanup pipeline (those remain post-merge)

### Requirement: Fast-forward-only merge to main
After all gates pass on an integrated branch, the merger SHALL advance main to the branch tip using `git merge --ff-only`. The merger SHALL NOT perform a regular merge, squash merge, or any merge that creates a merge commit. If ff-only fails, the merger SHALL NOT fall back to a regular merge.

#### Scenario: Gates pass and ff-only succeeds
- **WHEN** all verify gates pass on a branch that has main integrated and main has not advanced since integration
- **THEN** the system runs `git merge --ff-only` to advance main to the branch tip, marks the change as merged, and proceeds to archive and cleanup

#### Scenario: ff-only fails because main advanced
- **WHEN** ff-only merge fails because main has new commits since the branch integrated main
- **THEN** the system re-integrates main into the branch, re-runs gates, and retries ff-only merge after gates pass again

#### Scenario: ff-only retry limit reached
- **WHEN** the ff-only merge fails repeatedly and the retry count reaches the maximum (configurable, default 3)
- **THEN** the system marks the change as "merge-blocked" and stops retrying

### Requirement: CLI ff-only mode
The `set-merge` command SHALL support a `--ff-only` flag that performs a fast-forward-only merge without conflict resolution, LLM resolution, or conservation checks.

#### Scenario: set-merge with --ff-only succeeds
- **WHEN** `set-merge <change-id> --ff-only` is called and the branch is a descendant of the target branch tip
- **THEN** the merge completes via fast-forward, the target branch tip advances, and exit code is 0

#### Scenario: set-merge with --ff-only fails
- **WHEN** `set-merge <change-id> --ff-only` is called and fast-forward is not possible
- **THEN** the command exits with non-zero code and does NOT attempt regular merge or conflict resolution

### Requirement: Remove post-merge build recovery
The merger SHALL NOT run post-merge build checks, SHALL NOT set the `build_broken_on_main` flag, and SHALL NOT invoke `smoke_fix_scoped` on main. The engine SHALL NOT skip dispatch based on `build_broken_on_main`. These mechanisms are unnecessary because gates already verified the build on the integrated branch before the ff-only merge.

#### Scenario: No build check after merge
- **WHEN** a change is successfully merged via ff-only
- **THEN** the system does NOT run a build command on main, does NOT set build_broken_on_main, and proceeds directly to archive and worktree sync

#### Scenario: Dispatch not blocked by stale flag
- **WHEN** a stale `build_broken_on_main` flag exists in state from a previous orchestration run
- **THEN** the engine ignores the flag and dispatches changes normally

### Requirement: Preserve post-merge non-build steps
The merger SHALL continue to run post-merge steps that are NOT related to build verification: dependency installation (if package.json changed), custom post_merge_command, i18n sidecar merge, scope verification, archive, worktree sync, and post-merge hooks.

#### Scenario: Post-merge deps and archive still run
- **WHEN** a change is merged via ff-only
- **THEN** the system runs dependency install (if needed), custom post-merge command, i18n sidecar merge, scope verification, archive, and worktree sync in the same order as before
