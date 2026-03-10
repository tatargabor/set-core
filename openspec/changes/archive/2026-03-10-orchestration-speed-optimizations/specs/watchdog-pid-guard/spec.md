## ADDED Requirements

### Requirement: Hash loop detection respects PID-alive status
The watchdog hash loop detection SHALL check whether the Ralph PID is alive before escalating, matching the behavior of timeout detection.

#### Scenario: Healthy agent with identical hashes
- **WHEN** consecutive same hash count reaches WATCHDOG_LOOP_THRESHOLD AND the Ralph PID is alive
- **THEN** the watchdog SHALL log a warning but NOT escalate (no kill/resume)

#### Scenario: Dead agent with identical hashes
- **WHEN** consecutive same hash count reaches WATCHDOG_LOOP_THRESHOLD AND the Ralph PID is dead
- **THEN** the watchdog SHALL escalate as before (warn → resume → kill → fail)

#### Scenario: Warning visibility
- **WHEN** a hash loop is detected but PID is alive
- **THEN** the watchdog SHALL emit a WATCHDOG_WARN event so the TUI and logs show the condition
