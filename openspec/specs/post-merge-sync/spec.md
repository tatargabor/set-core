## ADDED Requirements

### Requirement: Running worktrees sync with main after each merge
After a successful merge, the orchestrator SHALL sync all running worktrees with the updated main branch.

#### Scenario: Successful merge triggers sync
- **WHEN** `merge_change()` completes successfully for change A AND changes B and C have status "running"
- **THEN** `sync_worktree_with_main` SHALL be called for both B and C

#### Scenario: Sync failure does not block
- **WHEN** sync fails for a running worktree (e.g., real merge conflict)
- **THEN** the failure SHALL be logged but SHALL NOT affect the merge result or other syncs

#### Scenario: Already up-to-date worktree
- **WHEN** a running worktree is already up-to-date with main
- **THEN** sync SHALL return immediately without git operations (existing behavior of sync_worktree_with_main)
