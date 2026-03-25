# version-info Specification

## Purpose
TBD - created by archiving change add-version-command. Update Purpose after archive.
## Requirements
### Requirement: Version Command
The system SHALL provide a `set-version` command that displays installed version information.

#### Scenario: Display version info
Given set-core is installed via symlinks
When the user runs `set-version`
Then the output shows:
  - set-core version header
  - Branch name (e.g., "main")
  - Commit hash (short, 7 chars)
  - Commit date (ISO format)
  - Source directory path

#### Scenario: JSON output
Given set-core is installed
When the user runs `set-version --json`
Then the output is valid JSON with fields: branch, commit, date, source_dir

#### Scenario: Source not found
Given set-version script symlink is broken
When the user runs `set-version`
Then an error message explains the source directory was not found

### Requirement: Install Script Update
The install.sh MUST include set-version in the list of installed scripts.

#### Scenario: Fresh install includes set-version
Given a fresh install
When install.sh completes
Then set-version is symlinked to ~/.local/bin/

