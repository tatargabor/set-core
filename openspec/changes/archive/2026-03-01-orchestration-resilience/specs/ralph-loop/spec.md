## MODIFIED Requirements

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
  - `status`: string - one of "starting", "running", "done", "stuck", "stalled", "stopped", "budget_exceeded", "waiting:human"
  - `current_iteration`: number - current iteration (1-based)
  - `max_iterations`: number - configured maximum
  - `started_at`: string - ISO 8601 timestamp
  - `task`: string - the task description
  - `iterations`: array - history of completed iterations
  - `done_criteria`: string - "tasks", "openspec", or "manual"
  - `stall_threshold`: number - consecutive commit-less iterations before stall
  - `iteration_timeout_min`: number - per-iteration timeout in minutes
  - `total_tokens`: number - cumulative token count across all iterations
  - `token_budget`: number - max token budget (0 = unlimited)
  - `label`: string or null - optional user-provided label for loop identification
  - `ff_attempts`: number - consecutive failed ff attempts for current change

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

### Requirement: Default done criteria
The Ralph loop SHALL default to `tasks` done criteria instead of `manual`.

#### Scenario: Default done criteria with tasks.md present
- **WHEN** user starts a loop without `--done` flag
- **AND** a `tasks.md` file exists in the change directory or worktree
- **THEN** done criteria SHALL be "tasks"

#### Scenario: Default done criteria without tasks.md
- **WHEN** user starts a loop without `--done` flag
- **AND** no `tasks.md` file exists
- **THEN** done criteria SHALL fall back to "manual"
- **AND** a warning SHALL be displayed: "No tasks.md found, using manual done criteria"

#### Scenario: Explicit manual override
- **WHEN** user starts a loop with `--done manual`
- **THEN** done criteria SHALL be "manual" regardless of tasks.md presence
