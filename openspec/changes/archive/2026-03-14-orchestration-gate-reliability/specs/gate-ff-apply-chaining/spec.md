## ADDED Requirements

### Requirement: ff→apply chaining triggers on action transition
The Ralph loop engine SHALL trigger in-iteration chaining when the detected action transitions from `ff:*` to `apply:*` between the start and end of an iteration, regardless of whether uncommitted files exist.

#### Scenario: ff commits artifacts and chaining fires
- **WHEN** an iteration starts with `detect_next_change_action()` returning `ff:<change>` AND the iteration ends with `detect_next_change_action()` returning `apply:<change>`
- **THEN** the engine SHALL invoke a chained Claude session with the apply prompt in the same iteration without waiting for the next iteration

#### Scenario: apply iteration does not trigger chaining
- **WHEN** an iteration starts with `detect_next_change_action()` returning `apply:<change>` AND ends with the same action
- **THEN** the engine SHALL NOT trigger chaining (normal iteration boundary)

#### Scenario: ff fails to create tasks.md
- **WHEN** an iteration starts and ends with `detect_next_change_action()` returning `ff:<change>`
- **THEN** the engine SHALL increment ff_attempts and follow existing ff retry logic without chaining
