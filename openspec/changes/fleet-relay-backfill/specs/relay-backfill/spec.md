## IN SCOPE
- Pulling in questions already open when the relay switch or the automatic-answer switch turns on
- Delivering a channel answer to a question asked before the relay saw it, through the fleet terminal
- Dropping a pulled-in question the session no longer waits on
- Reporting what could not be pulled in
- A by-hand run of the same pull-in

## OUT OF SCOPE
- Continuous re-scanning while the switch stays on (only the switch-on moment and the by-hand run)
- Typing into a terminal the fleet does not hold
- Permission prompts and finished turns that were never relayed
- Any new screen element: a pulled-in question shows in the relay's existing waiting list

## ADDED Requirements

### Requirement: Turning a switch on pulls in the questions already open
When the question relay switch is turned on, and when the automatic-answer switch is turned on
while the relay is on, the fleet SHALL look for `AskUserQuestion` calls that are open in a live,
fleet-held session and have no relay waiting record. It SHALL hand each one to the relay's
outbound as an ordinary question, with the same envelope, call id and waiting record a question
asked through the hook gets, so the operator's channel and the decider treat it like any other.
A session with such a call SHALL get at most one pulled-in question at a time.

#### Scenario: A question was asked while the relay was off
- **WHEN** an agent in a fleet terminal asked a question while the relay switch was off, and the operator turns the switch on
- **THEN** the question is handed to the relay's outbound, a waiting record for it appears in the relay's waiting list, and the decider sees it when automatic answers are on

#### Scenario: Nothing is open
- **WHEN** the switch is turned on and no fleet-held session has an open question
- **THEN** nothing is handed over and the switch's response reports zero pulled in

#### Scenario: The relay already holds the question
- **WHEN** a session's open question already has a relay waiting record
- **THEN** it is not handed over a second time

### Requirement: A question left to the terminal is parked for the next switch-on
When the relay hook lets an `AskUserQuestion` call go to the terminal unrelayed (the switch
off, the configuration not ready, the outbound failing, the switch turned off while it waited,
a release or a timeout), the hook SHALL record the call: session id, tool-use id, the call's
input, working directory and transcript path, in a private file (mode 600) beside the relay's
other state, never in a repository. The pull-in SHALL read these records first, because on the
current runtime an open call whose hook did nothing is not in the transcript until it resolves.
A record SHALL be removed when it is pulled in, when the same session's next question is
relayed, when its session is no longer live or its call has a result, and after 24 hours.

#### Scenario: Asked while the relay is off
- **WHEN** an agent asks while the relay switch is off
- **THEN** the hook releases the question to the terminal as before and parks it, and a later switch-on pulls it in although the transcript does not yet hold the call

#### Scenario: The session has ended
- **WHEN** a parked question's session is no longer live at the switch-on
- **THEN** it is not pulled in and its record is removed

### Requirement: A pulled-in answer reaches the agent through its terminal
The answer to a pulled-in question SHALL reach the agent through its fleet terminal, because the
hook that asked has already returned: Esc to close the open question, then one line naming each
question and its answer, then Enter. Before typing, the fleet SHALL check the session's
transcript again, and SHALL type nothing when the call has since been answered in the terminal
or the session has moved on. "Answered" SHALL be read only from a result for the call's id;
the call's own absence from the transcript SHALL NOT be read as an answer. The waiting record SHALL be removed before the line is typed.

#### Scenario: The operator answers on the channel
- **WHEN** the operator answers a pulled-in question on the channel
- **THEN** the agent's terminal receives Esc, then one line carrying the answer, then Enter, and the waiting record is gone

#### Scenario: The decider answers
- **WHEN** automatic answers are on and the decider writes an allowed answer after its window
- **THEN** the agent receives it the same way, and the decision log records it as written

#### Scenario: Answered in the terminal first
- **WHEN** the question is answered in the terminal before the channel answer arrives
- **THEN** the pulled-in question is dropped, nothing is typed, and its waiting record is removed

### Requirement: A pulled-in question ends like a relayed one
A pulled-in question SHALL end without typing anything when its release marker is set (the
fleet's "to terminal" or an Enter typed in its terminal), when the relay switch is turned off,
when the relay's timeout passes, or when its fleet terminal is gone. Its end SHALL be logged
with the session's short id and the reason, never with question or answer text.

#### Scenario: Handed back to the terminal
- **WHEN** the operator presses "to terminal" on a pulled-in question
- **THEN** the carrier ends, nothing is typed, and the question stays open in the terminal

#### Scenario: The switch goes off again
- **WHEN** the relay switch is turned off while a pulled-in question waits
- **THEN** the carrier ends and nothing is typed

### Requirement: What cannot be pulled in is named, not hidden
A question open in a session the fleet does not hold a terminal for SHALL be left in its
terminal, and the switch's response and the log SHALL count it and name its project and short
session id. The response SHALL report the pulled-in count beside it, so "nothing was pulled in"
and "nothing could be pulled in" read differently.

#### Scenario: A question in a plain terminal
- **WHEN** the switch is turned on while a session outside the fleet has an open question
- **THEN** that question is not handed over, and the response lists it as not fleet-held

### Requirement: The pull-in can be run by hand
`set-relay-backfill` SHALL run the same pull-in once and print what it pulled in and what it
left, so the owner or an agent can repeat it without toggling a switch. It SHALL do nothing
while the relay switch is off, and say so.

#### Scenario: Run while the relay is off
- **WHEN** `set-relay-backfill` runs with the relay switch off
- **THEN** it hands nothing over and says the relay is off
