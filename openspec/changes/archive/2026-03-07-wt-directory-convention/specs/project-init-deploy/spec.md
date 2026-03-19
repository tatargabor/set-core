## MODIFIED Requirements

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
