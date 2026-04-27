# Ralph Team Lifecycle Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

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

