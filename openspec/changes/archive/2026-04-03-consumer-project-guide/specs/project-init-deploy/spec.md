## MODIFIED Requirements

### Requirement: Deploy rules to project
When `set-project init` runs, it SHALL copy all files from the set-core repo's `templates/core/rules/` directory to `<project>/.claude/rules/`, prefixed with `set-`. This now includes `project-guide.md` which deploys as `set-project-guide.md`.

#### Scenario: First init deploys rules including project guide
- **WHEN** `set-project init` is run in a project that has no `.claude/rules/` directory
- **THEN** the directory is created and all rules files are copied with `set-` prefix from `templates/core/rules/`
- **AND** `set-project-guide.md` is among the deployed files

#### Scenario: Re-init updates rules without touching project rules
- **WHEN** `set-project init` is run in a project that has `.claude/rules/` with both `set-*` and custom rules
- **THEN** only `set-*` prefixed files SHALL be overwritten
- **AND** non-prefixed project-specific rules SHALL remain untouched
