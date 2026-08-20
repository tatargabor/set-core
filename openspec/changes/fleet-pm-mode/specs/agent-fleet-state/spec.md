## MODIFIED Requirements

### Requirement: An outstanding tool call is what "working" means

The framework SHALL derive the current activity from the tail of the session log: a tool invocation
with no matching result outstanding means the agent is in that tool, and the tool's name and elapsed
time SHALL be reported. A last entry that is an assistant message with no outstanding tool call
means the turn has ended.

This distinction is the whole question the surface answers. "In a tool for 19 minutes" and "turn
ended 18 minutes ago" look identical from the outside — one is work in progress, the other is an
agent waiting for a person — and only the log separates them.

**An outstanding call whose tool IS a question to a person is the exception, and it SHALL be
reported as blocked on a person rather than as working.** The framework SHALL hold a declared list
of such tools, SHALL name in the state which of them is outstanding, and SHALL report how long it
has been outstanding. A tool not on that list SHALL be treated as work, never guessed at by name.

Measured 2026-08-20 on a real session log, three instances: the `tool_use` entry for a
question-asking tool was journaled **8m13s, 9m32s and 1m43s before** its matching `tool_result`.
The outstanding call is therefore visible for the whole time the person is thinking — so this is
the one blockage on a person that is structurally certain, and until this change it was reported as
the opposite. That is a false value failing in the reassuring direction: the single case a reader
could act on immediately rendered as the case that needs nothing from them.

#### Scenario: An agent inside a tool
- **WHEN** the log tail holds a tool invocation with no matching result
- **THEN** the state is working, naming that tool and how long it has been outstanding

#### Scenario: An agent that finished its turn
- **WHEN** the last log entry is an assistant message and no tool call is outstanding
- **THEN** the state is waiting

#### Scenario: An outstanding question tool is a blockage, not work
- **WHEN** the log tail holds an outstanding invocation of a tool declared to ask a person
- **THEN** the state is blocked on a person, naming that tool and how long it has been outstanding,
  and it is not reported as working

#### Scenario: A question tool that has been answered is not a blockage
- **WHEN** such an invocation has a matching result
- **THEN** it does not make the agent blocked on a person

#### Scenario: An undeclared tool is work
- **WHEN** an outstanding tool is not on the declared list
- **THEN** the state is working, whatever the tool is named

## ADDED Requirements

### Requirement: Resuming after a blockage is measured, and an interrupt is not resuming

The framework SHALL report whether an agent has produced a new assistant utterance or opened a new
tool call **after** a given point in its session log. It SHALL NOT report the appearance of a user
entry as resumption.

Measured on a live log 2026-08-19: interrupting a session writes a `user` entry whose text is
`[Request interrupted by user]`. Any reader that treats a new user entry as "the person replied"
therefore reports an abandoned turn as an answered one. Recognising such entries by their text
would be a hand-maintained list of the runtime's synthetic markers, and a second copy of somebody
else's format drifts; measuring the effect — the agent moved — does not.

#### Scenario: An interrupt is not a resumption
- **WHEN** the only entry after the given point is an interrupt marker written as a user message
- **THEN** the agent is not reported as resumed

#### Scenario: A new turn is a resumption
- **WHEN** an assistant utterance or a new outstanding tool call is recorded after the given point
- **THEN** the agent is reported as resumed

#### Scenario: An unreadable log does not report resumption
- **WHEN** the session log cannot be read
- **THEN** resumption is reported as unknown, never as false
