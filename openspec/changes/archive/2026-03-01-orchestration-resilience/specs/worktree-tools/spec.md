## MODIFIED Requirements

### Requirement: Worktree Creation
The system SHALL create a git worktree for a specified change-id in a standardized location.

#### Scenario: Create worktree for new change
- **WHEN** user runs `wt-open <change-id>` (uses default project or current directory)
- **THEN** a new git worktree is created at `../<repo-name>-wt-<change-id>`
- **AND** a new branch `change/<change-id>` is created if it doesn't exist
- **AND** `.env` and `.env.local` are copied from the main repository if they exist
- **AND** `openspec init` is called in the new worktree if openspec is not initialized
- **AND** the worktree path is printed to stdout

#### Scenario: Env file bootstrap from main repo
- **WHEN** a new worktree is created
- **AND** the main repository contains `.env` or `.env.local` files
- **THEN** those files SHALL be copied to the worktree root
- **AND** the copy SHALL happen BEFORE dependency installation (since install scripts may read env vars)
- **AND** existing `.env` files in the worktree SHALL NOT be overwritten

#### Scenario: Env file bootstrap with no env files
- **WHEN** a new worktree is created
- **AND** the main repository does NOT contain `.env` or `.env.local`
- **THEN** no env files are copied
- **AND** no warning or error is emitted

#### Scenario: Worktree already exists
- **WHEN** user runs `wt-open <change-id>` and worktree already exists
- **THEN** the existing worktree path is printed
- **AND** no error is raised

#### Scenario: Invalid change-id
- **WHEN** user runs `wt-open` without change-id
- **THEN** an error message is displayed with usage instructions
