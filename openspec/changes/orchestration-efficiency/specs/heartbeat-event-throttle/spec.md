## ADDED Requirements

### Requirement: Heartbeat event throttle
The monitor loop must throttle `WATCHDOG_HEARTBEAT` events written to the event bus to reduce log noise.

#### Scenario: Normal polling
- **WHEN** the monitor loop polls every ~15 seconds
- **THEN** `WATCHDOG_HEARTBEAT` events are emitted at most once every 20 poll cycles (~5 minutes)
- **AND** internal heartbeat logic (liveness detection, idle escalation) continues to run every cycle unchanged

#### Scenario: First heartbeat after startup
- **WHEN** the monitor loop starts or resumes after checkpoint
- **THEN** the first heartbeat event is emitted immediately (no initial delay)

### Requirement: Sentinel liveness unaffected
The heartbeat throttle must not affect sentinel stuck detection.

#### Scenario: Sentinel stuck detection still works
- **WHEN** the sentinel checks for orchestrator liveness
- **THEN** it uses process-level checks (PID alive) and state file modification time
- **AND** does not depend on heartbeat event frequency in events.jsonl
