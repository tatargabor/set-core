# Watchdog Redispatch Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Redispatch stuck changes to fresh worktrees

When a change is detected as stuck (watchdog escalation L3 or spinning detection), the system SHALL automatically re-dispatch it to a fresh worktree instead of marking it as failed, up to a configurable `max_redispatch` limit.

#### Scenario: L3 escalation triggers redispatch on first stuck detection
- **WHEN** watchdog escalates a change to level 3 AND `redispatch_count` is less than `max_redispatch`
- **THEN** the system SHALL kill the Ralph PID, salvage partial work, clean up the old worktree, set the change status to `pending`, and increment `redispatch_count`

#### Scenario: L3 escalation triggers fail after max redispatches exhausted
- **WHEN** watchdog escalates a change to level 3 AND `redispatch_count` equals or exceeds `max_redispatch`
- **THEN** the system SHALL salvage partial work and mark the change as `failed`

#### Scenario: Spinning detection triggers redispatch
- **WHEN** `_watchdog_check_progress()` detects the spinning pattern (3+ consecutive no_op iterations) AND `redispatch_count` is less than `max_redispatch`
- **THEN** the system SHALL kill the Ralph PID, salvage partial work, clean up the old worktree, set the change status to `pending`, and increment `redispatch_count`

#### Scenario: Spinning detection triggers fail after max redispatches
- **WHEN** `_watchdog_check_progress()` detects spinning AND `redispatch_count` equals or exceeds `max_redispatch`
- **THEN** the system SHALL salvage partial work and mark the change as `failed`

### Requirement: Forward failure context to fresh agent

When a change is re-dispatched, the system SHALL build a `retry_context` string and store it in state.json so the fresh agent receives information about what went wrong.

#### Scenario: Retry context includes failure reason and partial work summary
- **WHEN** a change is re-dispatched
- **THEN** the `retry_context` field SHALL contain the failure pattern (spinning/stuck/timeout), the list of files modified in the failed attempt, the iteration count, and total tokens used

#### Scenario: Retry context is injected into the fresh dispatch proposal
- **WHEN** `dispatch_change()` processes a change that has a non-empty `retry_context`
- **THEN** the proposal text SHALL include the retry context so the agent knows what was previously attempted

### Requirement: Clean up old worktree before re-dispatch

When re-dispatching, the system SHALL remove the old worktree and branch to free resources and avoid conflicts.

#### Scenario: Old worktree is removed after salvage
- **WHEN** the system prepares to re-dispatch a change
- **THEN** it SHALL call worktree cleanup (removing the directory and the git branch) after salvaging partial work

#### Scenario: Stale branch cleanup on re-dispatch
- **WHEN** the old worktree's branch still exists after cleanup
- **THEN** `dispatch_change()` SHALL remove the stale branch before creating a new worktree (existing behavior)

### Requirement: Configurable max_redispatch limit

The maximum number of redispatch attempts SHALL be configurable via the `max_redispatch` directive in orchestration.yaml.

#### Scenario: Default max_redispatch is 2
- **WHEN** no `max_redispatch` directive is set in orchestration.yaml
- **THEN** the system SHALL use a default value of 2

#### Scenario: Custom max_redispatch from config
- **WHEN** `max_redispatch` is set to N in orchestration.yaml directives
- **THEN** the system SHALL allow up to N redispatch attempts per change

### Requirement: State tracking for redispatch count

Each change in state.json SHALL have a `redispatch_count` field tracking how many times it has been re-dispatched.

#### Scenario: Initial redispatch_count is zero
- **WHEN** a change is initialized in state.json
- **THEN** `redispatch_count` SHALL be 0

#### Scenario: Redispatch count increments on each re-dispatch
- **WHEN** a change is re-dispatched
- **THEN** `redispatch_count` SHALL increment by 1

#### Scenario: Redispatch count survives status transitions
- **WHEN** a re-dispatched change moves through pending → dispatched → running
- **THEN** `redispatch_count` SHALL retain its value

### Requirement: Event logging for redispatch activity

The system SHALL emit events for redispatch actions to enable post-run diagnostics.

#### Scenario: WATCHDOG_REDISPATCH event on re-dispatch
- **WHEN** a change is re-dispatched
- **THEN** the system SHALL emit a `WATCHDOG_REDISPATCH` event with the change name, redispatch count, failure pattern, and tokens used in the failed attempt

### Requirement: Status output shows redispatch info

The orchestrator status display SHALL show redispatch count for changes that have been re-dispatched.

#### Scenario: Status shows redispatch count for active changes
- **WHEN** a change has `redispatch_count > 0` and the user views orchestrator status
- **THEN** the status output SHALL include the redispatch count (e.g., "running (redispatch 1/2)")
