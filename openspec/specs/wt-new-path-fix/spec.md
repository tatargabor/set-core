# Wt New Path Fix Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: GUI set-new command resolution
The GUI SHALL invoke `set-new` using its full filesystem path via `SCRIPT_DIR`, not via bare command name PATH lookup.

#### Scenario: Create worktree from GUI with project flag
- **WHEN** user creates a new worktree via the GUI's "New Worktree" dialog for a registered project
- **THEN** the system SHALL invoke `set-new` using the full path `SCRIPT_DIR / "set-new"` with `-p <project> <change-id>` arguments
- **AND** the command SHALL succeed regardless of whether `~/.local/bin` is in the process's PATH

#### Scenario: Create worktree from GUI for local repo
- **WHEN** user creates a new worktree via the GUI from a local (non-registered) repository path
- **THEN** the system SHALL invoke `set-new` using the full path `SCRIPT_DIR / "set-new"` with `<change-id>` argument
- **AND** the working directory SHALL be set to the local repository path

#### Scenario: Consistency with other set-* commands
- **WHEN** any set-* command is invoked from the GUI
- **THEN** all commands SHALL use the same `SCRIPT_DIR`-based path resolution pattern

### Requirement: Test coverage for create_worktree handler
The test suite SHALL include tests that verify the `create_worktree()` handler constructs commands with correct paths.

#### Scenario: Test verifies full path usage
- **WHEN** automated tests run for the worktree creation handler
- **THEN** the test SHALL verify that `set-new` is invoked with its full `SCRIPT_DIR`-based path
- **AND** the test SHALL NOT rely on `set-new` being available via PATH
