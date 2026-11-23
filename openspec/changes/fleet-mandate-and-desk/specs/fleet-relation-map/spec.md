## IN SCOPE
- One payload describing projects, live agents with their mandates, and the relations between them
- A dockable view that draws it
- Marking an agent with no mandate and an engagement that is waiting or failed
- Reporting a source that could not be read

## OUT OF SCOPE
- Acting on agents from the map (start, stop, instruct stay where they are)
- History: the map shows what is live or open now
- Showing the text of any request, reply or session
- Agents on other machines

## ADDED Requirements

### Requirement: The map payload carries projects, agents and three kinds of relation
The framework SHALL serve one payload containing project groups, each live agent with its label, state and mandate, and relations of three kinds: `engagement` (asker to desk, with state and age), `started` (requester to started agent, marked as a claim), and `flow` (a declared relation between two projects). A project with no live agent and no open engagement SHALL be listed without being expanded.

#### Scenario: An agent with a mandate
- **WHEN** the map is requested while an agent with a mandate is live
- **THEN** the payload contains that agent in its project group with the mandate's kind and goal

#### Scenario: An open engagement
- **WHEN** an engagement is open between an asker and a desk
- **THEN** the payload contains an `engagement` relation between those two agents with the state `open` and its age

#### Scenario: An idle project
- **WHEN** a registered project has no live agent and no open engagement
- **THEN** it appears as a collapsed group

### Requirement: The three relation kinds are drawn so they cannot be confused
The view SHALL draw engagements, start relations and declared flows with visibly different styles, and SHALL mark a start relation as a claim.

#### Scenario: Reading a relation
- **WHEN** the reader looks at the map
- **THEN** an engagement, a start relation and a declared flow are distinguishable without opening a detail

### Requirement: A missing mandate and an unanswered engagement are marked where the reader stands
An agent with no mandate SHALL be marked on its node. An engagement that is waiting or failed SHALL be marked on its edge. The counts of both SHALL be shown on the control that opens the map, so a closed or collapsed map does not hide them.

#### Scenario: The map is closed
- **WHEN** one agent has no mandate and one engagement is waiting while the map view is not open
- **THEN** the control that opens the map shows both counts

#### Scenario: An unanswered engagement on the map
- **WHEN** an engagement is waiting
- **THEN** its edge is marked and shows its age

### Requirement: A detail opens above the layout
Opening the detail of a node or an edge SHALL NOT change the size or position of any other element of the view, and the detail SHALL be closable by the reader.

#### Scenario: Opening a node
- **WHEN** the reader opens an agent's detail
- **THEN** it appears above the map, nothing else moves, and it has a control to close it

### Requirement: A source that could not be read is reported and not drawn as empty
When the bus, the mandate store or the role file cannot be read, the payload SHALL say which, and the view SHALL show that the corresponding relations are unmeasured.

#### Scenario: The bus is unreachable
- **WHEN** the map is requested while the bus store cannot be read
- **THEN** the payload marks engagement states as unmeasured and the view says so

#### Scenario: No role file
- **WHEN** no role file exists on the machine
- **THEN** the map shows no declared flows and states that none are declared
