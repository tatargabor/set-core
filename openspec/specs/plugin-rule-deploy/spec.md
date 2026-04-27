# Plugin Rule Deploy Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Plugin controls which framework rules get deployed to consumer projects
- Framework rules stored in plugin package under `framework-rules/` directory
- Deploy mechanism applies `set-` prefix to framework rule filenames
- Re-running `set-project init` updates framework rules from plugin

### Out of scope
- Creating new project type plugins
- Changing the entry_points plugin discovery mechanism
- Template rule deployment changes (rules/ path mapping already works)

## Requirements

### Requirement: Plugin package contains framework rules
The plugin package SHALL store framework rules under `templates/<template-id>/framework-rules/<subdir>/` relative to the plugin's package directory. The subdirectory name (e.g., `web/`) determines the target subdirectory under `.claude/rules/` in the consumer project.

#### Scenario: Web plugin has framework rules
- **WHEN** `set-project-web` plugin package contains `templates/nextjs/framework-rules/web/auth-middleware.md`
- **THEN** the file is available for deployment to consumer projects at `.claude/rules/web/set-auth-middleware.md`

### Requirement: deploy_templates deploys framework rules with set- prefix
The `deploy_templates()` function in `set-project-base/deploy.py` SHALL map `framework-rules/` to `.claude/rules/` and apply the `set-` filename prefix to all files under this path.

#### Scenario: Framework rules deployed with prefix
- **WHEN** `deploy_templates()` processes a file at `framework-rules/web/security-patterns.md`
- **THEN** the file is written to `<target>/.claude/rules/web/set-security-patterns.md`

#### Scenario: Template rules deployed without prefix
- **WHEN** `deploy_templates()` processes a file at `rules/auth-conventions.md`
- **THEN** the file is written to `<target>/.claude/rules/auth-conventions.md` (no `set-` prefix)

### Requirement: Framework rules included in manifest
The plugin's `manifest.yaml` SHALL list framework rule files in the `core` section so they are deployed by default (not as optional modules).

#### Scenario: Manifest includes framework rules
- **WHEN** `manifest.yaml` contains `framework-rules/web/auth-middleware.md` in its `core` list
- **THEN** the file is deployed during `set-project init` without requiring `--modules` flag

### Requirement: Re-run updates framework rules
Running `set-project init` on an existing project SHALL overwrite previously deployed framework rules with current versions from the plugin package.

#### Scenario: Updated rule deployed on re-init
- **WHEN** the plugin updates `framework-rules/web/auth-middleware.md` with new content
- **AND** user runs `set-project init` on an existing consumer project
- **THEN** `.claude/rules/web/set-auth-middleware.md` in the consumer project contains the updated content
