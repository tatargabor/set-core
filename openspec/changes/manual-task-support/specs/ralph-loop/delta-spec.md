## ADDED Requirements

### Requirement: Manual task counting in check_tasks_done
`check_tasks_done()` must distinguish `[?]` tasks from `[ ]` tasks.

#### Scenario: Only manual tasks remain
- **WHEN** tasks.md has zero `[ ]` tasks and one or more `[?]` tasks
- **THEN** `check_tasks_done()` returns 0 (auto-tasks complete) — manual tasks are handled separately by stall detection

### Requirement: waiting:human status transition
The stall detection block transitions to `waiting:human` when appropriate.

#### Scenario: Stall detected with manual tasks pending
- **WHEN** an iteration produces no commits and no dirty files (stall condition)
- **AND** `check_tasks_done()` returns 0 (no `[ ]` tasks left)
- **AND** `[?]` tasks exist in tasks.md
- **THEN** set status to `"waiting:human"`, write manual task details to loop-state.json, and exit 0

### Requirement: Prompt builder includes manual task instruction
When `[?]` tasks exist, the prompt tells Claude to skip them.

#### Scenario: tasks.md has manual tasks
- **WHEN** `build_prompt()` runs and tasks.md contains `[?]` lines
- **THEN** append to prompt: "Tasks marked [?] require human action. Do NOT attempt them. Focus only on [ ] tasks."

## MODIFIED Requirements

### Requirement: Status display recognizes waiting:human
#### Scenario: Status icon for waiting:human
- **WHEN** loop status is `waiting:human`
- **THEN** display `⏸` icon (alongside existing `✅` done, `❓` stalled, etc.)
