## ADDED Requirements

### Requirement: Memory audit periodic health check
The orchestrator SHALL run `orch_memory_audit()` periodically during the monitor loop (approximately every 10 poll cycles). The audit SHALL check set-memory health, count orchestrator memories, and spot-check the latest memory content. Warnings SHALL be logged if memories are missing or the memory system is unhealthy.

#### Scenario: Memory system healthy
- **WHEN** orch_memory_audit runs and set-memory health returns OK
- **THEN** the audit SHALL log memory count and pass silently

#### Scenario: Memory system unhealthy
- **WHEN** set-memory health fails or memory count is 0
- **THEN** the audit SHALL log a warning but NOT block orchestration

## MODIFIED Requirements

### Requirement: Stall memory save timing
WHEN `poll_change()` detects a stalled/stuck change on the FINAL failure (stall_count exceeds max retries), the orchestrator SHALL call `orch_remember` with details about the failure. The memory save fires when the change is marked as "failed" (the give-up branch), not on the last retry attempt.

#### Scenario: Change fails after max stall retries
- **WHEN** stall_count exceeds 3 (the give-up threshold)
- **THEN** orch_remember SHALL be called with the change name and failure details before setting status to "failed"
