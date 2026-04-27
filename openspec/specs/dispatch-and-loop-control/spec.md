# Dispatch And Loop Control Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: ff→apply same-iteration chaining
When an ff iteration successfully creates tasks.md, the loop SHALL chain the apply phase within the same iteration instead of ending and starting a new one.

#### Scenario: ff creates tasks.md — chain apply
- **WHEN** a loop iteration runs `opsx:ff` for a change
- **AND** after the Claude invocation, `tasks.md` exists in the change directory
- **AND** `detect_next_change_action()` returns `apply:*`
- **THEN** the loop SHALL NOT end the current iteration
- **AND** SHALL build a new prompt with the `/opsx:apply` instruction
- **AND** SHALL pipe it to a second `claude` invocation in the same iteration
- **AND** the iteration record SHALL include both the ff and apply phases

#### Scenario: ff fails to create tasks.md — no chaining
- **WHEN** a loop iteration runs `opsx:ff`
- **AND** after the Claude invocation, `tasks.md` does NOT exist
- **THEN** the loop SHALL end the iteration normally (existing ff retry logic applies)
- **AND** no apply chaining SHALL be attempted

#### Scenario: Chained apply fails or times out
- **WHEN** the chained apply invocation fails (non-zero exit) or exceeds the iteration timeout
- **THEN** the iteration SHALL end normally
- **AND** the next iteration SHALL pick up `apply:*` from `detect_next_change_action()` as before
- **AND** this SHALL NOT be counted as a stall

#### Scenario: Chained apply produces commits
- **WHEN** the chained apply invocation produces commits
- **THEN** those commits SHALL be recorded in the same iteration's metadata
- **AND** the stall counter SHALL be reset (progress was made)

#### Scenario: Iteration counter not incremented for chain
- **WHEN** ff chains to apply within the same iteration
- **THEN** the iteration counter SHALL NOT be incremented
- **AND** the max_iterations limit SHALL count this as one iteration, not two
