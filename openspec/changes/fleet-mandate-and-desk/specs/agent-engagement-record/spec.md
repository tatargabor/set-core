## IN SCOPE
- One command by which an agent asks another project for something
- The record of that request: parties, kind, subject, and where the request is on the bus
- Deciding that a request was answered, from the bus's own reply link
- Reporting a request that has waited too long
- Bounding how many requests one asker holds open

## OUT OF SCOPE
- Storing or reading the text of a request or a reply
- Any transport other than the existing bus
- Judging whether an answer is correct or complete
- Requests addressed to the person (the bus's owner addressee covers those)

## ADDED Requirements

### Requirement: Asking a project is one command that sends as the asker
`set-fleet-ask <project> "<request>"` SHALL resolve the project's desk, send the request over the bus from the asking session's own seat addressed to the desk's seat, and record the engagement. It SHALL print the engagement id and the desk it reached.

#### Scenario: A request reaches a desk
- **WHEN** an agent runs the command for a project whose desk is reachable
- **THEN** a bus entry from the asker's seat addressed to the desk's seat exists, and an engagement in the state `open` points at it

#### Scenario: The bus refuses the send
- **WHEN** the bus send fails after the desk was resolved
- **THEN** the engagement is marked `failed` with a reason class and the command exits non-zero

#### Scenario: The desk cannot be resolved
- **WHEN** resolution refuses or fails
- **THEN** nothing is sent on the bus, the engagement is marked `failed` with the resolution's reason, and the command prints that reason

### Requirement: An engagement stores a pointer and never the request
The engagement record SHALL hold the asker, the addressed project and desk, the kind, an optional short subject supplied by the asker, and the room and timestamp of the request on the bus. It SHALL NOT hold the text of the request or of any reply.

#### Scenario: What is stored
- **WHEN** an engagement is recorded for a request
- **THEN** the record contains the request's room and timestamp and does not contain its text

### Requirement: An engagement is answered only by a reply the bus links to it
An engagement SHALL become `answered` when an entry by a seat of the addressed project, in the same room, links to the request's timestamp. No other entry SHALL close it, and no entry body SHALL be read to decide it.

#### Scenario: A linked reply
- **WHEN** the desk writes an entry that links to the request
- **THEN** the engagement becomes `answered` and records the reply's timestamp

#### Scenario: An unlinked entry
- **WHEN** the addressed project writes an entry in the room that does not link to the request
- **THEN** the engagement stays `open`

#### Scenario: Bodies are never read
- **WHEN** engagement states are computed
- **THEN** only entry headings are parsed, and no text from an entry body appears in any payload or log

### Requirement: An engagement open past the bound is reported as waiting
An `open` engagement older than the configured bound SHALL be reported as waiting, to the asker's listing and to the screen. Waiting SHALL NOT change the engagement's state.

#### Scenario: A request nobody answered
- **WHEN** an engagement has been open longer than the bound
- **THEN** it is listed as waiting with its age, and its state is still `open`

### Requirement: Open engagements per asker are bounded
An asker SHALL be refused a new engagement when it already holds the configured maximum of engagements that are resolving or open.

#### Scenario: One request too many
- **WHEN** an asker at the bound runs the command again
- **THEN** the request is refused, nothing is started or sent, and the refusal lists the open engagements

### Requirement: Engagements can be listed by the asker and the screen
The framework SHALL list engagements with their parties, kind, subject, state and age, filtered by asker, by addressed project, or by state. When the bus cannot be read, states SHALL be reported as unmeasured rather than as open.

#### Scenario: The asker's own list
- **WHEN** an agent lists its engagements
- **THEN** it sees each one's addressed project, subject, state and age

#### Scenario: The bus cannot be read
- **WHEN** engagement states are requested while the bus store is unreadable
- **THEN** the states are reported as unmeasured with the reason
