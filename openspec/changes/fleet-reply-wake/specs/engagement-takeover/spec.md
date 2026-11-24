## ADDED Requirements

### Requirement: The asker is woken once when its request is answered
When an engagement turns `answered`, the fleet SHALL wake the asking agent once by typing one
line into its fleet terminal. The line names the bus room, the request's timestamp and the
reply's timestamp, and asks the agent to read the reply and continue. It carries no request or
reply text. The fleet SHALL wake only when all of these hold:

- the asker is a live agent in a fleet-held terminal;
- its turn has ended (runtime status `idle` or `shell`, no open call);
- it has not moved since the reply was written;
- nobody typed into it in the last two minutes;
- automatic answers are not turned off for that terminal.

Nothing is typed before the line (no Esc), so a free prompt is not disturbed. A reply older
than 20 minutes SHALL NOT wake anybody. The engagement SHALL record the outcome (`woken`,
`moved`, `busy`, `operator-present`, `off-here`, `not-fleet-held`, `gone`, `too-old`) and when.
A `busy` asker SHALL be looked at again in the next round, and every other outcome SHALL be
final, so one reply wakes at most once. Unrelated room traffic SHALL never wake an agent.

#### Scenario: The reply arrives while the asker sits idle
- **WHEN** an agent's request is answered and the agent's turn has ended with nothing since
- **THEN** its terminal receives one line naming the room and the request, the engagement records `woken`, and the next round types nothing more

#### Scenario: The asker already moved on
- **WHEN** the agent moved after the reply was written (its stop hook reported the mail, or it was given new work)
- **THEN** nothing is typed and the engagement records `moved`

#### Scenario: The asker is still working
- **WHEN** the reply arrives while the agent's turn is running
- **THEN** nothing is typed in that round, and a later round wakes it only if it has not moved since the reply

#### Scenario: The operator is at that terminal
- **WHEN** someone typed into the asker's terminal in the last two minutes, or automatic answers are off there
- **THEN** nothing is typed and the engagement records why

#### Scenario: The asker is not in a fleet terminal
- **WHEN** the asking session runs outside the fleet
- **THEN** nothing is typed and the engagement records `not-fleet-held`
