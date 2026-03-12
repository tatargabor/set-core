## MODIFIED Requirements

### Requirement: Monitor loop polling — active time includes verify phase
The orchestrator's active time tracker SHALL count verify phases as active work.

#### Scenario: Timer increments during verify
- **WHEN** a change has status `verifying` (build, test, or E2E running)
- **THEN** `any_loop_active()` SHALL return true
- **AND** `active_seconds` SHALL increment by `POLL_INTERVAL`

#### Scenario: Timer increments during normal Ralph work
- **WHEN** a change has status `running` and loop-state.json mtime is less than 5 minutes old
- **THEN** `any_loop_active()` SHALL return true (existing behavior, unchanged)

#### Scenario: Timer does not increment when all work is idle
- **WHEN** no change has status `running` with recent loop-state.json AND no change has status `verifying`
- **THEN** `any_loop_active()` SHALL return false
- **AND** `active_seconds` SHALL NOT increment
