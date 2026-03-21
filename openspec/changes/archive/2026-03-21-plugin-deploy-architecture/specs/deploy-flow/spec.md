## MODIFIED Requirements

### Requirement: deploy.sh deploys core rules
deploy.sh SHALL deploy only top-level `.md` files from `set-core/.claude/rules/` (maxdepth 1). It SHALL NOT traverse subdirectories or apply project-type-specific filtering.

#### Scenario: Only top-level rules deployed by deploy.sh
- **WHEN** `set-core/.claude/rules/` contains `cross-cutting-checklist.md` at top level and `gui/testing.md` in a subdirectory
- **THEN** deploy.sh copies `cross-cutting-checklist.md` as `set-cross-cutting-checklist.md` to the consumer
- **AND** `gui/testing.md` is NOT copied

#### Scenario: No web/ directory check in deploy.sh
- **WHEN** deploy.sh processes rules
- **THEN** there is no conditional logic checking for `web`, `python`, or any other project-type subdirectory name

### Requirement: Plugin rules deployed via Python deploy_templates
All project-type-specific rules SHALL be deployed by the `deploy_templates()` function in `set-project-base/deploy.py`, not by deploy.sh.

#### Scenario: Web framework rules deployed by Python mechanism
- **WHEN** `set-project init web` is run
- **THEN** `deploy_templates()` copies `framework-rules/web/*.md` from the plugin to `.claude/rules/web/set-*.md` in the consumer
