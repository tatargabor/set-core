## ADDED Requirements

### Requirement: set-loop accepts --change flag
The `set-loop start` command SHALL accept an optional `--change <name>` CLI flag that specifies which OpenSpec change the loop is scoped to. The value SHALL be stored in `loop-state.json` under the `change` key.

#### Scenario: Start with explicit change
- **WHEN** user runs `set-loop start "task description" --change my-change --done openspec`
- **THEN** `loop-state.json` SHALL contain `"change": "my-change"`

#### Scenario: Start without change flag
- **WHEN** user runs `set-loop start "task description" --done openspec`
- **THEN** `loop-state.json` SHALL contain `"change": null` or the key SHALL be absent

### Requirement: Scoped detection when change is specified
When `--change` is set, `detect_next_change_action()` SHALL only inspect the specified change directory. It SHALL NOT scan other changes.

#### Scenario: Assigned change needs ff
- **WHEN** `--change smoke-config` is set AND `openspec/changes/smoke-config/tasks.md` does not exist
- **THEN** detect SHALL return `ff:smoke-config`
- **AND** other incomplete changes (e.g., `email-sandbox`) SHALL be ignored

#### Scenario: Assigned change needs apply
- **WHEN** `--change smoke-config` is set AND `openspec/changes/smoke-config/tasks.md` exists with unchecked tasks
- **THEN** detect SHALL return `apply:smoke-config`

#### Scenario: Assigned change is complete
- **WHEN** `--change smoke-config` is set AND all tasks in `openspec/changes/smoke-config/tasks.md` are checked
- **THEN** detect SHALL return `done`

### Requirement: No detection when change is unspecified
When `--change` is NOT set, `detect_next_change_action()` SHALL NOT run. The `build_prompt()` function SHALL use the generic task description as the effective task without OpenSpec-specific prompt injection.

#### Scenario: Solo loop without change flag
- **WHEN** `--change` is not set AND `--done openspec` is set
- **THEN** `build_prompt()` SHALL use the original task string as `effective_task`
- **AND** no `openspec_instructions` block SHALL be injected into the prompt

#### Scenario: Solo loop done criteria
- **WHEN** `--change` is not set AND `--done openspec` is set
- **THEN** the done-check in `check_done_criteria()` SHALL still evaluate OpenSpec completion by scanning all changes (existing behavior preserved for exit-condition only)

### Requirement: Orchestrator passes change name
The `dispatch_change()` function in `set-orchestrate` SHALL pass `--change "$change_name"` to the `set-loop start` invocation.

#### Scenario: Orchestrator dispatch
- **WHEN** the orchestrator dispatches change `smoke-config` to a worktree
- **THEN** the `set-loop start` command SHALL include `--change smoke-config`
