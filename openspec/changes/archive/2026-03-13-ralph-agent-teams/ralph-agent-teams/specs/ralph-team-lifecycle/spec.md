## ADDED Requirements

### Requirement: Inter-iteration team cleanup
The Ralph engine SHALL instruct Claude to clean up teams (TeamDelete) before finishing each iteration. The prompt MUST include explicit cleanup instructions.

#### Scenario: Normal iteration end
- **WHEN** Claude finishes an iteration that used Agent Teams
- **THEN** the prompt instructs Claude to call TeamDelete and send shutdown_request to all teammates before exiting

#### Scenario: Iteration timeout during team work
- **WHEN** an iteration times out while teammates are still running
- **THEN** the engine's existing cleanup_on_exit trap handles process termination; orphan team state files are cleaned up at next iteration start

### Requirement: Orphan team detection at iteration start
The team instructions SHALL include a preamble at each iteration start that checks for leftover team files from a previous interrupted iteration and cleans them up.

#### Scenario: Previous iteration left orphan team
- **WHEN** a new iteration starts and `~/.claude/teams/` contains team files from a previous Ralph iteration
- **THEN** the prompt instructs Claude to delete any leftover teams before starting new work

### Requirement: Graceful teammate shutdown
The team instructions SHALL specify that the team lead MUST send `shutdown_request` to each teammate and wait for `shutdown_response` before calling TeamDelete. This prevents data loss from in-progress teammate work.

#### Scenario: Teammate still working
- **WHEN** team lead sends shutdown_request to a teammate that hasn't finished
- **THEN** the teammate rejects the shutdown with reason, and the team lead waits for completion before retrying

#### Scenario: All teammates idle
- **WHEN** all teammates have completed their tasks and are idle
- **THEN** the team lead sends shutdown_request to each, receives approval, then calls TeamDelete
