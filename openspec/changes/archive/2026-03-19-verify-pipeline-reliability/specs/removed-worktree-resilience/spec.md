# Spec: removed-worktree-resilience

## ADDED Requirements

## IN SCOPE
- Detecting missing worktree directories before polling
- Auto-transitioning changes with missing worktrees to appropriate terminal status
- Preventing repeated poll failures on removed worktrees from escalating to sentinel shutdown

## OUT OF SCOPE
- Preventing worktree removal during active orchestration (that's a user/sentinel responsibility)
- Adding worktree recreation logic (manual merge = intentional removal)
- Changing the sentinel's clean-exit detection logic

### Requirement: Poll skips missing worktrees

The monitor's `_poll_active_changes` SHALL check that the worktree directory exists before calling `poll_change`. If the directory is missing, the change SHALL be auto-transitioned.

#### Scenario: Running change with missing worktree
- **WHEN** a change has status "running" and its `worktree_path` directory does not exist
- **THEN** the monitor SHALL set the change status to "merged" (assuming manual merge) and log a warning

#### Scenario: Verifying change with missing worktree
- **WHEN** a change has status "verifying" and its `worktree_path` directory does not exist
- **THEN** the monitor SHALL set the change status to "merged" and log a warning

### Requirement: Sync skips missing worktrees

Post-merge worktree sync operations SHALL skip worktrees that no longer exist on disk, without raising exceptions or triggering watchdog escalation.

#### Scenario: Post-merge sync target removed
- **WHEN** the post-merge sync iterates worktrees to update and a worktree directory is missing
- **THEN** the sync SHALL skip that worktree with a debug-level log message, not a warning or error
