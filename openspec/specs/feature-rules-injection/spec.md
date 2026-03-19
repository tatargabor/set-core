## ADDED Requirements

## IN SCOPE
- Reading `rules_file` from `project-knowledge.yaml` features at dispatch time
- Copying matched rule files into the worktree's `.claude/rules/` directory
- Path-glob matching of change scope against feature `touches` to determine which rules apply
- Graceful degradation when `project-knowledge.yaml` or `rules_file` is absent
- Skip injection if rule file already exists in worktree (idempotent dispatch)

## OUT OF SCOPE
- Mid-iteration rule injection (dispatch-time only)
- Automatic rule content generation (rules files must already exist in the project)
- Injection into the main project directory (worktree only)

### Requirement: Feature rules resolved at dispatch
When dispatching a change, the dispatcher SHALL read `project-knowledge.yaml`, match the change scope against each feature's `touches` globs, and for each matching feature with a `rules_file` field, copy that rule file into the worktree.

#### Scenario: Matching feature rule is injected
- **WHEN** `dispatch_change("db-migration-change")` runs
- **AND** `project-knowledge.yaml` has a `data_model` feature with `touches: ["prisma/**"]` and `rules_file: ".claude/rules/data-model.md"`
- **AND** the change scope mentions `prisma/schema.prisma`
- **THEN** `data-model.md` is copied to `<worktree>/.claude/rules/data-model.md` before `set-loop` starts

#### Scenario: Non-matching feature rules are not injected
- **WHEN** `dispatch_change("feature-change")` runs
- **AND** the change scope does not mention any `prisma/**` paths
- **THEN** `data-model.md` is NOT copied to the worktree

#### Scenario: Multiple features match
- **WHEN** a change scope overlaps with both `data_model` and `api` features
- **THEN** both feature rule files are copied to the worktree

### Requirement: Injection happens after bootstrap
Rule file injection SHALL occur after `bootstrap_worktree()` completes in `dispatch_change()`, ensuring bootstrap does not overwrite injected files.

#### Scenario: Injection order is post-bootstrap
- **WHEN** `dispatch_change()` executes the worktree setup sequence
- **THEN** rule file copy happens after `bootstrap_worktree()` and before `set-loop` is started

### Requirement: Graceful degradation
If `project-knowledge.yaml` does not exist, or a feature's `rules_file` path does not resolve to an existing file, the dispatcher SHALL log a warning and continue dispatch without failing.

#### Scenario: Missing project-knowledge.yaml is a no-op
- **WHEN** no `project-knowledge.yaml` exists in the project
- **THEN** dispatch proceeds normally with no rule injection
- **AND** no error is raised

#### Scenario: Missing rules_file is a warning
- **WHEN** a feature specifies `rules_file: ".claude/rules/missing.md"` but that file does not exist
- **THEN** dispatcher logs `"[warn] rules_file not found: .claude/rules/missing.md — skipping injection"`
- **AND** dispatch continues

#### Scenario: Existing worktree rule file is not overwritten
- **WHEN** `<worktree>/.claude/rules/data-model.md` already exists (e.g., from a previous dispatch)
- **THEN** the dispatcher does NOT overwrite it
- **AND** the existing file is preserved

### Requirement: Injection is logged
The dispatcher SHALL log each injected rule file at INFO level.

#### Scenario: Injection appears in orchestration log
- **WHEN** rule injection occurs for `data-model.md`
- **THEN** the orchestration log contains `"injected feature rule: data_model → .claude/rules/data-model.md"`
