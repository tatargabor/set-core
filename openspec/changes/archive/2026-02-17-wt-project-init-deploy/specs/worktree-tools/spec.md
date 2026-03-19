## MODIFIED Requirements

### Requirement: Project Management
The system SHALL manage multiple git projects through a central registry.

#### Scenario: Initialize current directory as project
- **WHEN** user runs `set-project init` inside a git repository
- **THEN** the repository is registered with its directory name as project name
- **AND** the project path is stored in `~/.config/set-core/projects.json`
- **AND** set-core hooks, commands, and skills are deployed to `<project>/.claude/`

#### Scenario: Initialize with custom name
- **WHEN** user runs `set-project init --name myproject` inside a git repository
- **THEN** the repository is registered with "myproject" as its name
- **AND** set-core hooks, commands, and skills are deployed to `<project>/.claude/`

#### Scenario: Init outside git repository
- **WHEN** user runs `set-project init` outside a git repository
- **THEN** an error is shown indicating the current directory is not a git repository

#### Scenario: Re-init already registered project
- **WHEN** user runs `set-project init` in an already-registered project
- **THEN** registration is skipped
- **AND** set-core hooks, commands, and skills are updated to the current version

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
