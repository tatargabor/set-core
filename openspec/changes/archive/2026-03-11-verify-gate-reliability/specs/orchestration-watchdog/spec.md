## MODIFIED Requirements

### Requirement: Hash loop PID-alive log level (MODIFIED)
When hash loop detection finds the Ralph PID is still alive, the system SHALL log at DEBUG level instead of WARN.

#### Scenario: PID alive during hash loop
- **WHEN** `watchdog_loop_threshold` consecutive identical hashes are detected
- **AND** the Ralph PID for that change is alive (`kill -0` succeeds)
- **THEN** the watchdog SHALL log at DEBUG level: "hash loop (N identical hashes) but PID alive — skipping escalation"
- **AND** SHALL still emit `WATCHDOG_WARN` event to events JSONL (audit trail preserved)
- **AND** SHALL still apply the throttle (log at threshold, then every 20th occurrence)

#### Scenario: PID dead during hash loop (unchanged)
- **WHEN** `watchdog_loop_threshold` consecutive identical hashes are detected
- **AND** the Ralph PID is dead
- **THEN** the watchdog SHALL log at WARN level (unchanged behavior)
- **AND** SHALL trigger escalation (unchanged behavior)
