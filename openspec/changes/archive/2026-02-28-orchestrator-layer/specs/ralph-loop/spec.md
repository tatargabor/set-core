## MODIFIED Requirements

### Requirement: External pause via signal
The Ralph loop SHALL support graceful pause initiated by an external process.

#### Scenario: SIGTERM from orchestrator
- **WHEN** the orchestrator sends SIGTERM to the Ralph terminal PID
- **THEN** the existing cleanup_on_exit trap SHALL fire
- **AND** the current iteration SHALL be recorded with an `ended` timestamp
- **AND** loop status SHALL be updated to "stopped" in loop-state.json
- **AND** the exit SHALL be graceful (no data loss)

#### Scenario: Terminal PID file
- **WHEN** Ralph starts
- **THEN** it SHALL write its PID to `<worktree>/.claude/ralph-terminal.pid`
- **AND** the orchestrator SHALL read this file to determine the signal target

### Requirement: Programmatic status query
The Ralph loop state SHALL be queryable by external processes without parsing terminal output.

#### Scenario: Status via loop-state.json
- **WHEN** an external process reads `<worktree>/.claude/loop-state.json`
- **THEN** the `status` field SHALL accurately reflect the current state: one of "starting", "running", "done", "stuck", "stalled", "stopped"
- **AND** `current_iteration` SHALL reflect the latest iteration number
- **AND** `total_tokens` SHALL reflect cumulative token usage

#### Scenario: Done signal for orchestrator
- **WHEN** Ralph detects that all tasks are complete (via check_done)
- **THEN** it SHALL update loop-state.json status to "done" before exiting
- **AND** the orchestrator SHALL detect this by polling the status field

### Requirement: Restart in existing worktree
The Ralph loop SHALL support restarting in a worktree that has prior loop state.

#### Scenario: Resume after pause
- **WHEN** `wt-loop start` is run in a worktree that already has loop-state.json with status "stopped"
- **THEN** Ralph SHALL create a new loop-state.json (fresh iteration count)
- **AND** use the existing tasks.md progress (already-checked tasks remain checked)
- **AND** detect_next_change_action SHALL correctly identify remaining work

#### Scenario: No duplicate worktree creation
- **WHEN** the orchestrator resumes a paused change
- **THEN** it SHALL NOT create a new worktree
- **AND** SHALL run `wt-loop start` in the existing worktree path from orchestration-state.json

### Requirement: Stale loop-state detection
When a change has status "running" but its `loop-state.json` file has not been modified for more than 5 minutes, the orchestrator SHALL treat this as a stall and auto-resume the change.

#### Scenario: Loop state file goes stale
- **WHEN** loop-state.json mtime is older than 5 minutes for a running change
- **THEN** the orchestrator SHALL increment stall_count and resume the change
- **AND** status SHALL be set to "stalled" before calling resume_change()

#### Scenario: Max stall retries exceeded
- **WHEN** stall_count exceeds 3 for a stale running change
- **THEN** the change SHALL be marked as "failed" with a critical notification

### Requirement: Ralph loop launch flags
The orchestrator SHALL launch Ralph loops with the following flags:

#### Scenario: Dispatch start
- **WHEN** dispatch_change() starts a new Ralph loop
- **THEN** it SHALL run: `wt-loop start "<task description>" --max 30 --done openspec --label "<change-name>" --model opus`
- **AND** the task description SHALL be the first positional argument (the change scope)

#### Scenario: Resume start
- **WHEN** resume_change() restarts a Ralph loop
- **THEN** it SHALL use the same flags: task description as positional arg, --max, --done, --label, --model
