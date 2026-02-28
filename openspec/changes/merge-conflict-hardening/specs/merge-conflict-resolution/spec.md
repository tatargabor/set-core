## ADDED Requirements

### Requirement: Post-rebase merge verification
After the agent rebase loop completes (regardless of how it ended), the orchestrator SHALL check whether the change branch now merges cleanly into main. If it does, the orchestrator SHALL proceed to merge. If it does not, the orchestrator SHALL set the change status to `merge-blocked`.

#### Scenario: Agent rebase succeeds
- **WHEN** the agent rebase loop ends and the change branch can be merged into main without conflicts
- **THEN** the orchestrator merges the change automatically and sets status to `merged`

#### Scenario: Agent rebase fails
- **WHEN** the agent rebase loop ends and the change branch still has conflicts with main
- **THEN** the orchestrator sets the change status to `merge-blocked` and adds it to the merge retry queue

### Requirement: Conflict fingerprint deduplication
The merge retry path SHALL compute a conflict fingerprint (sorted list of conflicted file paths) before each retry attempt. If the fingerprint matches the previous attempt, the retry loop SHALL stop immediately and mark the change as `merge-blocked`.

#### Scenario: Same conflict on retry
- **WHEN** a merge retry produces conflicts in the same set of files as the previous attempt
- **THEN** the retry loop stops immediately without exhausting remaining attempts

#### Scenario: Different conflict on retry
- **WHEN** a merge retry produces conflicts in a different set of files than the previous attempt (e.g., after another change was merged into main)
- **THEN** the retry loop continues with the next attempt

### Requirement: Merge-blocked exclusion from completion check
The orchestrator's "all changes complete" detection SHALL NOT count changes with status `merge-blocked` or `failed` as complete. Only `merged` and `done` statuses SHALL count as complete.

#### Scenario: Merge-blocked change prevents false completion
- **WHEN** 5 of 6 changes are `merged` and 1 is `merge-blocked`
- **THEN** the orchestrator does NOT trigger auto-replan and does NOT log "All N changes complete"

#### Scenario: All truly complete
- **WHEN** all changes have status `merged` or `done`
- **THEN** the orchestrator triggers auto-replan normally

### Requirement: Merge retry log level reduction
The orchestrator SHALL emit `log_error` only on the first merge conflict for a change and on the final failure (retries exhausted). Intermediate retry attempts SHALL use `log_info` level.

#### Scenario: First conflict is ERROR
- **WHEN** a change encounters its first merge conflict
- **THEN** the orchestrator logs at ERROR level

#### Scenario: Retry attempts are INFO
- **WHEN** a merge retry attempt (attempt 2 through N-1) encounters the same conflict
- **THEN** the orchestrator logs at INFO level with the attempt counter

#### Scenario: Final failure is ERROR
- **WHEN** the final merge retry attempt fails (retries exhausted)
- **THEN** the orchestrator logs at ERROR level with the total attempt count

### Requirement: Post-merge dependency install
After a successful merge, the orchestrator SHALL check whether `package.json` was modified in the merged diff. If so, it SHALL run the project's package manager install command (auto-detected from lockfile: `pnpm-lock.yaml` → `pnpm install`, `yarn.lock` → `yarn install`, `package-lock.json` → `npm install`). The install runs synchronously before the next merge or verify gate. Install failure SHALL be logged as a warning but SHALL NOT revert the merge.

#### Scenario: Merge adds new dependency
- **WHEN** a change that adds a new package to `package.json` is successfully merged
- **THEN** the orchestrator runs the package manager install command on main so the dependency is available for subsequent builds

#### Scenario: Merge does not change dependencies
- **WHEN** a change that does not modify `package.json` is successfully merged
- **THEN** the orchestrator skips the install step

#### Scenario: Install fails after merge
- **WHEN** the post-merge install command fails (network error, corrupted lockfile)
- **THEN** the orchestrator logs a warning but the merge status remains `merged`
