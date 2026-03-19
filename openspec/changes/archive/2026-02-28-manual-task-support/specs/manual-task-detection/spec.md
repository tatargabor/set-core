## ADDED Requirements

### Requirement: waiting:human loop status
wt-loop recognizes when only manual tasks remain and transitions to `waiting:human` status instead of stalling.

#### Scenario: All auto-tasks done, manual tasks remain
- **WHEN** Ralph completes an iteration with no commits and no dirty files (would normally stall)
- **AND** tasks.md has zero `[ ]` tasks but one or more `[?]` tasks
- **THEN** wt-loop sets status to `"waiting:human"` and exits cleanly (exit code 0)

#### Scenario: Auto-tasks still remain alongside manual tasks
- **WHEN** tasks.md has both `[ ]` auto-tasks and `[?]` manual tasks
- **THEN** wt-loop continues running normally — Ralph works on the `[ ]` tasks

#### Scenario: Stall with manual tasks present
- **WHEN** Ralph stalls (no commits, no progress) and `[?]` tasks exist in tasks.md
- **AND** `[ ]` auto-tasks also exist (agent failed to make progress on them)
- **THEN** wt-loop still increments stall_count as usual — the `[?]` tasks don't mask a genuine stall on auto-tasks

#### Scenario: No manual tasks — existing behavior preserved
- **WHEN** tasks.md has only `[ ]` and `[x]` tasks (no `[?]`)
- **THEN** all existing stall detection and check_done behavior is unchanged

### Requirement: Manual task info in loop-state.json
When entering `waiting:human`, wt-loop writes structured info about pending manual tasks.

#### Scenario: Loop state includes manual task details
- **WHEN** wt-loop transitions to `waiting:human`
- **THEN** loop-state.json includes `manual_tasks` array with `id`, `description`, `type`, and optional `input_key` for each pending `[?]` task
- **AND** includes `waiting_since` timestamp

### Requirement: Orchestrator handles waiting:human
set-orchestrate's poll_change() treats `waiting:human` as a distinct state — not a stall, not a failure.

#### Scenario: poll_change sees waiting:human
- **WHEN** a change's Ralph loop-state has status `waiting:human`
- **THEN** the orchestrator updates change status to `"waiting:human"` in orchestration-state.json
- **AND** does NOT increment stall_count
- **AND** does NOT auto-resume the loop
- **AND** logs the manual task summary

#### Scenario: Other changes continue
- **WHEN** one change is in `waiting:human` status
- **THEN** the orchestrator continues dispatching and polling other non-blocked changes normally

#### Scenario: Status display shows manual task info
- **WHEN** orchestrator status is displayed (TUI or log)
- **THEN** `waiting:human` changes show with a `⏸` icon and the pending manual task summary

### Requirement: Agent prompt awareness
Ralph (Claude) is instructed not to attempt `[?]` tasks.

#### Scenario: Prompt includes manual task instruction
- **WHEN** wt-loop builds the prompt for a Ralph iteration
- **AND** tasks.md contains `[?]` tasks
- **THEN** the prompt includes an instruction telling Claude to skip `[?]` tasks and focus on `[ ]` tasks only
