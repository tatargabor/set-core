## IN SCOPE
- One list of what waits on the owner, from four separately measured sources
- An API answer carrying that list, for the fleet and for any other surface
- A header control with the total and an unmeasured marker, and a floating panel listing the items
- Linking each item to the place where it can be answered
- The persistence boundary on item content

## OUT OF SCOPE
- Answering an item inside the panel (answers happen where the question lives)
- Pushing items to a chat channel (a notifier reads the API; building one is separate)
- Dismissing, snoozing or assigning items
- Defining a project's domain vocabulary for its questions (the project supplies values)

## ADDED Requirements

### Requirement: The owner's queue has four sources, and each is measured on its own

The framework SHALL build the owner's queue from four sources — agent questions, framework run
state, project questions, and bus entries addressed to the owner — and SHALL report, for each
source, a count and whether it was measured. A source that could not be read SHALL be reported as
unmeasured with its reason, and SHALL NOT contribute a zero. The total SHALL be the sum of the
measured sources only, and SHALL be accompanied by the number of unmeasured sources.

#### Scenario: An unreadable source is not a zero
- **WHEN** the bus cannot be read and the other three sources hold 4 items
- **THEN** the total is 4
- **AND** the answer states that one source is unmeasured and why

#### Scenario: Sources are not merged into one count
- **WHEN** two sources each hold items
- **THEN** each source's count is reported separately alongside the total

### Requirement: Agent questions come from the attention classes and the question relay

The agent-question source SHALL list every live agent whose attention class means it is waiting
for a person, and every question the question relay is holding. Each item SHALL name the agent, its
project, and since when it has waited. An agent counted through the relay SHALL NOT be listed a
second time through its attention class.

#### Scenario: A relayed question is listed once
- **WHEN** an agent's question is held by the relay and the agent also reads as waiting
- **THEN** exactly one item is listed for that agent

#### Scenario: A waiting agent is listed with its wait
- **WHEN** an agent has waited 12 minutes for input
- **THEN** its item names the agent, its project and a 12-minute wait

### Requirement: Framework run state contributes its existing awaiting kinds

The run-state source SHALL list the manual, stalled, orphaned and decision items the fleet already
measures per project, keeping each item's kind. Items reported as unverifiable SHALL NOT be listed
as waiting. A project with no run state SHALL count towards this source's unmeasured projects, not
towards its items.

#### Scenario: A stalled change is listed with its kind
- **WHEN** a project's run state holds one stalled change
- **THEN** one item of kind `stalled` is listed for that project

### Requirement: Project questions are read from a project's declared command

The project-question source SHALL read open questions and decisions from a read command a project
declares for that purpose under the status-contract rules, and SHALL list each item with its
identifier, kind (question or decision), title, and since when it has been open, plus what it
blocks and a reference into the project's own status data where the project supplies them. A
project that declares no such command SHALL be reported as *not declared*, distinct from a project
that declared one and has nothing open. A command that fails SHALL be reported with the
contract's own failure class.

#### Scenario: Not declared is not nothing open
- **WHEN** one project declares no questions command and another declares one that answers with no items
- **THEN** the first is reported as not declared and the second as zero open

#### Scenario: A blocked release is carried
- **WHEN** a project's item names the release it blocks
- **THEN** the listed item carries that release

### Requirement: Bus entries addressed to the owner are read through the bus's own machine view

The bus source SHALL list entries that the bus itself reports as addressed to the owner and still
open, read through a machine-readable view the bus provides. The framework SHALL NOT parse message
text to decide whether an entry is addressed to the owner, and SHALL NOT read the bus's storage
format directly for this purpose.

#### Scenario: Prose addressing is not counted
- **WHEN** a broadcast entry mentions the owner only inside its text
- **THEN** it is not listed by the bus source

#### Scenario: The bus view is unavailable
- **WHEN** the bus provides no such view or it fails
- **THEN** the bus source is reported as unmeasured with that reason

### Requirement: The queue is one API answer that other surfaces can read

`GET /api/fleet/waiting-on-you` SHALL return the queue: per-source counts, measured flags and
reasons, the total, and the items. Item titles and texts SHALL be read at request time and SHALL
NOT be logged, cached to disk, or written into any artifact; logs SHALL carry counts and source
names only.

#### Scenario: The answer carries every source
- **WHEN** the endpoint is called
- **THEN** the answer names all four sources with a count and a measured flag each

#### Scenario: Logs carry no item content
- **WHEN** the queue is built with items present
- **THEN** no log line contains an item's title or text

### Requirement: The header shows the total, and the panel floats

The fleet header SHALL carry a "waiting on you" control showing the total and, when any source is
unmeasured, a marker saying so, both visible while the panel is closed. Opening the control SHALL
show a panel positioned above the layout that moves nothing beneath it, closes on its own control
and on Escape, and does not close by itself. The panel SHALL list items oldest first, grouped by
project, SHALL mark items that name a blocked release, and SHALL link each item to where it can be
answered: the agent's tile, the project's status row, or the bus entry.

#### Scenario: Unmeasured is visible while closed
- **WHEN** one source is unmeasured and the panel is closed
- **THEN** the header control shows the unmeasured marker

#### Scenario: Opening the panel moves nothing
- **WHEN** the reader opens the panel
- **THEN** no element of the fleet screen beneath it changes position or size

#### Scenario: An agent item leads to the agent
- **WHEN** the reader follows an agent-question item
- **THEN** that agent's project is selected and the agent is enlarged
