## ADDED Requirements

### Requirement: Merge change pipeline
The system SHALL provide a `merge_change(change_name, state_file)` function that executes the full merge pipeline for a completed change. The pipeline SHALL handle three cases: branch already deleted (skip), branch already ancestor of HEAD (skip), and normal merge via `wt-merge` with LLM conflict resolution.

#### Scenario: Branch no longer exists
- **WHEN** the source branch `change/<name>` does not exist
- **THEN** the system SHALL mark the change as "merged", set smoke_result to "skip_merged", cleanup the worktree, archive the change, and remove from merge queue

#### Scenario: Branch already merged
- **WHEN** the source branch commit is an ancestor of HEAD
- **THEN** the system SHALL mark the change as "merged", set smoke_result to "skip_merged", cleanup the worktree, archive the change, and remove from merge queue

#### Scenario: Successful merge
- **WHEN** `wt-merge` succeeds
- **THEN** the system SHALL mark status as "merged", run post-merge dependency install if package.json changed, run post-merge build verification, run post-merge scope verification, sync running worktrees, execute smoke pipeline, cleanup worktree, archive change, and remove from merge queue

#### Scenario: Merge conflict with agent rebase
- **WHEN** `wt-merge` fails with a real conflict (merge-tree confirms conflict markers) and agent rebase has not been attempted
- **THEN** the system SHALL set retry_context with merge instructions, set merge_rebase_pending, and resume the change for agent-assisted rebase

#### Scenario: Merge conflict after agent rebase
- **WHEN** `wt-merge` fails and agent rebase was already attempted
- **THEN** the system SHALL mark the change as "merge-blocked"

### Requirement: Post-merge smoke pipeline
The system SHALL support both blocking and non-blocking smoke test modes after a successful merge.

#### Scenario: Blocking smoke pass
- **WHEN** smoke_blocking is true and smoke tests pass
- **THEN** the system SHALL set smoke_result to "pass" and smoke_status to "done"

#### Scenario: Blocking smoke fail with fix
- **WHEN** smoke_blocking is true, smoke tests fail, and `smoke_fix_scoped` succeeds
- **THEN** the system SHALL set smoke_result to "fixed" and smoke_status to "done"

#### Scenario: Blocking smoke fail without fix
- **WHEN** smoke_blocking is true, smoke tests fail, and `smoke_fix_scoped` fails
- **THEN** the system SHALL set status to "smoke_failed" and smoke_status to "failed"

#### Scenario: Blocking smoke health check failure
- **WHEN** smoke_blocking is true and the health check URL is unreachable
- **THEN** the system SHALL attempt auto-starting the dev server if configured, or set status to "smoke_blocked"

### Requirement: Merge timeout enforcement
The system SHALL enforce a configurable merge timeout that aborts the merge pipeline if exceeded.

#### Scenario: Timeout before smoke
- **WHEN** the elapsed merge time exceeds the configured timeout before smoke tests start
- **THEN** the system SHALL set status to "merge_timeout" and abort

#### Scenario: Timeout during smoke fix
- **WHEN** the elapsed merge time exceeds the configured timeout during smoke fix
- **THEN** the system SHALL set status to "merge_timeout", set smoke_status to "timeout", and abort

### Requirement: Merge queue management
The system SHALL provide `retry_merge_queue()` that processes queue items and merge-blocked changes with retry limits and conflict fingerprint deduplication.

#### Scenario: Retry with different conflict
- **WHEN** a merge-blocked change has a different conflict fingerprint than the previous attempt
- **THEN** the system SHALL retry the merge up to MAX_MERGE_RETRIES (5) times

#### Scenario: Same conflict fingerprint
- **WHEN** a retry produces the same conflict fingerprint as the previous attempt
- **THEN** the system SHALL stop retrying and mark the change as "merge-blocked"

### Requirement: Worktree cleanup
The system SHALL provide `cleanup_worktree(change_name, wt_path)` that archives agent logs, then removes the worktree via `wt-close` with fallback to manual `git worktree remove`.

#### Scenario: Normal cleanup
- **WHEN** cleanup is requested for a merged change
- **THEN** the system SHALL archive logs from `.claude/logs/`, call `wt-close`, and delete the branch

#### Scenario: wt-close failure fallback
- **WHEN** `wt-close` fails
- **THEN** the system SHALL force-remove the worktree directory and delete the branch manually

### Requirement: Archive change
The system SHALL provide `archive_change(change_name)` that moves the openspec change directory to a dated archive path and commits the move.

#### Scenario: Archive a change
- **WHEN** the change directory exists at `openspec/changes/<name>`
- **THEN** the system SHALL move it to `openspec/changes/archive/YYYY-MM-DD-<name>` and create a git commit

### Requirement: Post-merge worktree sync
The system SHALL provide `_sync_running_worktrees(merged_change)` that syncs all running worktrees with main after a merge to prevent stale-main gate failures.

#### Scenario: Sync running worktrees
- **WHEN** a change is merged
- **THEN** the system SHALL sync each running worktree with main (non-blocking — failures are logged but do not affect merge result)
