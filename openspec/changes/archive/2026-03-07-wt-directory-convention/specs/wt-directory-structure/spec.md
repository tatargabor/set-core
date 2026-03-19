## ADDED Requirements

### Requirement: wt directory exists in consumer projects
Every consumer project using set-core SHALL have a `wt/` directory at the project root. This directory is the canonical location for all set-core project-specific artifacts.

#### Scenario: New project initialization
- **WHEN** `set-project init` runs in a project without a `wt/` directory
- **THEN** the `wt/` directory structure is created with all subdirectories

#### Scenario: Existing project re-init
- **WHEN** `set-project init` runs in a project that already has a `wt/` directory
- **THEN** missing subdirectories are created without modifying existing files

### Requirement: Orchestration subdirectory
The `wt/orchestration/` directory SHALL contain all orchestration-related artifacts: configuration, run logs, and saved plans.

#### Scenario: Config file location
- **WHEN** the orchestrator looks for orchestration directives
- **THEN** it checks `wt/orchestration/config.yaml` first, then falls back to `.claude/orchestration.yaml`

#### Scenario: Run logs location
- **WHEN** the orchestrator writes a run log
- **THEN** the log is saved to `wt/orchestration/runs/` with the existing markdown format

#### Scenario: Plan history
- **WHEN** the planner creates a new orchestration plan
- **THEN** the plan JSON is saved to `wt/orchestration/plans/plan-v{N}-{YYYY-MM-DD}.json` in addition to the working `orchestration-plan.json`

### Requirement: Knowledge subdirectory
The `wt/knowledge/` directory SHALL contain project knowledge artifacts used by agents during execution.

#### Scenario: Project knowledge location
- **WHEN** the planner, dispatcher, or verifier looks for project-knowledge.yaml
- **THEN** it checks `wt/knowledge/project-knowledge.yaml` first, then falls back to `./project-knowledge.yaml`

#### Scenario: Patterns subdirectory
- **WHEN** a project has reusable code patterns (CRUD templates, API endpoint patterns)
- **THEN** they are stored as markdown files in `wt/knowledge/patterns/`

#### Scenario: Lessons subdirectory
- **WHEN** orchestration runs produce learnings (from run log conclusions)
- **THEN** extracted lessons are stored in `wt/knowledge/lessons/`

### Requirement: Requirements subdirectory
The `wt/requirements/` directory SHALL contain business requirement YAML files that serve as input for spec generation and planning.

#### Scenario: Requirements directory exists
- **WHEN** `set-project init` completes
- **THEN** `wt/requirements/` directory exists and is ready for requirement files

#### Scenario: Requirements are discoverable
- **WHEN** the planner generates a plan
- **THEN** it can scan `wt/requirements/*.yaml` for business requirements to inform decomposition

### Requirement: Plugins subdirectory
The `wt/plugins/` directory SHALL provide a workspace for each installed set-core plugin, where plugins can store their data, state, and generated artifacts.

#### Scenario: Plugin workspace created on plugin init
- **WHEN** a plugin is installed or initialized (e.g., `set-project add-plugin wt-spec-capture`)
- **THEN** `wt/plugins/<plugin-name>/` directory is created
- **AND** the plugin can define its own internal directory structure within its workspace

#### Scenario: Plugin workspace isolation
- **WHEN** multiple plugins are installed (e.g., wt-web and wt-spec-capture)
- **THEN** each plugin has its own isolated directory under `wt/plugins/`
- **AND** plugins do not write to each other's workspace

#### Scenario: Chrome extension workspace example
- **WHEN** wt-spec-capture plugin is installed
- **THEN** it uses `wt/plugins/wt-spec-capture/` for scraped site data, generated drafts, and plugin config

#### Scenario: Plugin workspace without plugin system
- **WHEN** `wt/plugins/` exists but no formal plugin system is implemented yet
- **THEN** plugins can manually create their workspace directory and use it independently

### Requirement: Gitignored work directory
The `wt/.work/` directory SHALL be a gitignored scratch space for temporary files that should not be version-controlled.

#### Scenario: Work directory created on init
- **WHEN** `set-project init` creates the `wt/` structure
- **THEN** `wt/.work/` directory is created
- **AND** `wt/.work/` is added to the project's `.gitignore`

#### Scenario: Temporary files not tracked
- **WHEN** a plugin, agent, or orchestrator writes files to `wt/.work/`
- **THEN** those files are not tracked by git

#### Scenario: Safe to clean
- **WHEN** a user runs `rm -rf wt/.work/*`
- **THEN** no versioned data is lost and the system continues to function

### Requirement: Backward-compatible file lookup
All set-core components SHALL use a fallback chain when looking for configuration and knowledge files, checking the new `wt/` location first and falling back to legacy locations.

#### Scenario: New location takes precedence
- **WHEN** both `wt/orchestration/config.yaml` and `.claude/orchestration.yaml` exist
- **THEN** the `wt/orchestration/config.yaml` is used

#### Scenario: Legacy location still works
- **WHEN** only `.claude/orchestration.yaml` exists (no `wt/` directory)
- **THEN** the orchestrator uses `.claude/orchestration.yaml` without errors or warnings

#### Scenario: No config exists
- **WHEN** neither new nor legacy config files exist
- **THEN** the component uses hardcoded defaults (existing behavior preserved)
