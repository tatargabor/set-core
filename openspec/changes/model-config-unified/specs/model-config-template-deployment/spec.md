## ADDED Requirements

### Requirement: web template ships a documented models block

`modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml` SHALL include a documented `models:` block. The block SHALL be commented out by default (so framework defaults apply), with each role line accompanied by a one-line comment explaining its purpose.

#### Scenario: deployed config.yaml contains a models block (commented)
- **WHEN** the file `modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml` is read
- **THEN** it contains a `# models:` block listing each of the 13 leaf roles plus the trigger sub-dict, with role descriptions

#### Scenario: each documented role has a per-line comment
- **WHEN** the `models:` block in the deployed template is read
- **THEN** each role line (e.g. `#   agent: opus-4-6  # per-change agent (ralph/claude in worktree)`) has a comment explaining what the role does

#### Scenario: deploying the template produces a working orchestration.yaml
- **WHEN** `set-project init` is run on a fresh project
- **THEN** the resulting `set/orchestration/config.yaml` contains the commented `models:` block
- **AND** running `resolve_model("agent")` against the new project returns the DIRECTIVE_DEFAULTS value (`"opus-4-6"`) since the block is commented out

### Requirement: release notes document the agent-default change as breaking

`docs/release/v1.8.0.md` (or the active release-notes file) SHALL include a prominent entry calling out the `models.agent` default change from `opus → opus-4-7` to `opus-4-6` as a behavioral change. The entry SHALL include a migration recipe for operators that want the prior behavior.

#### Scenario: release notes mention the agent default change
- **WHEN** `docs/release/v1.8.0.md` is read
- **THEN** it contains a one-line entry naming `models.agent` and the new default `opus-4-6`
- **AND** it documents the migration: "operators that want the prior behavior set `models.agent: opus-4-7` (or use `--model-profile all-opus-4-7`)"
