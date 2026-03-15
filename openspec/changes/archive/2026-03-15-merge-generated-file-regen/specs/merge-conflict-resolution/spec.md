## MODIFIED Requirements

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
