# Uncommitted Work Guard Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Detect uncommitted work in worktree
The system SHALL provide a function `git_has_uncommitted_work(wt_path)` that returns a tuple of `(has_work: bool, summary: str)`. It SHALL run `git -C <wt_path> status --porcelain` with a 10-second timeout. If the output is non-empty, `has_work` SHALL be True and `summary` SHALL contain a human-readable description (e.g., "3 modified, 2 untracked"). If the output is empty, `has_work` SHALL be False and `summary` SHALL be empty string.

#### Scenario: Worktree has modified tracked files
- **WHEN** `git status --porcelain` outputs lines starting with ` M` or `M `
- **THEN** `has_work` SHALL be True and `summary` SHALL include the count of modified files

#### Scenario: Worktree has untracked files
- **WHEN** `git status --porcelain` outputs lines starting with `??`
- **THEN** `has_work` SHALL be True and `summary` SHALL include the count of untracked files

#### Scenario: Worktree is clean
- **WHEN** `git status --porcelain` outputs nothing
- **THEN** `has_work` SHALL be False and `summary` SHALL be empty string

#### Scenario: Git command times out
- **WHEN** `git status --porcelain` does not complete within 10 seconds
- **THEN** `has_work` SHALL be False (fail-open — do not block on git timeout)

#### Scenario: Git command fails
- **WHEN** `git status --porcelain` exits with non-zero code
- **THEN** `has_work` SHALL be False (fail-open — do not block on git errors)
