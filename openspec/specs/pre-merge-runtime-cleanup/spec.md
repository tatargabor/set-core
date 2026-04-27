# Pre Merge Runtime Cleanup Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Pre-merge runtime file removal from git index
Before merging a worktree branch, the system SHALL remove `.set-core/` runtime files from the git index to prevent them from causing merge conflicts.

#### Scenario: Runtime files removed from index before merge
- **WHEN** a merge is initiated and the worktree branch has `.set-core/` runtime files tracked in git (`.last-memory-commit`, `agents/`, `orphan-detect/`)
- **THEN** the system SHALL run `git rm --cached` on those files and commit the cleanup before attempting the merge

#### Scenario: No runtime files tracked
- **WHEN** a merge is initiated and no `.set-core/` runtime files are tracked in git
- **THEN** the cleanup step SHALL be a no-op and the merge SHALL proceed normally

#### Scenario: Cleanup applies to specific runtime patterns only
- **WHEN** the pre-merge cleanup runs
- **THEN** it SHALL only target known runtime file patterns (`.set-core/.last-memory-commit`, `.set-core/agents/**`, `.set-core/orphan-detect/**`) and SHALL NOT remove other `.set-core/` files (e.g., configuration files)

### Requirement: Runtime files added to .gitignore
The system SHALL ensure `.set-core/` runtime file patterns are present in the project's `.gitignore` to prevent re-tracking after cleanup.

#### Scenario: Patterns added to .gitignore
- **WHEN** the pre-merge cleanup removes runtime files from the index
- **THEN** the system SHALL verify that `.set-core/.last-memory-commit`, `.set-core/agents/`, and `.set-core/orphan-detect/` patterns exist in `.gitignore`, adding them if missing

#### Scenario: Patterns already in .gitignore
- **WHEN** the runtime file patterns are already present in `.gitignore`
- **THEN** the system SHALL not add duplicate entries
