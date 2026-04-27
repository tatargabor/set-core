# Wt Directory Structure Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: wt directory exists in consumer projects
Every consumer project using set-core SHALL have a `wt/` directory at the project root. This directory is the canonical location for all set-core project-specific artifacts.

#### Scenario: New project initialization
- **WHEN** `set-project init` runs in a project without a `wt/` directory
- **THEN** the `wt/` directory structure is created with all subdirectories

#### Scenario: Existing project re-init
- **WHEN** `set-project init` runs in a project that already has a `wt/` directory
- **THEN** missing subdirectories are created without modifying existing files

### Requirement: Orchestration subdirectory
The `set/orchestration/` directory SHALL contain all orchestration-related artifacts: configuration, run logs, and saved plans.

#### Scenario: Config file location
- **WHEN** the orchestrator looks for orchestration directives
- **THEN** it checks `set/orchestration/config.yaml` first, then falls back to `.claude/orchestration.yaml`

#### Scenario: Run logs location
- **WHEN** the orchestrator writes a run log
- **THEN** the log is saved to `set/orchestration/runs/` with the existing markdown format

#### Scenario: Plan history
- **WHEN** the planner creates a new orchestration plan
- **THEN** the plan JSON is saved to `set/orchestration/plans/plan-v{N}-{YYYY-MM-DD}.json` in addition to the working `orchestration-plan.json`

### Requirement: Knowledge subdirectory
The `set/knowledge/` directory SHALL contain project knowledge artifacts used by agents during execution.

#### Scenario: Project knowledge location
- **WHEN** the planner, dispatcher, or verifier looks for project-knowledge.yaml
- **THEN** it checks `set/knowledge/project-knowledge.yaml` first, then falls back to `./project-knowledge.yaml`

#### Scenario: Patterns subdirectory
- **WHEN** a project has reusable code patterns (CRUD templates, API endpoint patterns)
- **THEN** they are stored as markdown files in `set/knowledge/patterns/`

#### Scenario: Lessons subdirectory
- **WHEN** orchestration runs produce learnings (from run log conclusions)
- **THEN** extracted lessons are stored in `set/knowledge/lessons/`

### Requirement: Requirements subdirectory
The `wt/requirements/` directory SHALL contain business requirement YAML files that serve as input for spec generation and planning.

#### Scenario: Requirements directory exists
- **WHEN** `set-project init` completes
- **THEN** `wt/requirements/` directory exists and is ready for requirement files

#### Scenario: Requirements are discoverable
- **WHEN** the planner generates a plan
- **THEN** it can scan `wt/requirements/*.yaml` for business requirements to inform decomposition

### Requirement: Plugins subdirectory
The `set/plugins/` directory SHALL provide a workspace for each installed set-core plugin, where plugins can store their data, state, and generated artifacts.

#### Scenario: Plugin workspace created on plugin init
- **WHEN** a plugin is installed or initialized (e.g., `set-project add-plugin set-spec-capture`)
- **THEN** `set/plugins/<plugin-name>/` directory is created
- **AND** the plugin can define its own internal directory structure within its workspace

#### Scenario: Plugin workspace isolation
- **WHEN** multiple plugins are installed (e.g., set-web and set-spec-capture)
- **THEN** each plugin has its own isolated directory under `set/plugins/`
- **AND** plugins do not write to each other's workspace

#### Scenario: Chrome extension workspace example
- **WHEN** set-spec-capture plugin is installed
- **THEN** it uses `set/plugins/set-spec-capture/` for scraped site data, generated drafts, and plugin config

#### Scenario: Plugin workspace without plugin system
- **WHEN** `set/plugins/` exists but no formal plugin system is implemented yet
- **THEN** plugins can manually create their workspace directory and use it independently

### Requirement: Gitignored work directory
The `set/.work/` directory SHALL be a gitignored scratch space for temporary files that should not be version-controlled.

#### Scenario: Work directory created on init
- **WHEN** `set-project init` creates the `wt/` structure
- **THEN** `set/.work/` directory is created
- **AND** `set/.work/` is added to the project's `.gitignore`

#### Scenario: Temporary files not tracked
- **WHEN** a plugin, agent, or orchestrator writes files to `set/.work/`
- **THEN** those files are not tracked by git

#### Scenario: Safe to clean
- **WHEN** a user runs `rm -rf set/.work/*`
- **THEN** no versioned data is lost and the system continues to function

### Requirement: Backward-compatible file lookup
All set-core components SHALL use a fallback chain when looking for configuration and knowledge files, checking the new `wt/` location first and falling back to legacy locations.

#### Scenario: New location takes precedence
- **WHEN** both `set/orchestration/config.yaml` and `.claude/orchestration.yaml` exist
- **THEN** the `set/orchestration/config.yaml` is used

#### Scenario: Legacy location still works
- **WHEN** only `.claude/orchestration.yaml` exists (no `wt/` directory)
- **THEN** the orchestrator uses `.claude/orchestration.yaml` without errors or warnings

#### Scenario: No config exists
- **WHEN** neither new nor legacy config files exist
- **THEN** the component uses hardcoded defaults (existing behavior preserved)
