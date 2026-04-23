## ADDED Requirements

### Requirement: Tick loop includes DIAGNOSED-stall watchdog

`IssueManager.tick()` SHALL call `_check_diagnosed_stalls()` on every tick cycle, alongside the existing `_check_timeout_reminders()` pass.

#### Scenario: Tick sequence includes the watchdog
- **WHEN** `tick()` runs
- **THEN** the method SHALL call `_check_diagnosed_stalls()` at least once per invocation
- **AND** the call SHALL occur after the `_process(issue)` loop so freshly-transitioned issues are evaluated by the watchdog on the NEXT tick (not the same tick that transitioned them)

#### Scenario: Watchdog errors do not break tick
- **WHEN** `_check_diagnosed_stalls` raises an unexpected exception
- **THEN** the exception SHALL be caught and logged at WARN
- **AND** the remainder of the tick (including `_check_timeout_reminders`) SHALL still run
