## ADDED Requirements

### Requirement: Throttle hash_loop_pid_alive event emission
The watchdog MUST throttle `WATCHDOG_WARN` event emission for `hash_loop_pid_alive` reason to match the existing log throttle. Events should only be emitted at the threshold crossing and then every Nth occurrence, not on every poll cycle.

#### Scenario: Agent working on long iteration (PID alive, hash unchanged for 200 poll cycles)
- **WHEN** the watchdog detects 200 consecutive identical hashes with a live PID
- **THEN** it emits ~10 WATCHDOG_WARN events (at threshold + every 20th) instead of 200

#### Scenario: Agent actually stuck (PID dead, hash unchanged)
- **WHEN** the watchdog detects consecutive identical hashes with a dead PID
- **THEN** escalation behavior is unchanged — full event emission and escalation proceed normally
