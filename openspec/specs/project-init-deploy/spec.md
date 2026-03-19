## MODIFIED Requirements

### Requirement: Deploy wt commands to project
When `set-project init` runs, it SHALL copy all files from the set-core repo's `.claude/commands/wt/` directory to `<project>/.claude/commands/wt/`, creating the directory if it does not exist. Existing files SHALL be overwritten.

#### Scenario: First init deploys commands
- **WHEN** `set-project init` is run in a project that has no `.claude/commands/wt/` directory
- **THEN** the directory is created and all `/wt:*` command files are copied from the set-core repo

#### Scenario: Re-init updates commands
- **WHEN** `set-project init` is run in a project that already has `.claude/commands/wt/` with older files
- **THEN** all files in `.claude/commands/wt/` are replaced with the current versions from the set-core repo

### Requirement: Deploy rules to project
When `set-project init` runs, it SHALL copy all files from the set-core repo's `.claude/rules/` directory to `<project>/.claude/rules/`, preserving subdirectory structure and creating directories as needed. Files SHALL be prefixed with `wt-` in target projects (unless deploying to the set-core repo itself) to avoid conflicts with project-specific rules. Existing wt-prefixed files SHALL be overwritten.

#### Scenario: First init deploys rules
- **WHEN** `set-project init` is run in a project that has no `.claude/rules/` directory
- **THEN** the directory is created and all rules files are copied with `wt-` prefix from the set-core repo

#### Scenario: Re-init updates rules without touching project rules
- **WHEN** `set-project init` is run in a project that has `.claude/rules/` with both `wt-*` and custom rules
- **THEN** only `wt-*` prefixed files SHALL be overwritten
- **AND** non-prefixed project-specific rules SHALL remain untouched

#### Scenario: Self-deploy skips prefix
- **WHEN** `set-project init` deploys to the set-core repo itself (source == destination)
- **THEN** rules files SHALL NOT be copied (self-deploy detected via realpath comparison)

### Requirement: Deploy agents to project
When `set-project init` runs, it SHALL copy all files from the set-core repo's `.claude/agents/` directory to `<project>/.claude/agents/`, creating the directory if it does not exist. Existing files with the same name SHALL be overwritten.

#### Scenario: First init deploys agents
- **WHEN** `set-project init` is run in a project that has no `.claude/agents/` directory
- **THEN** the directory is created and all agent definition files are copied from the set-core repo

#### Scenario: Re-init updates agents
- **WHEN** `set-project init` is run in a project that already has `.claude/agents/`
- **THEN** agent files from set-core SHALL be overwritten with current versions

### Requirement: Deploy hooks to project
When `set-project init` runs, it SHALL call `wt-deploy-hooks <project-path>` to deploy or update hooks in `<project>/.claude/settings.json`. The deployed hooks SHALL include the new SubagentStart and SessionStart[compact] hooks alongside existing memory hooks.

#### Scenario: New hooks deployed alongside existing
- **WHEN** `set-project init` is run after the modernization
- **THEN** `wt-deploy-hooks` SHALL deploy SubagentStart and SessionStart[compact] hooks in addition to all existing hooks

#### Scenario: Existing memory hooks unchanged
- **WHEN** `wt-deploy-hooks` runs on a project with existing memory hooks
- **THEN** all existing hook entries (UserPromptSubmit, PostToolUse, PostToolUseFailure, SubagentStop, Stop) SHALL remain unchanged

### Requirement: Post-init health summary
After deploying hooks, commands, and skills, `set-project init` SHALL run `wt-audit scan` and display a summary of project health.

#### Scenario: Init with gaps
- **WHEN** `set-project init` completes and audit finds ❌ or ⚠️ items
- **THEN** output shows the summary line (e.g., `Health: ✅ 10  ⚠️ 3  ❌ 2`) and suggests running `/wt:audit` to address gaps

#### Scenario: Init with clean health
- **WHEN** `set-project init` completes and audit finds all ✅
- **THEN** output shows `Health: ✅ all checks passed`

#### Scenario: Audit not available
- **WHEN** `wt-audit` is not in PATH (e.g., partial install)
- **THEN** `set-project init` skips the audit step without error

### Requirement: Scaffold wt directory structure
When `set-project init` runs, it SHALL create the `wt/` directory structure in the target project after deploying `.claude/` files.

#### Scenario: Scaffold on first init
- **WHEN** `set-project init` runs in a project without a `wt/` directory
- **THEN** the following directories are created:
  - `wt/orchestration/`
  - `wt/orchestration/runs/`
  - `wt/orchestration/plans/`
  - `wt/knowledge/`
  - `wt/knowledge/patterns/`
  - `wt/knowledge/lessons/`
  - `wt/requirements/`
  - `wt/plugins/`
  - `wt/.work/`
- **AND** `wt/.work/` is added to `.gitignore` if not already present

#### Scenario: Scaffold on re-init
- **WHEN** `set-project init` runs in a project that already has a `wt/` directory
- **THEN** only missing subdirectories are created
- **AND** existing files in `wt/` are not modified

#### Scenario: Legacy file detection
- **WHEN** `set-project init` runs and detects files in legacy locations
- **THEN** it prints a migration suggestion listing each legacy file and its new location
- **AND** it suggests running `set-project migrate`

#### Scenario: Deploy output includes wt directory status
- **WHEN** `set-project init` completes
- **THEN** the output includes a line confirming wt/ directory status (e.g., "Scaffolded wt/ directory structure")
