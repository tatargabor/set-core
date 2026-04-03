## MODIFIED Requirements

### Requirement: Deploy rules to project
When `set-project init` runs, it SHALL copy all files from the set-core repo's `.claude/rules/` directory to `<project>/.claude/rules/`, preserving subdirectory structure and creating directories as needed. Files SHALL be prefixed with `set-` in target projects (unless deploying to the set-core repo itself) to avoid conflicts with project-specific rules. Existing set-prefixed files SHALL be overwritten.

#### Scenario: First init deploys rules
- **WHEN** `set-project init` is run in a project that has no `.claude/rules/` directory
- **THEN** the directory is created and all rules files are copied with `set-` prefix from the set-core repo

#### Scenario: Re-init updates rules without touching project rules
- **WHEN** `set-project init` is run in a project that has `.claude/rules/` with both `set-*` and custom rules
- **THEN** only `set-*` prefixed files SHALL be overwritten
- **AND** non-prefixed project-specific rules SHALL remain untouched

#### Scenario: Self-deploy skips prefix
- **WHEN** `set-project init` deploys to the set-core repo itself (source == destination)
- **THEN** rules files SHALL NOT be copied (self-deploy detected via realpath comparison)

### Requirement: Template file deployment respects protection
When `set-project init` deploys template files during re-init, files annotated as `protected` in the manifest SHALL be skipped if modified by the project. Files annotated as `merge` SHALL use additive YAML merge.

#### Scenario: Re-init preserves modified scaffold files
- **WHEN** `set-project init` re-initializes a project
- **AND** `next.config.js` is marked `protected: true` in the manifest
- **AND** the project's `next.config.js` differs from the template
- **THEN** the file SHALL NOT be overwritten
- **AND** the output SHALL show `Skipped (protected): next.config.js`

#### Scenario: Re-init merges config additively
- **WHEN** `set-project init` re-initializes a project
- **AND** `set/orchestration/config.yaml` is marked `merge: true` in the manifest
- **THEN** new keys from the template SHALL be added to the existing config
- **AND** existing keys SHALL NOT be modified

#### Scenario: First init deploys all files normally
- **WHEN** `set-project init` runs on a fresh project with no existing files
- **THEN** all template files SHALL be deployed regardless of protection or merge flags
