## ADDED Requirements

### Requirement: The watchdog itself is checked
`set-doctor` SHALL report a `watchdog` record. It is `ok` when the `set-watchdog.timer` user unit
is enabled and active and the last tick is no older than three intervals. It is `warn` with the
install command as its fix when the timer is not installed. It is `fail` when the timer is installed
but the last tick is stale, and its detail names the last tick time. The record MUST NOT run a tick.

#### Scenario: Timer installed but ticks stopped
- **WHEN** the timer unit is enabled and the tick log's last line is two hours old with a 5-minute interval
- **THEN** the `watchdog` record is `fail` and its detail names the last tick time

#### Scenario: Not installed
- **WHEN** no `set-watchdog.timer` unit exists
- **THEN** the `watchdog` record is `warn` and its fix names the install command
