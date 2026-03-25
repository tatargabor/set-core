## MODIFIED Requirements

### Requirement: deploy.sh deploys core rules
deploy.sh SHALL deploy only top-level `.md` files from `templates/core/rules/` (maxdepth 1). It SHALL NOT traverse subdirectories. Each file is deployed with a `set-` filename prefix. When deploying to the set-core repository itself, rules deployment SHALL be skipped (self-deploy guard via git root comparison).

#### Scenario: Only template core rules deployed by deploy.sh
- **WHEN** `templates/core/rules/` contains `cross-cutting-checklist.md` and `.claude/rules/` contains `modular-architecture.md`
- **THEN** deploy.sh copies `cross-cutting-checklist.md` as `set-cross-cutting-checklist.md` to the consumer
- **AND** `modular-architecture.md` is NOT copied (it lives in `.claude/rules/` which is not the deploy source)

#### Scenario: Self-deploy skips rules
- **WHEN** deploy.sh detects that the target project's git root matches set-core's own root
- **THEN** rules deployment is skipped entirely

### Requirement: Plugin rules deployed via Python deploy_templates
All project-type-specific rules SHALL be deployed by the `deploy_templates()` function in `profile_deploy.py`, not by deploy.sh.

#### Scenario: Web framework rules deployed by Python mechanism
- **WHEN** `set-project init --project-type web` is run
- **THEN** `deploy_templates()` copies `framework-rules/web/*.md` from the plugin to `.claude/rules/set-*.md` in the consumer
