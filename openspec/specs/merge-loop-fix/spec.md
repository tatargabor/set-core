# Merge Loop Fix Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Recovery logic resets ff_retry_count when recovering merge-blocked → done
- Recovery logic increments merge_retry_count to bound total recovery attempts
- Logging of recovery state resets for observability

### Out of scope
- Changing the ff_retry or merge_retry limits (remain at 3)
- Modifying the monitor's orphaned-done re-queue logic (already has merge_retry_count guard)
- Modifying the merger's FF merge command construction

## Requirements

### Requirement: Recovery resets FF retry state

When recovering a merge-blocked change back to done, the engine SHALL reset `ff_retry_count` to 0 so the change re-enters the merge pipeline with a fresh set of FF retry attempts and full integration gate execution.

#### Scenario: Recovery resets ff_retry_count
- **WHEN** `_recover_merge_blocked_safe` transitions a change from `merge-blocked` to `done`
- **THEN** it SHALL set `ff_retry_count` to 0 in the change extras
- **AND** it SHALL log the reset at INFO level with the change name

### Requirement: Recovery increments merge retry counter

Each recovery from merge-blocked SHALL increment `merge_retry_count` by 1 so the monitor's existing `merge_retry_count >= 3` guard eventually transitions the change to `integration-failed` (terminal state).

#### Scenario: Recovery increments merge_retry_count
- **WHEN** `_recover_merge_blocked_safe` transitions a change from `merge-blocked` to `done`
- **THEN** it SHALL increment `merge_retry_count` by 1 in the change extras

#### Scenario: Loop terminates after bounded recoveries
- **WHEN** a change has been recovered from merge-blocked 3 times
- **AND** the monitor finds it as an orphaned done change with `merge_retry_count >= 3`
- **THEN** the monitor SHALL transition it to `integration-failed` (existing behavior)
- **AND** the loop SHALL NOT continue
