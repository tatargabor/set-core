# Loop Stall Recovery Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Per-Iteration Timeout
The system SHALL enforce a maximum duration per iteration to prevent stuck iterations from running indefinitely.

#### Scenario: Iteration exceeds timeout
- **WHEN** a loop iteration has been running longer than the configured timeout (default 45 minutes)
- **THEN** the Claude process SHALL be sent SIGTERM
- **AND** the iteration SHALL be recorded with `"timed_out": true`
- **AND** the loop SHALL continue to the next iteration with fresh context

#### Scenario: Iteration completes within timeout
- **WHEN** a loop iteration completes before the timeout
- **THEN** the iteration SHALL be recorded normally with `"timed_out": false` or field omitted

#### Scenario: Timeout is configurable
- **WHEN** user starts a loop with `--iteration-timeout N` (minutes)
- **THEN** each iteration SHALL use N minutes as the timeout
- **AND** the value SHALL be stored in `loop-state.json` as `iteration_timeout_min`

### Requirement: Time-Based Stall Detection
The system SHALL detect when an iteration runs excessively long without producing commits, independent of the cross-iteration stall counter.

#### Scenario: Long iteration with no progress
- **WHEN** an iteration has been running for more than 30 minutes
- **AND** no new commits have been detected since the iteration started
- **THEN** the loop status SHALL be updated to "stuck"
- **AND** a warning SHALL be logged

### Requirement: Configurable Stall Threshold
The system SHALL allow users to configure how many consecutive commit-less iterations trigger a stall.

#### Scenario: Custom stall threshold via CLI
- **WHEN** user starts a loop with `--stall-threshold N`
- **THEN** the loop SHALL wait for N consecutive commit-less iterations before declaring "stalled"
- **AND** the default SHALL be 2 (changed from 1)

#### Scenario: Stall threshold stored in state
- **WHEN** a loop starts with a stall threshold
- **THEN** the value SHALL be stored in `loop-state.json` as `stall_threshold`
