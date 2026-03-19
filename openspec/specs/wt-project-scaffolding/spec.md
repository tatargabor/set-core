## ADDED Requirements

### Requirement: Scaffold wt directory on init
`set-project init` SHALL create the `wt/` directory structure as part of project initialization, after deploying `.claude/` files.

#### Scenario: Fresh project init
- **WHEN** `set-project init` runs in a project with no `wt/` directory
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
- **AND** `wt/.work/` is added to the project's `.gitignore` if not already present

#### Scenario: Idempotent scaffolding
- **WHEN** `set-project init` runs in a project that already has `wt/` with some subdirectories
- **THEN** only missing subdirectories are created, existing content is untouched

### Requirement: Detect legacy file locations
`set-project init` SHALL detect set-core files in legacy locations and inform the user about migration.

#### Scenario: Legacy orchestration config detected
- **WHEN** `.claude/orchestration.yaml` exists but `wt/orchestration/config.yaml` does not
- **THEN** the init output displays a migration suggestion:
  ```
  Found legacy files:
    .claude/orchestration.yaml → wt/orchestration/config.yaml
  Run 'set-project migrate' to move them.
  ```

#### Scenario: Legacy project-knowledge detected
- **WHEN** `project-knowledge.yaml` exists at project root but `wt/knowledge/project-knowledge.yaml` does not
- **THEN** the init output includes it in the migration suggestion list

#### Scenario: Legacy run logs detected
- **WHEN** `docs/orchestration-runs/` exists but `wt/orchestration/runs/` is empty or missing
- **THEN** the init output includes run logs in the migration suggestion list

#### Scenario: No legacy files
- **WHEN** no legacy set-core files exist in old locations
- **THEN** no migration message is shown

### Requirement: Migrate command
`set-project migrate` SHALL move files from legacy locations to the `wt/` directory structure using `git mv` when in a git repository.

#### Scenario: Migrate orchestration config
- **WHEN** user runs `set-project migrate`
- **AND** `.claude/orchestration.yaml` exists
- **THEN** the file is moved to `wt/orchestration/config.yaml` via `git mv`

#### Scenario: Migrate project-knowledge
- **WHEN** user runs `set-project migrate`
- **AND** `project-knowledge.yaml` exists at project root
- **THEN** the file is moved to `wt/knowledge/project-knowledge.yaml` via `git mv`

#### Scenario: Migrate run logs
- **WHEN** user runs `set-project migrate`
- **AND** `docs/orchestration-runs/` contains files
- **THEN** all files are moved to `wt/orchestration/runs/` via `git mv`
- **AND** the empty `docs/orchestration-runs/` directory is removed

#### Scenario: Already migrated
- **WHEN** user runs `set-project migrate`
- **AND** no legacy files exist
- **THEN** the command prints "Nothing to migrate — all files already in wt/"

#### Scenario: Non-git project
- **WHEN** user runs `set-project migrate` in a non-git directory
- **THEN** files are moved with `mv` instead of `git mv`
