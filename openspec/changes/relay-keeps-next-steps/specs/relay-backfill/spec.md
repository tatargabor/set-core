## ADDED Requirements

### Requirement: A next step the hook lets go only for lack of time is carried on
When the continuation hook releases a finished turn's next step only because its own time ran out, and the session is held in a fleet terminal, the next step SHALL be posted to the relay again by a carrier that no hook limit binds, keeping the age the board shows. A channel answer SHALL be typed into that terminal as the instruction the hook would have woken the session with. The carrier SHALL let go without typing when the session produced a newer turn, a prompt was typed, the fleet released the item, the switch went off, or the terminal is gone. A next step in a terminal the fleet does not hold SHALL stay there, as before.

#### Scenario: The hook's time runs out on a next step
- **WHEN** a next step has waited 3300 s with no answer and its session is in a fleet terminal
- **THEN** it is still listed on the board with its original age, and an answer given after that is typed into the session

#### Scenario: The session moved on
- **WHEN** the session produced a newer turn after the next step was posted
- **THEN** the carrier lets the next step go and types nothing

#### Scenario: Not held by the fleet
- **WHEN** the next step's session runs in a plain terminal
- **THEN** nothing is carried, and the session stays idle with its last message
