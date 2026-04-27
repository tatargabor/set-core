# Dispatch Lifecycle Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Pause a running change
The system SHALL send SIGTERM to the Ralph terminal PID (after identity verification via process.check_pid) and set change status to "paused".

#### Scenario: Pause running change
- **WHEN** pause_change is called for a change with a live Ralph PID
- **THEN** SIGTERM is sent to the PID and status is set to "paused"

#### Scenario: Pause with no PID file
- **WHEN** no worktree path exists for the change
- **THEN** function returns failure with warning

### Requirement: Resume a paused or stopped change
The system SHALL snapshot cumulative token counts (tokens_used → tokens_used_prev, per-type tokens), set watchdog progress baseline, determine done criteria (openspec/build/merge based on retry_context), resolve model, and start set-loop with appropriate --max iterations.

#### Scenario: Resume with retry context (build fix)
- **WHEN** change has retry_context and merge_rebase_pending is false
- **THEN** set-loop starts with --done build --max 3 using retry_context as task description

#### Scenario: Resume with retry context (merge conflict)
- **WHEN** change has retry_context and merge_rebase_pending is true
- **THEN** set-loop starts with --done merge --max 5

#### Scenario: Resume without retry context
- **WHEN** change has no retry_context
- **THEN** set-loop starts with --done openspec --max 30 using "Continue <name>: <scope>" as task

#### Scenario: Token accumulation across resumes
- **WHEN** a change is resumed
- **THEN** current tokens_used is stored as tokens_used_prev so new loop tokens add to cumulative total

### Requirement: Resume stopped changes on restart
The system SHALL iterate changes with status "stopped", resume those with existing worktrees, and reset those without worktrees to "pending".

#### Scenario: Stopped change with worktree
- **WHEN** orchestrator restarts and a stopped change has its worktree intact
- **THEN** the change is resumed via resume_change

#### Scenario: Stopped change without worktree
- **WHEN** a stopped change's worktree no longer exists
- **THEN** status is reset to "pending" for fresh dispatch

### Requirement: Resume stalled changes after cooldown
The system SHALL resume stalled changes after a 5-minute cooldown period (300 seconds since stalled_at timestamp).

#### Scenario: Stalled change after cooldown
- **WHEN** a change has been stalled for >= 300 seconds
- **THEN** it is resumed via resume_change

#### Scenario: Stalled change within cooldown
- **WHEN** a change has been stalled for < 300 seconds
- **THEN** it is not resumed (still cooling down)
