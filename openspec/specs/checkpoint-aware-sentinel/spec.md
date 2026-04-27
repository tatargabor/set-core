# Checkpoint Aware Sentinel Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: sentinel-skips-stuck-detection-during-checkpoint
The sentinel's `check_orchestrator_liveness()` must not report the orchestrator as stuck when the orchestration state is `checkpoint`, but must enforce a maximum checkpoint wait duration.

#### Scenario: orchestrator waiting for checkpoint approval
- **WHEN** the orchestration state file has `status == "checkpoint"` and the orchestrator process is alive and checkpoint age is below `CHECKPOINT_MAX_WAIT` (default: 86400s / 24h)
- **THEN** `check_orchestrator_liveness()` returns 0 (not stuck), regardless of event/state file mtime staleness

#### Scenario: checkpoint wait exceeded maximum duration
- **WHEN** the orchestration state is `checkpoint` and the checkpoint has been active for longer than `CHECKPOINT_MAX_WAIT`
- **THEN** `check_orchestrator_liveness()` returns 1 (stuck) and the sentinel kills the orchestrator and stops with a log message indicating checkpoint timeout

#### Scenario: orchestrator genuinely stuck (not checkpoint)
- **WHEN** the orchestration state is `running` and no events have been produced for longer than `SENTINEL_STUCK_TIMEOUT`
- **THEN** `check_orchestrator_liveness()` returns 1 (stuck) and the sentinel kills and restarts the orchestrator — existing behavior unchanged

#### Scenario: checkpoint with dead orchestrator process
- **WHEN** the orchestration state is `checkpoint` but the orchestrator PID is no longer alive
- **THEN** `fix_stale_state()` preserves checkpoint status (existing behavior), the sentinel restarts the orchestrator which resumes from checkpoint. Any changes that were `running` when the orchestrator died are marked `stalled` by `fix_stale_state()` — the resumed orchestrator must handle stalled changes during checkpoint processing.

#### Scenario: state file unreadable during liveness check
- **WHEN** the state file exists but `jq` fails to parse it (torn read, I/O error)
- **THEN** `check_orchestrator_liveness()` returns 0 (not stuck) — failing safe by skipping the kill rather than proceeding with it
