# Spec: wt-directory-structure (MODIFIED)

## MODIFIED Requirements

### Requirement: Project config directory naming
The project config directory SHALL be named `set/` (previously `wt/`). All paths referencing `wt/orchestration/`, `wt/knowledge/`, `wt/plugins/`, `wt/.work/` SHALL use `set/orchestration/`, `set/knowledge/`, `set/plugins/`, `set/.work/` respectively.

#### Scenario: New project scaffold
- **WHEN** `set-project init` creates a new project
- **THEN** the directory `set/` is created with subdirectories orchestration/, knowledge/, plugins/, .work/

#### Scenario: Legacy project migration
- **WHEN** `set-project init` runs on a project with existing `wt/` directory
- **THEN** `wt/` is renamed to `set/` automatically
- **AND** a message is shown: "Migrated wt/ → set/"

#### Scenario: Backwards compatibility
- **WHEN** code looks for config files (config.yaml, project-type.yaml, etc.)
- **THEN** it checks `set/` first, falls back to `wt/` if `set/` doesn't exist
