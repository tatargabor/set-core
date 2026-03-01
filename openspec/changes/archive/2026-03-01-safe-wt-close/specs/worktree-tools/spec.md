## MODIFIED Requirements

### Requirement: Worktree Removal
The system SHALL remove a worktree and optionally its branch, with safety checks that cannot be bypassed.

#### Scenario: Remove worktree interactively
- **WHEN** user runs `wt-close <change-id>`
- **THEN** the worktree is removed
- **AND** user is prompted whether to keep or delete the branch

#### Scenario: Uncommitted changes block removal
- **WHEN** user runs `wt-close <change-id>` and the worktree has uncommitted changes
- **THEN** the command SHALL fail with an error showing the uncommitted changes
- **AND** the worktree SHALL NOT be removed

#### Scenario: Non-interactive close keeping branch
- **WHEN** user runs `wt-close <change-id> --keep-branch`
- **THEN** the worktree is removed
- **AND** the branch is kept (can be reopened with wt-work)
- **AND** no interactive prompts are shown

#### Scenario: Non-interactive close deleting safe branch
- **WHEN** user runs `wt-close <change-id> --delete-branch`
- **AND** the branch has no commits that are absent from both master and remote
- **THEN** the worktree is removed
- **AND** the branch is deleted

#### Scenario: Non-interactive close deleting unsafe branch
- **WHEN** user runs `wt-close <change-id> --delete-branch`
- **AND** the branch has commits not in master AND not pushed to remote
- **THEN** the command SHALL fail with an error listing the unprotected commits
- **AND** the worktree SHALL NOT be removed

#### Scenario: Interactive delete with unmerged commits warning
- **WHEN** user runs `wt-close <change-id>` interactively and chooses to delete the branch
- **AND** the branch has commits not in master and not pushed to remote
- **THEN** a warning SHALL be shown with the number of commits that will be lost
- **AND** user MUST confirm with explicit "yes" to proceed
- **AND** if user declines, the branch is kept

#### Scenario: Delete remote branch
- **WHEN** user runs `wt-close <change-id> --delete-remote` (with interactive delete or `--delete-branch`)
- **AND** the branch exists on remote
- **THEN** the remote branch is also deleted

## REMOVED Requirements

### Requirement: Remove with force
**Reason**: The `--force` flag bypasses safety checks and leads to silent code loss, especially when used by agents and GUI.
**Migration**: Use `--keep-branch` for safe non-interactive close, or `--delete-branch` for non-interactive branch deletion (only succeeds if no code loss).
