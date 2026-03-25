## MODIFIED Requirements

### Requirement: Deploy rules to project
When `set-project init` runs, it SHALL copy rule files from `templates/core/rules/` in the set-core repo to `<project>/.claude/rules/`, prefixing each filename with `set-`. The source directory is `templates/core/rules/`, NOT `.claude/rules/`. All `.md` files in `templates/core/rules/` SHALL be deployed. Existing `set-`prefixed files SHALL be overwritten. Non-prefixed project-specific rules SHALL remain untouched.

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
