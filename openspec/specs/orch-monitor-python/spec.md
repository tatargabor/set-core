# Orch Monitor Python Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Python monitor loop as live engine
The system SHALL execute the orchestration monitor loop via Python (`engine.py:monitor_loop()`) when `ORCH_ENGINE=python` is set (or when it becomes the default). The Python monitor loop SHALL provide identical behavior to the bash `monitor_loop()` in `monitor.sh`.

#### Scenario: Python monitor loop starts via cmd_start
- **WHEN** `cmd_start()` is called with `ORCH_ENGINE=python` (or default after cutover)
- **THEN** bash `cmd_start()` SHALL exec `set-orch-core engine monitor --directives <json> --state <file> --poll-interval <int>`
- **AND** the Python process SHALL replace the bash process (via exec)

#### Scenario: Feature flag selects engine
- **WHEN** `ORCH_ENGINE=bash` is set
- **THEN** `cmd_start()` SHALL call bash `monitor_loop()` as before
- **WHEN** `ORCH_ENGINE=python` is set (or env var is absent after default flip)
- **THEN** `cmd_start()` SHALL exec to Python monitor

### Requirement: Signal handling in Python monitor
The Python monitor process SHALL handle SIGTERM, SIGINT, and SIGHUP signals and perform cleanup before exit.

#### Scenario: SIGTERM received during monitoring
- **WHEN** the Python monitor process receives SIGTERM
- **THEN** it SHALL update orchestration state status to "stopped" (unless already "done")
- **AND** it SHALL pause running changes if `pause_on_exit` directive is set
- **AND** it SHALL exit cleanly with code 0

#### Scenario: SIGINT received during monitoring
- **WHEN** the Python monitor process receives SIGINT (Ctrl+C)
- **THEN** it SHALL perform the same cleanup as SIGTERM
- **AND** it SHALL exit cleanly

#### Scenario: Cleanup on normal exit
- **WHEN** the Python monitor loop exits normally (all changes done)
- **THEN** it SHALL kill any auto-started dev server PIDs
- **AND** it SHALL generate a final report

### Requirement: Python monitor sends notifications
The Python monitor loop SHALL send desktop and email notifications at the same points as the bash version.

#### Scenario: Completion notification
- **WHEN** all changes reach terminal status
- **THEN** the Python monitor SHALL call `notifications.send_notification()` with completion summary

#### Scenario: Summary email on completion
- **WHEN** orchestration completes (done, time_limit, or replan exhausted)
- **THEN** the Python monitor SHALL call `notifications.send_summary_email()` with state summary and coverage report

### Requirement: Python monitor triggers checkpoints
The Python monitor loop SHALL support interactive checkpoint gates.

#### Scenario: Periodic checkpoint
- **WHEN** `checkpoint_every` directive is set and `changes_since_checkpoint >= checkpoint_every`
- **THEN** the Python monitor SHALL update state status to "checkpoint" and pause the loop until status changes

#### Scenario: Token hard limit checkpoint
- **WHEN** cumulative tokens exceed `token_hard_limit`
- **THEN** the Python monitor SHALL trigger a checkpoint with reason "token_hard_limit"

### Requirement: Python monitor performs memory operations
The Python monitor loop SHALL call memory audit and stats at the same intervals as bash.

#### Scenario: Periodic memory audit
- **WHEN** poll count is a multiple of 10 (approximately every 2.5 minutes)
- **THEN** the Python monitor SHALL call `orch_memory.orch_memory_stats()`, `orch_memory.orch_gate_stats()`, and `orch_memory.orch_memory_audit()`

### Requirement: Python monitor emits watchdog heartbeat
The Python monitor SHALL emit a WATCHDOG_HEARTBEAT event on each poll cycle so the sentinel can detect monitor liveness.

#### Scenario: Heartbeat emission
- **WHEN** a poll cycle completes
- **THEN** the Python monitor SHALL call `event_bus.emit("WATCHDOG_HEARTBEAT")`

### Requirement: Python monitor handles coverage checks
The Python monitor SHALL perform final coverage validation before marking orchestration complete.

#### Scenario: Final coverage check on completion
- **WHEN** orchestration reaches terminal state (done, time_limit)
- **THEN** the Python monitor SHALL call `digest.final_coverage_check()` and include the result in the summary email
