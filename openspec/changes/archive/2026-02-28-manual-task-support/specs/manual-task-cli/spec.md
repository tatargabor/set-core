## ADDED Requirements

### Requirement: wt-manual list
Show all changes currently waiting for human input.

#### Scenario: Changes waiting for input exist
- **WHEN** user runs `wt-manual list`
- **AND** orchestration-state.json has changes with status `waiting:human`
- **THEN** display each change name, waiting duration, and summary of pending manual tasks

#### Scenario: No changes waiting
- **WHEN** user runs `wt-manual list`
- **AND** no changes have status `waiting:human`
- **THEN** display "No changes waiting for manual input"

### Requirement: wt-manual show
Display detailed instructions for a specific change's manual tasks.

#### Scenario: Show manual tasks for a change
- **WHEN** user runs `wt-manual show <change-name>`
- **THEN** display each pending `[?]` task with its type, description, and `### Manual:` instructions from tasks.md
- **AND** show the worktree path where the change is being worked on

#### Scenario: Change not found or not waiting
- **WHEN** user runs `wt-manual show <change-name>` but the change doesn't exist or isn't in `waiting:human`
- **THEN** display an appropriate error message

### Requirement: wt-manual input
Provide a secret/value for an input-type manual task.

#### Scenario: Provide input value
- **WHEN** user runs `wt-manual input <change-name> <KEY> <value>`
- **THEN** write `KEY=value` to the change's worktree `.env.local` file (append or update if key exists)
- **AND** mark the corresponding `[?]` task as `[x]` in tasks.md

#### Scenario: Key already exists in .env.local
- **WHEN** user provides input for a KEY that already exists in `.env.local`
- **THEN** update the existing value (replace the line)

### Requirement: wt-manual done
Mark a confirm-type manual task as complete.

#### Scenario: Confirm task completion
- **WHEN** user runs `wt-manual done <change-name> <task-id>`
- **THEN** change the task from `- [?]` to `- [x]` in tasks.md

#### Scenario: Invalid task ID
- **WHEN** user runs `wt-manual done <change-name> <task-id>` with a non-existent task ID
- **THEN** display error message listing valid task IDs

### Requirement: wt-manual resume
Resume the Ralph loop after manual tasks are resolved.

#### Scenario: All manual tasks resolved
- **WHEN** user runs `wt-manual resume <change-name>`
- **AND** all `[?]` tasks for that change have been resolved (marked `[x]`)
- **THEN** restart the Ralph loop for that change's worktree (call `wt-loop resume`)

#### Scenario: Manual tasks still pending
- **WHEN** user runs `wt-manual resume <change-name>`
- **AND** some `[?]` tasks are still pending
- **THEN** warn the user about unresolved tasks and ask for confirmation before resuming

#### Scenario: Resume without orchestrator
- **WHEN** user runs `wt-manual resume <change-name>` and set-orchestrate is NOT running
- **THEN** resume the Ralph loop directly (standalone mode — wt-loop resume in the worktree)

#### Scenario: Resume with orchestrator
- **WHEN** user runs `wt-manual resume <change-name>` and set-orchestrate IS running
- **THEN** update the change status in orchestration-state.json back to `"running"` so the orchestrator picks it up, and let the orchestrator handle the resume
