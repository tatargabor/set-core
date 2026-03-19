# orchestrate-reset-cli Specification

## Purpose
Dedicated CLI tool for safe orchestration state reset, replacing inline reset snippets that were previously in sentinel/E2E documentation.

## IN SCOPE
- Partial reset: failed changes back to pending (safe default)
- Full reset: all changes to pending + clean worktrees (destructive, requires explicit flag)
- Backup before destructive operations
- Dry-run for full reset

## OUT OF SCOPE
- Resetting individual changes by name (future enhancement)
- Remote state reset (only local state files)

### Requirement: partial-reset-safe-default
`set-orchestrate reset` and `set-orchestrate reset --partial` SHALL reset only failed changes to pending, preserving merged/done changes.

#### Scenario: Partial reset of failed changes
- **WHEN** user runs `set-orchestrate reset` or `set-orchestrate reset --partial`
- **THEN** the tool SHALL set status to "pending", clear worktree_path, ralph_pid, and verify_retry_count for all changes with status "failed", set overall status to "running", and print a summary of what was reset

#### Scenario: No failed changes
- **WHEN** user runs `set-orchestrate reset --partial` and no changes have status "failed"
- **THEN** the tool SHALL print "Nothing to reset — no failed changes found" and exit 0

### Requirement: full-reset-requires-confirmation
`set-orchestrate reset --full` SHALL require `--yes-i-know` flag and create a backup before executing.

#### Scenario: Full reset without confirmation flag
- **WHEN** user runs `set-orchestrate reset --full` without `--yes-i-know`
- **THEN** the tool SHALL print what would be destroyed (number of changes, worktrees, events) and exit without making changes

#### Scenario: Full reset with confirmation
- **WHEN** user runs `set-orchestrate reset --full --yes-i-know`
- **THEN** the tool SHALL:
  1. Create backup at `orchestration-state.backup.json`
  2. Remove all non-main worktrees
  3. Reset all changes to pending with cleared fields
  4. Clear events log
  5. Set overall status to "running"
  6. Print summary of everything that was reset

#### Scenario: Backup exists
- **WHEN** `orchestration-state.backup.json` already exists during full reset
- **THEN** the tool SHALL overwrite the backup (latest backup wins) and print a warning

### Requirement: sentinel-no-longer-resets-state
The sentinel skill documentation SHALL NOT contain state reset code or instructions. Reset operations are delegated to `set-orchestrate reset`.

#### Scenario: Sentinel encounters unrecoverable state
- **WHEN** sentinel detects a state that requires reset (e.g., too many failed changes)
- **THEN** sentinel SHALL stop and report to the user with the command to run: `set-orchestrate reset --partial`
