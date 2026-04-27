# Execution Model Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Orchestration entry point
The `set-orchestrate start` command SHALL initialize orchestration state and launch the monitor loop. When `ORCH_ENGINE=python` (or after default cutover), `cmd_start()` SHALL exec to `set-orch-core engine monitor` instead of calling bash `monitor_loop()`.

#### Scenario: Python engine exec
- **WHEN** `cmd_start()` detects `ORCH_ENGINE=python` (or default after cutover)
- **AND** state initialization and initial dispatch are complete
- **THEN** `cmd_start()` SHALL exec `set-orch-core engine monitor --directives <path> --state <path> --poll-interval <int>`
- **AND** the exec SHALL replace the bash process (Python becomes PID owner)

#### Scenario: Bash engine fallback
- **WHEN** `cmd_start()` detects `ORCH_ENGINE=bash`
- **THEN** `cmd_start()` SHALL call bash `monitor_loop()` as before (backward compatible)

#### Scenario: Resume with Python engine
- **WHEN** `cmd_start()` detects a stopped/time_limit state and `ORCH_ENGINE=python`
- **THEN** it SHALL perform recovery (orphan detection, merge queue retry, resume stopped)
- **AND** THEN exec to Python monitor loop
