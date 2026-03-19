## ADDED Requirements

### Requirement: Deploy wt commands to project
When `set-project init` runs, it SHALL copy all files from the set-core repo's `.claude/commands/wt/` directory to `<project>/.claude/commands/wt/`, creating the directory if it does not exist. Existing files SHALL be overwritten.

#### Scenario: First init deploys commands
- **WHEN** `set-project init` is run in a project that has no `.claude/commands/wt/` directory
- **THEN** the directory is created and all `/wt:*` command files are copied from the set-core repo

#### Scenario: Re-init updates commands
- **WHEN** `set-project init` is run in a project that already has `.claude/commands/wt/` with older files
- **THEN** all files in `.claude/commands/wt/` are replaced with the current versions from the set-core repo

### Requirement: Deploy wt skills to project
When `set-project init` runs, it SHALL copy all files from the set-core repo's `.claude/skills/wt/` directory to `<project>/.claude/skills/wt/`, creating the directory if it does not exist. Existing files SHALL be overwritten.

#### Scenario: First init deploys skills
- **WHEN** `set-project init` is run in a project that has no `.claude/skills/wt/` directory
- **THEN** the directory is created and all wt skill files are copied from the set-core repo

#### Scenario: Re-init updates skills
- **WHEN** `set-project init` is run in a project that already has `.claude/skills/wt/`
- **THEN** skill files are replaced with the current versions

### Requirement: Deploy hooks to project
When `set-project init` runs, it SHALL call `wt-deploy-hooks <project-path>` to deploy or update hooks in `<project>/.claude/settings.json`.

#### Scenario: First init deploys hooks
- **WHEN** `set-project init` is run in a project that has no `.claude/settings.json`
- **THEN** `settings.json` is created with the standard set-core hooks

#### Scenario: Re-init updates hooks
- **WHEN** `set-project init` is run in a project that already has `.claude/settings.json`
- **THEN** `wt-deploy-hooks` adds any missing hooks (idempotent)

### Requirement: Source resolution from script location
The set-core repo path SHALL be resolved from the `set-project` script's own location (`BASH_SOURCE[0]`), traversing symlinks. This ensures the deployed files come from the same set-core version as the running script.

#### Scenario: Running from set-core worktree
- **WHEN** `set-project init` is invoked via a symlink in `~/.local/bin/` pointing to a specific set-core worktree
- **THEN** the deployed commands and skills come from that worktree's `.claude/` directory

### Requirement: install.sh removes global symlinks
`install.sh`'s `install_skills()` function SHALL NOT create global symlinks at `~/.claude/commands/wt` or `~/.claude/skills/wt`. Instead, `install.sh` SHALL call `set-project init` for each project registered in `projects.json`.

#### Scenario: Fresh install deploys to all registered projects
- **WHEN** `install.sh` runs with 3 projects registered in `projects.json`
- **THEN** `set-project init` is called for each project, deploying hooks, commands, and skills

#### Scenario: No global wt symlinks created
- **WHEN** `install.sh` completes
- **THEN** `~/.claude/commands/wt` and `~/.claude/skills/wt` are NOT created as symlinks
