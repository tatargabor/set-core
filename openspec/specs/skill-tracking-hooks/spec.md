## ADDED Requirements

### Requirement: Stop hook refreshes skill timestamp
The system SHALL provide a Claude Code `Stop` hook script (`bin/set-hook-stop`) that refreshes the `.set-core/current_skill` timestamp after every agent response.

#### Scenario: Skill file exists and agent responds
- **WHEN** Claude finishes a response (Stop event fires)
- **AND** `.set-core/current_skill` exists in the current working directory
- **THEN** the timestamp portion of the file SHALL be updated to the current unix timestamp
- **AND** the skill name portion SHALL remain unchanged

#### Scenario: No skill file exists
- **WHEN** Claude finishes a response (Stop event fires)
- **AND** `.set-core/current_skill` does not exist
- **THEN** the hook SHALL exit 0 without creating the file

#### Scenario: Not in a set-managed directory
- **WHEN** the Stop hook fires in a directory without `.set-core/`
- **THEN** the hook SHALL exit 0 silently

#### Scenario: set-hook-stop not on PATH
- **WHEN** the `.claude/settings.json` references `set-hook-stop` but it is not installed
- **THEN** the hook SHALL fail silently (Claude Code handles missing commands gracefully)

### Requirement: All skills register via set-skill-start
Every Claude Code skill SKILL.md in `.claude/skills/` SHALL call `set-skill-start <skill-name>` at the beginning of its execution.

#### Scenario: opsx skill registers itself
- **WHEN** an opsx skill (e.g., `opsx:apply`, `opsx:explore`) starts
- **THEN** it SHALL run `set-skill-start <skill-name>` before any other action
- **AND** `.set-core/current_skill` SHALL contain the skill name and current timestamp

#### Scenario: wt skill registers itself
- **WHEN** the `wt` skill starts
- **THEN** it SHALL run `set-skill-start wt` (already implemented)

### Requirement: Project hook deployment via install
The `install.sh` script SHALL deploy Claude Code hooks to all registered projects using the `set-deploy-hooks` script.

#### Scenario: Fresh install with registered projects
- **WHEN** user runs `install.sh`
- **AND** `projects.json` contains registered projects
- **THEN** `set-deploy-hooks` SHALL be called for each project's main repo path

#### Scenario: Project already has settings.json
- **WHEN** a project already has `.claude/settings.json` with other settings
- **THEN** `set-deploy-hooks` SHALL merge hooks without overwriting existing settings
- **AND** a backup SHALL be created before modification

#### Scenario: No registered projects
- **WHEN** user runs `install.sh`
- **AND** `projects.json` does not exist or has no projects
- **THEN** `install_project_hooks()` SHALL skip gracefully with an info message

### Requirement: Hook deployment on set-add
The `set-add` command SHALL deploy Claude Code hooks when registering a new project using the `set-deploy-hooks` script.

#### Scenario: Add new project deploys hooks
- **WHEN** user runs `set-add /path/to/repo`
- **AND** the repository is successfully registered
- **THEN** `set-deploy-hooks` SHALL be called on the project root

#### Scenario: Add worktree to existing project
- **WHEN** user runs `set-add` for a worktree whose main repo already has hooks deployed
- **THEN** no duplicate hook deployment SHALL occur for the main repo
