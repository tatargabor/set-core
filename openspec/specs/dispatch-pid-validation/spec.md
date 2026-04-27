# Dispatch Pid Validation Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Validate terminal_pid is a positive integer before marking a change as "running"
- Log errors when loop-state.json parsing fails instead of silently swallowing
- Watchdog fast-path escalation for running changes with null/zero PID

### Out of scope
- Changing the set-loop startup mechanism itself
- Modifying how loop-state.json is written by set-loop
- Changing the reconciliation logic in recover_orphaned_changes()

## Requirements

### Requirement: Dispatch PID validation
The dispatcher SHALL validate that `terminal_pid` extracted from `loop-state.json` is a positive integer (> 0) before marking a change as "running". If the PID is 0, null, or invalid, the dispatcher SHALL mark the change as "failed" and return False.

#### Scenario: Valid PID in loop-state.json
- **WHEN** `loop-state.json` contains a valid `terminal_pid` (positive integer)
- **THEN** the change is marked as "running" with the correct `ralph_pid` value

#### Scenario: Missing terminal_pid field
- **WHEN** `loop-state.json` exists but lacks the `terminal_pid` field
- **THEN** the dispatcher marks the change as "failed" and logs an error

#### Scenario: Null terminal_pid value
- **WHEN** `loop-state.json` contains `"terminal_pid": null`
- **THEN** the dispatcher marks the change as "failed" and logs an error

#### Scenario: JSON parse failure
- **WHEN** `loop-state.json` exists but contains invalid JSON
- **THEN** the dispatcher marks the change as "failed" and logs the parse error (not silently swallowed)

### Requirement: Watchdog null-PID fast-path
The watchdog SHALL immediately escalate any change with `status="running"` and `ralph_pid` of 0 or null, without waiting for the normal timeout threshold.

#### Scenario: Running change with zero PID
- **WHEN** watchdog checks a change with `status="running"` and `ralph_pid=0`
- **THEN** watchdog immediately triggers escalation (should_escalate=True) with reason indicating invalid PID

#### Scenario: Running change with valid PID
- **WHEN** watchdog checks a change with `status="running"` and a positive `ralph_pid`
- **THEN** watchdog follows normal timeout/loop-detection logic (no change to existing behavior)
