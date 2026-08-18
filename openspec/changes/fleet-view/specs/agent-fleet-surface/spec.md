## IN SCOPE
- A two-panel screen: projects on the left, the selected project's agents on the right
- What an agent tile carries, and what it may never drop when space runs short
- How the screen behaves as the number of agents grows
- Dictation into an agent's input

- Being the application's landing screen, including what it shows before discovery has answered

## OUT OF SCOPE
- The existing orchestration, status and activity screens, which are unchanged
- How a terminal is started, streamed and torn down (`agent-fleet-terminal`); this capability only
  places the terminal, and states where one is not on offer
- Any rendering that recognises a project's domain field names

## ADDED Requirements

### Requirement: Projects on the left, the selected project's agents on the right

The screen SHALL present projects as a scrollable column of tiles, and the agents of the selected
project as tiles in the remaining area, one per agent. Selecting a project SHALL show its agents
without a further navigation step.

#### Scenario: Selecting a project shows its agents
- **WHEN** a project tile is selected
- **THEN** that project's agents appear as tiles, one per agent

#### Scenario: A project with no running agent
- **WHEN** a selected project holds no live agent
- **THEN** the panel says so, and the project remains in the list

### Requirement: A project tile carries the state of the agents inside it

A project tile SHALL show how many agents it holds and enough of their states to tell, without
selecting it, whether any agent inside it is waiting or stuck.

This is what stops the compaction from hiding a failure. The screen's whole purpose is to find where
work has stopped; a left column that shows only names would require opening every project to find
the one agent that is waiting — which is the window-switching the screen replaces.

#### Scenario: A waiting agent is visible from the project list
- **WHEN** any agent in an unselected project is waiting
- **THEN** its project's tile shows that, without the project being selected

#### Scenario: The counts stay visible when the grid is compacted
- **WHEN** the agent area is compacted for density
- **THEN** the count of waiting agents remains readable

### Requirement: A project awaiting a human is surfaced even when no agent is running

A project holding work that is waiting for a human answer SHALL be surfaced as waiting even when no
agent process is running in it, and its tile SHALL count what is awaiting an answer rather than
counting agents.

This is the case an agent-centric screen gets wrong by construction, and it is the common case
rather than an edge. An open decision is written into the task file and outlives the run that
produced it, so the ordinary shape of a project blocked on a question is: no process alive, nothing
to show on any agent tile, a project holding zero agents. Rendered by agent count, it is
indistinguishable from a project with nothing to do — and it is the one project on the screen that
a person could unblock in a minute.

It is the same false absence this change exists to remove, arriving through the state that most
needs a reader. A screen that lists running agents answers "who is working"; this screen has to
answer "where has work stopped", and the stopped work usually has no one standing on it.

#### Scenario: A stopped project with no agents is not empty
- **WHEN** a project has work awaiting a human answer and no agent process running
- **THEN** its tile reports it as awaiting an answer, not as holding nothing

#### Scenario: The count is of what is waiting, not of who is present
- **WHEN** a project tile shows a waiting count
- **THEN** that count includes work awaiting an answer with no agent attached to it

#### Scenario: The marker outlives every process
- **WHEN** everything that produced the question has exited and restarted
- **THEN** the project is still surfaced as awaiting an answer

### Requirement: An agent tile carries state, log excerpt and its own input

Each agent tile SHALL show the agent's identity, its derived state, a recent excerpt of its log, and
an input for instructing it. Under any density, the tile SHALL retain its state and its input.

The input belongs on the tile rather than behind an opened view: the reason the screen exists is to
answer a waiting agent without changing context. A density that drops the input reintroduces the
step it was built to remove.

#### Scenario: A tile shows what the agent is doing
- **WHEN** an agent is inside a tool
- **THEN** the tile names the tool and how long it has been running

#### Scenario: A tile shows why an agent is waiting
- **WHEN** an agent has ended its turn
- **THEN** the tile shows the last lines of its log, so the reason for waiting is readable

#### Scenario: Density does not remove state or input
- **WHEN** the number of agents forces a denser layout
- **THEN** each tile still shows its state and its input, with other content shortened instead

#### Scenario: A tile whose binding is a guess says so
- **WHEN** an agent's session log was bound heuristically
- **THEN** the tile marks the log as unconfirmed

### Requirement: A tile can be enlarged, and the other agents stay visible as rows

The surface SHALL allow one agent tile to be enlarged, giving it a larger log area. While a tile is
enlarged, every other agent of that project SHALL remain visible as a single-line row carrying at
least its state and what it is doing, and selecting a row SHALL enlarge that agent instead.

Rows rather than nothing, because hiding the others would put an agent that is stuck behind a screen
that looks calm — the one thing this surface may not do. A row carries state and current activity
specifically so that choosing which agent to open is a decision rather than a guess.

#### Scenario: Enlarging one tile
- **WHEN** an agent tile is enlarged
- **THEN** it shows a larger log area and the other agents appear as rows

