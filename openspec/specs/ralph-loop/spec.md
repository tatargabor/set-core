## Requirements

### Requirement: Ralph loop state file format
The Ralph loop SHALL write state to `<worktree>/.claude/loop-state.json` with a documented, stable format for MCP consumption.

#### Scenario: State file location
- **WHEN** Ralph loop starts
- **THEN** creates/updates `.claude/loop-state.json` in worktree root
- **AND** file is worktree-scoped (not global)

#### Scenario: State file schema
- **WHEN** Ralph writes loop-state.json
- **THEN** JSON includes required fields:
  - `change_id`: string - the change identifier
  - `status`: string - one of "starting", "running", "done", "stuck", "stalled", "stopped", "waiting:human", "waiting:budget"
  - `current_iteration`: number - current iteration (1-based)
  - `max_iterations`: number - configured maximum
  - `started_at`: string - ISO 8601 timestamp
  - `task`: string - the task description
  - `iterations`: array - history of completed iterations
  - `done_criteria`: string - "tasks", "openspec", or "manual"
  - `stall_threshold`: number - consecutive commit-less iterations before stall
  - `iteration_timeout_min`: number - per-iteration timeout in minutes
  - `total_tokens`: number - cumulative token count across all iterations
  - `label`: string or null - optional user-provided label for loop identification
  - `session_id`: string or null - Claude session UUID for resume
  - `resume_failures`: number - count of `--resume` failures (default 0)

#### Scenario: Iteration history entry
- **WHEN** Ralph completes an iteration
- **THEN** adds entry to `iterations` array with:
  - `n`: number - iteration number
  - `started`: string - ISO timestamp
  - `ended`: string - ISO timestamp
  - `done_check`: boolean - whether done criteria met
  - `commits`: array - commit hashes made
  - `tokens_used`: number - tokens consumed this iteration
  - `timed_out`: boolean - whether iteration was killed by timeout (optional, only if true)
  - `no_op`: boolean - whether iteration produced no meaningful work (optional, only if true)
  - `ff_exhausted`: boolean - whether ff retry limit was exceeded (optional, only if true)
  - `ff_recovered`: boolean - whether fallback tasks.md was generated (optional, only if true)
  - `log_file`: string - path to per-iteration log file
  - `resumed`: boolean - whether this iteration used `--resume` (optional, only if true)

### Requirement: Universal done detection safety net
The Ralph loop SHALL have a fallback done check that catches completion regardless of the primary `done_criteria` setting.

#### Scenario: Tasks.md all-checked fallback triggers
- **WHEN** the primary done criteria check (`check_done`) returns false
- **AND** a `tasks.md` file exists in the worktree or change directory
- **AND** all `- [ ]` tasks are checked off (zero unchecked auto-tasks)
- **THEN** the loop SHALL treat the change as done
- **AND** log a warning: "Done by tasks.md fallback (primary criteria '{type}' said not done)"

#### Scenario: Fallback does not override primary when tasks remain
- **WHEN** the primary done criteria check returns false
- **AND** `tasks.md` has unchecked `- [ ]` tasks
- **THEN** the fallback SHALL NOT trigger
- **AND** the loop SHALL continue normally

#### Scenario: Fallback does not fire when no tasks.md exists
- **WHEN** no `tasks.md` file exists
- **THEN** the fallback SHALL NOT trigger
- **AND** only the primary done criteria SHALL be evaluated
