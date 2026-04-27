# Stale Lock Recovery Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Sentinel flock fd not inherited by child orchestrator process
- Sentinel lock released when sentinel exits, regardless of child process state

### Out of scope
- Changing the flock mechanism to a different locking strategy
- PID file management (already handled in prior fix)

## Requirements

### Requirement: Close flock fd in child process
<!-- REQ-FLOCK-FD -->
The sentinel MUST close its flock file descriptor (fd 9) before spawning the orchestrator child process so that the lock is not inherited.

#### Scenario: Sentinel crashes while orchestrator runs
- **WHEN** the sentinel process dies unexpectedly (SIGKILL, OOM, etc.) while the orchestrator child is still running
- **THEN** the flock on `sentinel.lock` SHALL be released (because the only fd 9 holder — the sentinel — is dead)
- **AND** a new sentinel instance SHALL be able to acquire the lock immediately

#### Scenario: Normal sentinel restart
- **WHEN** the sentinel receives SIGTERM and forwards it to the orchestrator
- **THEN** after both processes exit, the lock file SHALL not remain locked
- **AND** the next sentinel start SHALL succeed without stale lock recovery
