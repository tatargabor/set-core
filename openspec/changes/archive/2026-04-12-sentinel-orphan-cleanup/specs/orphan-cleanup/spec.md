# Spec: Orphan Cleanup

## ADDED Requirements

## IN SCOPE
- Detecting and cleaning orphaned worktrees (exist on disk but not in state)
- Fixing stale ralph_pid references (PID dead but still in state)
- Fixing stuck current_step values (merged but step != done)
- Running automatically at orchestrator startup (before poll loop)
- Conservative approach: never kill processes, never touch dirty worktrees

## OUT OF SCOPE
- Killing orphaned claude processes (too dangerous — could be user sessions)
- Modifying change status (only step, pid, worktree cleanup)
- Real-time cleanup during the poll loop (only on startup)
- Cleaning up worktrees from OTHER projects

### Requirement: Clean orphaned worktrees on startup

The orchestrator SHALL detect and remove worktrees that exist on disk but have no corresponding change entry in the orchestration state, or whose change is already merged/done.

#### Scenario: Worktree exists but no state entry
- **WHEN** the orchestrator starts
- **AND** a worktree directory `<project>-wt-<name>` exists
- **AND** no change named `<name>` exists in orchestration-state.json
- **THEN** the worktree is removed via `git worktree remove --force`
- **AND** the orphaned branch `change/<name>` is deleted
- **AND** a log message is emitted: "Removed orphaned worktree: <name>"

#### Scenario: Worktree exists for merged change
- **WHEN** a change has status `merged` or `done`
- **AND** its worktree directory still exists on disk
- **AND** the worktree has no uncommitted changes (git status clean)
- **THEN** the worktree is removed
- **AND** a log message is emitted

#### Scenario: Worktree has uncommitted changes
- **WHEN** a worktree exists for a merged/done change
- **AND** `git status --porcelain` in the worktree returns non-empty output
- **THEN** the worktree is NOT removed
- **AND** a warning is logged: "Skipping dirty worktree: <name> (has uncommitted changes)"

#### Scenario: Worktree belongs to active change
- **WHEN** a worktree exists for a change with status `running`, `pending`, or `dispatched`
- **THEN** the worktree is NOT touched
- **AND** no log message is emitted

### Requirement: Fix stale ralph_pid references

The orchestrator SHALL detect and clear ralph_pid values that reference dead processes.

#### Scenario: ralph_pid points to dead process
- **WHEN** a change has `ralph_pid` set to a numeric value
- **AND** `kill -0 <pid>` returns non-zero (process dead)
- **THEN** `ralph_pid` is set to None in the state
- **AND** if change status is `merged` or `done`, `current_step` is set to `done`
- **AND** a log message is emitted: "Cleared stale PID <pid> for <name>"

#### Scenario: ralph_pid points to live process
- **WHEN** a change has `ralph_pid` set
- **AND** `kill -0 <pid>` returns zero (process alive)
- **THEN** the PID is NOT cleared
- **AND** no changes are made to the state

#### Scenario: ralph_pid for running change with dead process
- **WHEN** a change has status `running` and `ralph_pid` pointing to a dead process
- **THEN** `ralph_pid` is cleared
- **AND** status is changed to `stalled` (sentinel recovery will handle redispatch)
- **AND** a log message is emitted: "Change <name> stalled (PID <pid> dead)"

### Requirement: Fix stuck current_step values

The orchestrator SHALL fix current_step values that are inconsistent with change status.

#### Scenario: Merged change with non-done step
- **WHEN** a change has status `merged`
- **AND** `current_step` is not `done` (e.g., `integrating`, `merging`, `fixing`)
- **THEN** `current_step` is set to `done`
- **AND** a log message is emitted: "Fixed stuck step for <name>: <old_step> → done"

#### Scenario: Done change with non-done step
- **WHEN** a change has status `done`
- **AND** `current_step` is not `done`
- **THEN** `current_step` is set to `done`

#### Scenario: Running change with valid step
- **WHEN** a change has status `running`
- **AND** `current_step` is `planning`, `fixing`, or `integrating`
- **THEN** no changes are made (these are valid intermediate steps)

### Requirement: Conservative safety rules

The cleanup SHALL follow conservative rules to avoid destroying useful state.

#### Scenario: Never kill processes
- **WHEN** an orphaned worktree has a running process in its directory
- **THEN** the worktree is NOT removed
- **AND** a warning is logged: "Skipping worktree <name>: process running in directory"

#### Scenario: Log all actions
- **WHEN** any cleanup action is taken (worktree removal, PID clear, step fix)
- **THEN** the action is logged at INFO level with the change name and details
- **AND** a summary line at the end: "Orphan cleanup: N worktrees removed, M PIDs cleared, K steps fixed"

#### Scenario: No cleanup needed
- **WHEN** the orchestrator starts
- **AND** no orphaned resources are detected
- **THEN** no state modifications are made
- **AND** a debug message is logged: "Orphan cleanup: nothing to clean"
