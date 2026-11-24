## ADDED Requirements

### Requirement: Automatic answers can be turned off for one agent
The operator SHALL be able to turn automatic answers off for one agent while they stay on for
the rest. The opt-out SHALL be stored machine-locally (`auto_answer.off_agents`) and name the
agent by its fleet terminal label (`label:<label>`), so a `/clear` in that terminal keeps it.
A session outside the fleet is named by its session id (`session:<id>`). For an opted-out
agent the decider's outbound SHALL forward every envelope to the operator's channel byte for
byte, as with the machine switch off, and SHALL decide nothing, a continuation included. The
switch-on pull-in SHALL start no decide-only worker for it. The opt-out SHALL be set and cleared
from the fleet terminal's header, from the automatic-answer panel, and with
`set-auto-answer here off|on|status` run inside the session. Logs SHALL name the label or the
short session id, never question text.

#### Scenario: Planning at one agent
- **WHEN** automatic answers are on, the operator turns them off for the agent they are working at, and that agent asks a question
- **THEN** the question reaches the channel exactly as the relay built it, no proposal is attached, and nothing is written

#### Scenario: The other agents are unaffected
- **WHEN** another agent asks while one agent is opted out
- **THEN** the decider decides that question as before

#### Scenario: The terminal is cleared
- **WHEN** the opted-out agent's terminal runs `/clear` and asks again under a new session id
- **THEN** it is still opted out, because the opt-out names the terminal

#### Scenario: From inside the session
- **WHEN** the operator types `! set-auto-answer here off` in a fleet terminal
- **THEN** that terminal's label is opted out and the command says so; `here on` clears it, and `here status` reports it

#### Scenario: Turned back on from the panel
- **WHEN** the operator clears an opt-out on the automatic-answer panel
- **THEN** the next question from that agent is decided again
