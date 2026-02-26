## MODIFIED Requirements

### Requirement: Deploy wt commands to project
When `wt-project init` runs, it SHALL copy all files from the wt-tools repo's `.claude/commands/wt/` directory to `<project>/.claude/commands/wt/`, creating the directory if it does not exist. Existing files SHALL be overwritten.

#### Scenario: First init deploys commands
- **WHEN** `wt-project init` is run in a project that has no `.claude/commands/wt/` directory
- **THEN** the directory is created and all `/wt:*` command files are copied from the wt-tools repo

#### Scenario: Re-init updates commands
- **WHEN** `wt-project init` is run in a project that already has `.claude/commands/wt/` with older files
- **THEN** all files in `.claude/commands/wt/` are replaced with the current versions from the wt-tools repo

### Requirement: Deploy rules to project
When `wt-project init` runs, it SHALL copy all files from the wt-tools repo's `.claude/rules/` directory to `<project>/.claude/rules/`, preserving subdirectory structure and creating directories as needed. Files SHALL be prefixed with `wt-` in target projects (unless deploying to the wt-tools repo itself) to avoid conflicts with project-specific rules. Existing wt-prefixed files SHALL be overwritten.

#### Scenario: First init deploys rules
- **WHEN** `wt-project init` is run in a project that has no `.claude/rules/` directory
- **THEN** the directory is created and all rules files are copied with `wt-` prefix from the wt-tools repo

#### Scenario: Re-init updates rules without touching project rules
- **WHEN** `wt-project init` is run in a project that has `.claude/rules/` with both `wt-*` and custom rules
- **THEN** only `wt-*` prefixed files SHALL be overwritten
- **AND** non-prefixed project-specific rules SHALL remain untouched

#### Scenario: Self-deploy skips prefix
- **WHEN** `wt-project init` deploys to the wt-tools repo itself (source == destination)
- **THEN** rules files SHALL NOT be copied (self-deploy detected via realpath comparison)

### Requirement: Deploy agents to project
When `wt-project init` runs, it SHALL copy all files from the wt-tools repo's `.claude/agents/` directory to `<project>/.claude/agents/`, creating the directory if it does not exist. Existing files with the same name SHALL be overwritten.

#### Scenario: First init deploys agents
- **WHEN** `wt-project init` is run in a project that has no `.claude/agents/` directory
- **THEN** the directory is created and all agent definition files are copied from the wt-tools repo

#### Scenario: Re-init updates agents
- **WHEN** `wt-project init` is run in a project that already has `.claude/agents/`
- **THEN** agent files from wt-tools SHALL be overwritten with current versions

### Requirement: Deploy hooks to project
When `wt-project init` runs, it SHALL call `wt-deploy-hooks <project-path>` to deploy or update hooks in `<project>/.claude/settings.json`. The deployed hooks SHALL include the new SubagentStart and SessionStart[compact] hooks alongside existing memory hooks.

#### Scenario: New hooks deployed alongside existing
- **WHEN** `wt-project init` is run after the modernization
- **THEN** `wt-deploy-hooks` SHALL deploy SubagentStart and SessionStart[compact] hooks in addition to all existing hooks

#### Scenario: Existing memory hooks unchanged
- **WHEN** `wt-deploy-hooks` runs on a project with existing memory hooks
- **THEN** all existing hook entries (UserPromptSubmit, PostToolUse, PostToolUseFailure, SubagentStop, Stop) SHALL remain unchanged
