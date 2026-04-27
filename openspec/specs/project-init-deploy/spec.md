# Project Init Deploy Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Deploy wt commands to project
When `set-project init` runs, it SHALL copy all files from the set-core repo's `.claude/commands/wt/` directory to `<project>/.claude/commands/wt/`, creating the directory if it does not exist. Existing files SHALL be overwritten.

#### Scenario: First init deploys commands
- **WHEN** `set-project init` is run in a project that has no `.claude/commands/wt/` directory
- **THEN** the directory is created and all `/wt:*` command files are copied from the set-core repo

#### Scenario: Re-init updates commands
- **WHEN** `set-project init` is run in a project that already has `.claude/commands/wt/` with older files
- **THEN** all files in `.claude/commands/wt/` are replaced with the current versions from the set-core repo

### Requirement: Deploy rules to project
When `set-project init` runs, it SHALL copy rule files from `templates/core/rules/` in the set-core repo to `<project>/.claude/rules/`, prefixing each filename with `set-`. The source directory is `templates/core/rules/`, NOT `.claude/rules/`. All `.md` files in `templates/core/rules/` SHALL be deployed, including `project-guide.md` (deployed as `set-project-guide.md`). Existing `set-`prefixed files SHALL be overwritten. Non-prefixed project-specific rules SHALL remain untouched.

The set-core repo's own `.claude/rules/` directory SHALL NOT be used as a deploy source. It is reserved for set-core's own development rules.

#### Scenario: First init deploys core rules from templates
- **WHEN** `set-project init` is run in a project that has no `.claude/rules/` directory
- **THEN** the directory is created and all `.md` files from `templates/core/rules/` are copied with `set-` prefix

#### Scenario: Re-init updates rules without touching project rules
- **WHEN** `set-project init` is run in a project that has `.claude/rules/` with both `set-*` and custom rules
- **THEN** only `set-*` prefixed files matching files in `templates/core/rules/` SHALL be overwritten
- **AND** non-prefixed project-specific rules SHALL remain untouched

#### Scenario: Self-deploy skips rules
- **WHEN** `set-project init` deploys to the set-core repo itself (source == destination)
- **THEN** rules files SHALL NOT be copied (self-deploy detected via realpath comparison)

#### Scenario: Only template core rules are deployed
- **WHEN** `set-project init` runs and `.claude/rules/` contains files not present in `templates/core/rules/`
- **THEN** those extra files (e.g., `modular-architecture.md`, `openspec-artifacts.md`) SHALL NOT be deployed to consumer projects

### Requirement: Deploy agents to project
When `set-project init` runs, it SHALL copy all files from the set-core repo's `.claude/agents/` directory to `<project>/.claude/agents/`, creating the directory if it does not exist. Existing files with the same name SHALL be overwritten.

#### Scenario: First init deploys agents
- **WHEN** `set-project init` is run in a project that has no `.claude/agents/` directory
- **THEN** the directory is created and all agent definition files are copied from the set-core repo

#### Scenario: Re-init updates agents
- **WHEN** `set-project init` is run in a project that already has `.claude/agents/`
- **THEN** agent files from set-core SHALL be overwritten with current versions

### Requirement: Deploy hooks to project
When `set-project init` runs, it SHALL call `set-deploy-hooks <project-path>` to deploy or update hooks in `<project>/.claude/settings.json`. The deployed hooks SHALL include the new SubagentStart and SessionStart[compact] hooks alongside existing memory hooks.

#### Scenario: New hooks deployed alongside existing
- **WHEN** `set-project init` is run after the modernization
- **THEN** `set-deploy-hooks` SHALL deploy SubagentStart and SessionStart[compact] hooks in addition to all existing hooks

#### Scenario: Existing memory hooks unchanged
- **WHEN** `set-deploy-hooks` runs on a project with existing memory hooks
- **THEN** all existing hook entries (UserPromptSubmit, PostToolUse, PostToolUseFailure, SubagentStop, Stop) SHALL remain unchanged

### Requirement: Post-init health summary
After deploying hooks, commands, and skills, `set-project init` SHALL run `set-audit scan` and display a summary of project health.

#### Scenario: Init with gaps
- **WHEN** `set-project init` completes and audit finds items with issues
- **THEN** output shows the summary line and suggests running `/set:audit` to address gaps

#### Scenario: Init with clean health
- **WHEN** `set-project init` completes and audit finds all passing
- **THEN** output shows all checks passed

#### Scenario: Audit not available
- **WHEN** `set-audit` is not in PATH (e.g., partial install)
- **THEN** `set-project init` skips the audit step without error

### Requirement: Scaffold set directory structure
When `set-project init` runs, it SHALL create the `set/` directory structure in the target project after deploying `.claude/` files.

#### Scenario: Scaffold on first init
- **WHEN** `set-project init` runs in a project without a `set/` directory
- **THEN** the following directories are created:
  - `set/orchestration/`
  - `set/knowledge/`
  - `set/knowledge/patterns/`
  - `set/knowledge/lessons/`
  - `set/plugins/`
  - `set/.work/`
- **AND** `set/.work/` is added to `.gitignore` if not already present

#### Scenario: Scaffold on re-init
- **WHEN** `set-project init` runs in a project that already has a `set/` directory
- **THEN** only missing subdirectories are created
- **AND** existing files in `set/` are not modified

### Requirement: Template file deployment respects protection
When `set-project init` deploys template files during re-init, files annotated as `protected` in the manifest SHALL be skipped if modified by the project. Files annotated as `merge` SHALL use additive YAML merge.

#### Scenario: Re-init preserves modified scaffold files
- **WHEN** `set-project init` re-initializes a project
- **AND** a file is marked `protected: true` in the manifest
- **AND** the project's file differs from the template
- **THEN** the file SHALL NOT be overwritten
- **AND** the output SHALL show `Skipped (protected): <path>`

#### Scenario: Re-init merges config additively
- **WHEN** `set-project init` re-initializes a project
- **AND** a config file is marked `merge: true` in the manifest
- **THEN** new keys from the template SHALL be added to the existing config
- **AND** existing keys SHALL NOT be modified

#### Scenario: First init deploys all files normally
- **WHEN** `set-project init` runs on a fresh project with no existing files
- **THEN** all template files SHALL be deployed regardless of protection or merge flags
