## IN SCOPE
- WARNING-level use by long-running set-core services (the dashboard, the agent owner) and hooks
- A measured sweep: WARNING lines per service per day, the top messages, and each fix's proof

## OUT OF SCOPE
- Log storage, rotation and archiving (existing log capabilities)
- Consumer projects' own logging

## ADDED Requirements

### Requirement: A normal answer is not a WARNING
A long-running set-core service or hook SHALL log at WARNING only a condition an operator
should act on. An expected outcome — an empty listing, a missing optional file, a peer that is
not running, a poll that found nothing — SHALL be logged at DEBUG, and a condition that repeats
on every poll SHALL be logged at WARNING at most once per state change.

#### Scenario: A polled resource is absent
- **WHEN** a poll finds an optional resource absent on every cycle
- **THEN** at most one WARNING is logged when it becomes absent, and none on the following cycles

#### Scenario: An expected empty answer
- **WHEN** a listing call returns nothing because there is nothing to list
- **THEN** no WARNING is logged

### Requirement: A sweep is measured before and after
Each service in the sweep SHALL have its WARNING count per day and its top messages recorded
before the fix, and each demoted message SHALL be covered by a test that fails when the level
is reverted.

#### Scenario: Reverting a demotion
- **WHEN** a demoted message's level is changed back to WARNING
- **THEN** its test fails
