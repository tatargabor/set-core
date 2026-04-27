# Merge Branch Resolution

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Fixing set-merge --ff-only branch name resolution in worktree context
- Ensuring the source branch ref is accessible from the main repo before merge

### Out of scope
- Changing the overall merge strategy (integrate-then-verify-then-ff)
- Adding remote push/fetch for worktree branches

## Requirements

### Requirement: FF-only merge resolves worktree branch correctly
The `set-merge` script SHALL ensure the source branch (e.g., `change/subscriptions`) is resolvable from the main repo before attempting `git merge --ff-only`. Since worktree branches are shared across the main repo and its worktrees, the branch ref should already exist — but the script MUST verify this and provide a clear error if not.

#### Scenario: FF-only merge succeeds for worktree branch
- **WHEN** `set-merge <change> --ff-only` is called AND the worktree branch is ahead of main with a clean merge-base
- **THEN** the merge succeeds with exit code 0

#### Scenario: Diagnostic output on ff-only failure
- **WHEN** `git merge --ff-only` fails in the set-merge script
- **THEN** the script logs the merge-base, HEAD, and source branch HEAD for diagnostics (not hidden by `2>/dev/null`)