#### Scenario: The other agents are still readable
- **WHEN** a tile is enlarged while another agent is waiting
- **THEN** that agent's row shows its waiting state

#### Scenario: A row is the way back
- **WHEN** a row is selected
- **THEN** that agent becomes the enlarged tile

### Requirement: View state is remembered per project

The surface SHALL remember, per project, which tile is enlarged, the grid density, and any composed
but unsent text, and SHALL restore them when that project is selected again. A remembered view SHALL
never determine state: if the remembered agent no longer exists, the surface falls back to the grid.

Switching between projects is the motion this screen replaces window-switching with, and a view that
resets on every switch reintroduces the cost it removed. Unsent text is included because losing a
half-written answer is the most expensive small failure a surface like this has.

#### Scenario: Returning to a project restores its view
- **WHEN** a project is selected, a tile enlarged, another project visited, and the first selected again
- **THEN** the same tile is enlarged

#### Scenario: A remembered agent that is gone
- **WHEN** the remembered enlarged agent is no longer running
- **THEN** the grid is shown, and no empty enlarged tile

#### Scenario: An unsent draft survives a project switch
- **WHEN** text is typed into an agent's input and another project is visited
- **THEN** returning to that project restores the text, unsent

#### Scenario: A project holding one agent opens enlarged
- **WHEN** a project with exactly one agent is opened for the first time
- **THEN** that agent's tile is enlarged, because a grid of one leaves the rest of the area empty

#### Scenario: A remembered choice outranks the default
- **WHEN** the single tile is collapsed and the project is visited again
- **THEN** it stays collapsed — a default may choose the first view, never override a chosen one

### Requirement: Dictation writes into the same input as typing

The surface SHALL allow dictating an instruction into an agent's input, using the existing voice
input, and dictated text SHALL be reviewable and editable before it is sent.

#### Scenario: Dictated text lands in the input
- **WHEN** dictation is used on an agent tile
- **THEN** the transcript appears in that agent's input, editable before sending

#### Scenario: Dictation unavailable
- **WHEN** voice input is not configured
- **THEN** typing is unaffected and the dictation control is absent rather than failing on use

### Requirement: The delivery outcome is shown where the message was sent

After an instruction is sent, the surface SHALL show which delivery outcome occurred, on the tile
of the agent it was sent to, and SHALL NOT show a single confirmation that covers all outcomes.

#### Scenario: Each outcome reads differently
- **WHEN** an instruction is sent to an agent
- **THEN** the tile distinguishes arriving now, arriving at the end of the turn, and sitting unread

#### Scenario: An agent that will not wake offers the remedy
- **WHEN** the outcome is that the message sits unread because no waiter is running
- **THEN** the tile says so, and offers the action that would make that agent wakeable

### Requirement: The fleet is the landing screen, and an unfinished answer is not an empty one

The fleet SHALL be what the application's root route renders. While discovery has not yet answered,
the screen SHALL say that it is still looking, and SHALL NOT render an empty fleet, a zero count, or
the word idle for any agent it has not measured yet.

This requirement exists because of the measurement that produced the whole change: the previous
landing screen reported a project as stopped and last touched weeks earlier while six agents were
working inside it. Replacing one false absence with a faster one — a screen that paints "no agents"
during its first second — would reproduce the defect at the exact place every reader arrives first.
An unfinished measurement is a gap, and a gap is not a zero.

The projects overview SHALL remain reachable by its own route and by a navigation entry: this
decision moves what greets a reader, and removes nothing.

#### Scenario: The root route renders the fleet
- **WHEN** the application is opened at its root route
- **THEN** the fleet screen is shown

#### Scenario: Discovery has not answered yet
- **WHEN** the screen paints before discovery has returned
- **THEN** it states that it is still looking, and shows neither an empty fleet nor a count of zero

#### Scenario: Discovery answered, and there genuinely is nothing
- **WHEN** discovery has completed and found no live agent
- **THEN** the screen says that no agent is running, distinctly from the state above

#### Scenario: The projects overview is not lost
- **WHEN** a reader wants the projects overview
- **THEN** it is reachable from the navigation, with every behaviour it had before

### Requirement: A tile offers a terminal only where one can exist, and says why when it cannot

An agent tile SHALL offer a terminal only for an agent the framework started under a terminal it
owns. For any other agent the tile SHALL state that no terminal is available and that instruction
goes over the bus, and SHALL NOT present a terminal control that opens onto nothing.

A control that opens and silently swallows what is typed into it is worse than an absent one: the
reader has no way to tell a delivered instruction from a discarded one, and the kernel boundary that
causes it is invisible from the screen.

#### Scenario: A surface-started agent offers its terminal
- **WHEN** an agent was started from this screen
- **THEN** its tile offers a terminal that types into that agent

#### Scenario: A foreign session offers no terminal
- **WHEN** an agent was started outside the framework and cannot be adopted
- **THEN** its tile offers no terminal, states the reason, and keeps its bus input
