# Post Merge Sync Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Running worktrees sync with main after each merge
After a successful merge, the orchestrator SHALL sync all running worktrees with the updated main branch. When sync encounters lock file conflicts, it SHALL auto-resolve them with "ours" AND regenerate the lock file via the appropriate install command before committing.

#### Scenario: Successful merge triggers sync
- **WHEN** `merge_change()` completes successfully for change A AND changes B and C have status "running"
- **THEN** `sync_worktree_with_main` SHALL be called for both B and C

#### Scenario: Sync auto-resolves lock file conflict with regeneration
- **WHEN** a worktree sync encounters a lock file conflict (e.g., `pnpm-lock.yaml`)
- **THEN** the system SHALL accept "ours", run the install command in the worktree to regenerate the lock file, stage the regenerated file, and commit the merge

#### Scenario: Sync failure does not block
- **WHEN** sync fails for a running worktree (e.g., real merge conflict in non-generated files)
- **THEN** the failure SHALL be logged but SHALL NOT affect the merge result or other syncs

#### Scenario: Already up-to-date worktree
- **WHEN** a running worktree is already up-to-date with main
- **THEN** sync SHALL return immediately without git operations
