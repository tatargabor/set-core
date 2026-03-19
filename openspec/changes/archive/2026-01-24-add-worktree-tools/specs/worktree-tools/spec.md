## ADDED Requirements

### Requirement: Project Management
The system SHALL manage multiple git projects through a central registry.

#### Scenario: Initialize current directory as project
- **WHEN** user runs `set-project init` inside a git repository
- **THEN** the repository is registered with its directory name as project name
- **AND** the project path is stored in `~/.config/set-core/projects.json`

#### Scenario: Initialize with custom name
- **WHEN** user runs `set-project init --name myproject` inside a git repository
- **THEN** the repository is registered with "myproject" as its name

#### Scenario: Init outside git repository
- **WHEN** user runs `set-project init` outside a git repository
- **THEN** an error is shown indicating the current directory is not a git repository

#### Scenario: List registered projects
- **WHEN** user runs `set-project list`
- **THEN** all registered projects are displayed with name and path
- **AND** the default project is marked

#### Scenario: Remove project from registry
- **WHEN** user runs `set-project remove myproject`
- **THEN** the project is removed from the registry
- **AND** existing worktrees are NOT deleted

#### Scenario: Set default project
- **WHEN** user runs `set-project default myproject`
- **THEN** "myproject" becomes the default for other wt-* commands

### Requirement: Worktree Creation
The system SHALL create a git worktree for a specified change-id in a standardized location.

#### Scenario: Create worktree for new change
- **WHEN** user runs `wt-open <change-id>` (uses default project or current directory)
- **THEN** a new git worktree is created at `../<repo-name>-wt-<change-id>`
- **AND** a new branch `change/<change-id>` is created if it doesn't exist
- **AND** `openspec init` is called in the new worktree if openspec is not initialized
- **AND** the worktree path is printed to stdout

#### Scenario: Create worktree for specific project
- **WHEN** user runs `wt-open <change-id> -p <project-name>`
- **THEN** a worktree is created for the specified registered project

#### Scenario: Worktree already exists
- **WHEN** user runs `wt-open <change-id>` and worktree already exists
- **THEN** the existing worktree path is printed
- **AND** no error is raised

#### Scenario: Invalid change-id
- **WHEN** user runs `wt-open` without change-id
- **THEN** an error message is displayed with usage instructions

### Requirement: Editor Integration
The system SHALL open the Zed editor for a specified worktree.

#### Scenario: Open Zed for worktree
- **WHEN** user runs `wt-edit <change-id>`
- **THEN** Zed editor opens with the worktree directory
- **AND** if worktree doesn't exist, it is created first

#### Scenario: Zed not installed
- **WHEN** user runs `wt-edit` and Zed is not found
- **THEN** an informative error message is displayed with installation instructions

### Requirement: Worktree Listing
The system SHALL list all active worktrees for projects.

#### Scenario: List worktrees for default project
- **WHEN** user runs `wt-list`
- **THEN** all worktrees for the default project are listed
- **AND** each entry shows the change-id and path

#### Scenario: List all worktrees across projects
- **WHEN** user runs `wt-list --all`
- **THEN** all worktrees for all registered projects are listed
- **AND** each entry shows the project name, change-id and path

#### Scenario: List worktrees for specific project
- **WHEN** user runs `wt-list -p <project-name>`
- **THEN** worktrees for the specified project are listed

#### Scenario: No worktrees exist
- **WHEN** user runs `wt-list` and no worktrees exist
- **THEN** an informative message is displayed

### Requirement: Worktree Removal
The system SHALL remove a worktree and optionally its branch.

#### Scenario: Remove worktree
- **WHEN** user runs `wt-close <change-id>`
- **THEN** the worktree is removed
- **AND** user is prompted whether to delete the branch

#### Scenario: Remove with force
- **WHEN** user runs `wt-close <change-id> --force`
- **THEN** the worktree and branch are removed without prompts

### Requirement: Installation
The system SHALL provide installation scripts for all supported platforms that install all necessary dependencies.

#### Scenario: Install on Linux/macOS
- **WHEN** user runs `./install.sh`
- **THEN** tool scripts are symlinked to `~/.local/bin/`
- **AND** Claude Code CLI is installed via npm if not present
- **AND** OpenSpec CLI is installed if not present
- **AND** Zed editor installation is offered if not present
- **AND** user is informed if PATH update is needed

#### Scenario: Install on Windows
- **WHEN** user runs `install.ps1` in PowerShell
- **THEN** tool scripts are added to user PATH
- **AND** Claude Code CLI is installed via npm if not present
- **AND** OpenSpec CLI is installed if not present
- **AND** Zed editor installation is offered if not present

#### Scenario: Skip already installed dependencies
- **WHEN** a dependency is already installed
- **THEN** installation is skipped for that dependency
- **AND** user is informed of current version

### Requirement: Cross-Platform Support
The system SHALL work on Linux, macOS, and Windows.

#### Scenario: Platform detection
- **WHEN** any tool script is executed
- **THEN** the current platform is detected
- **AND** platform-specific paths and commands are used

#### Scenario: Windows Git Bash
- **WHEN** tools are used from Git Bash on Windows
- **THEN** POSIX shell scripts work correctly
