## MODIFIED Requirements

### Requirement: A pulled-in question ends like a relayed one
A pulled-in question SHALL end without typing anything when its release marker is set (the
fleet's "to terminal" or an Enter typed in its terminal), when the relay switch is turned off,
or when its fleet terminal is gone. It SHALL NOT end because the relay's own timeout passed:
that timeout bounds the hook, which the runtime limits, and a carrier is not a hook. A carrier
SHALL stop after 24 hours at most. Its end SHALL be logged with the session's short id and the
reason, never with question or answer text.

#### Scenario: Handed back to the terminal
- **WHEN** the operator presses "to terminal" on a pulled-in question
- **THEN** the carrier ends, nothing is typed, and the question stays open in the terminal

#### Scenario: The switch goes off again
- **WHEN** the relay switch is turned off while a pulled-in question waits
- **THEN** the carrier ends and nothing is typed

#### Scenario: A long wait
- **WHEN** the operator answers a pulled-in question on the channel three hours after it was pulled in
- **THEN** the carrier still types the answer into the terminal

## ADDED Requirements

### Requirement: A question the hook lets go only for lack of time is pulled back in
When the relay hook releases an `AskUserQuestion` call because its own time ran out — and for
no other reason — it SHALL park the call and then start the backfill's pull-in at once, so a
question that is still open stays on the relay and on the fleet panel. A switch turned off, a
fleet release and an outbound failure SHALL NOT re-pull. A re-pull that fails SHALL be logged
and SHALL still release the question to the terminal.

#### Scenario: The hook's time runs out
- **WHEN** a relayed question gets no answer within the relay's timeout
- **THEN** the hook releases it, a carrier pulls it straight back in, and the fleet panel still counts it as waiting

#### Scenario: Handed back on purpose
- **WHEN** the operator presses "to terminal"
- **THEN** the question is released and not pulled back in
