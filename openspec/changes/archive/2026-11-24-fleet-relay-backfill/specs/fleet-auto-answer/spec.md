## ADDED Requirements

### Requirement: A question already on the channel can be decided without a second post
When automatic answers are turned on while the relay holds questions no decider has seen, the
decider SHALL decide each of them without forwarding it to the channel again, because the
operator already has it. Whatever it decides, it SHALL NOT release such a question to the
terminal: an excluded, below-bar or undecided question stays waiting on the channel as it was.
An allowed answer SHALL still be written only after the window, and a human answer SHALL still
win. The decision log SHALL record the decision like any other.

#### Scenario: Automatic answers turned on over a waiting question
- **WHEN** a question waits on the relay, no decider has seen it, and the operator turns automatic answers on
- **THEN** the decider decides it, nothing new is posted to the channel, and an allowed answer is written after the window unless the operator answers first

#### Scenario: The decider cannot answer it
- **WHEN** such a question is excluded, below the bar or undecided
- **THEN** it keeps waiting on the channel and is not released to the terminal
