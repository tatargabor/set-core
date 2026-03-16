## MODIFIED Requirements

### Requirement: Features Section
The `features` section in `project-knowledge.yaml` maps feature names to file path globs, an optional `rules_file` path, cross-cutting file references, and related features.

The optional `rules_file` field SHALL specify the path (relative to the project root) of a Claude rules file to inject into the worktree at dispatch time when the feature matches the change scope.

The dispatcher SHALL read `rules_file` and copy the referenced file into the worktree's `.claude/rules/` directory, making the rule active for the agent during implementation.

#### Scenario: Feature rules_file is injected at dispatch
- **WHEN** `dispatch_change()` runs for a change whose scope overlaps with a feature's `touches` globs
- **AND** that feature has `rules_file: ".claude/rules/data-model.md"`
- **THEN** `.claude/rules/data-model.md` is copied from the main project into the worktree's `.claude/rules/` before the agent starts

#### Scenario: Feature without rules_file has no injection side effect
- **WHEN** a feature in `project-knowledge.yaml` has no `rules_file` field
- **THEN** no rule file injection occurs for that feature
- **AND** dispatch proceeds normally

#### Scenario: rules_file path is relative to project root
- **WHEN** `rules_file: ".claude/rules/auth-conventions.md"` is specified
- **THEN** the dispatcher resolves it as `<project_root>/.claude/rules/auth-conventions.md`
- **AND** the file is copied to `<worktree>/.claude/rules/auth-conventions.md`
