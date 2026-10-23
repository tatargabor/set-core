## IN SCOPE
- A latest-mode toggle and an agent-count control in the fleet header
- Selecting the N agents a person most recently wrote into, across every project
- The order following recency on every poll, held while the pointer is over the tabs or tiles
- The project column's selection and the tiles' project naming while the mode is on
- Mutual exclusion with PM mode
- The human-input measurement reaching beyond the bounded transcript tail

## OUT OF SCOPE
- Ordering by anything other than a person's last message (agent activity, wait time, cache heat)
- A server-side or cross-browser memory of the mode's state or count
- Docking, agent drag-reorder, and the project files/board panels inside the mode
- Starting, stopping or instructing agents from the mode beyond what a tile already offers

## ADDED Requirements

### Requirement: Latest mode is a toggle beside PM mode, and it changes nothing about the agents

The fleet header SHALL offer a latest-mode toggle next to the PM mode toggle. Turning it on SHALL
NOT start, stop, instruct or otherwise touch any agent, and turning it off SHALL return the reader
to the project and arrangement they had before turning it on.

#### Scenario: Turning the mode on does not act on agents
- **WHEN** the reader turns latest mode on
- **THEN** no agent receives an instruction and no agent's lifecycle changes

#### Scenario: Turning it off restores the previous project
- **WHEN** the reader had project P selected, turned latest mode on, and turns it off again
- **THEN** project P is selected and shown with the arrangement it had

### Requirement: The mode shows the N agents a person most recently wrote into, across all projects

While latest mode is on, the agent area SHALL show the N agents with the smallest
`last_human_input_seconds`, drawn from every project the fleet lists. N SHALL be set by a number
control beside the toggle, SHALL default to 10, and SHALL be remembered per browser. Agents with no
measured human input SHALL be placed after every measured agent and SHALL be shown as *no message
from you found*, never as a long silence. When fewer agents exist than N, the mode SHALL show the
agents that exist and SHALL NOT render empty slots.

#### Scenario: Agents from different projects share one screen
- **WHEN** the most recently written agents belong to three different projects
- **THEN** all of them are shown together in the mode's agent area

#### Scenario: Unmeasured agents come last and are not called old
- **WHEN** one agent's human-input age is absent and N is larger than the number of measured agents
- **THEN** that agent is placed after every measured agent
- **AND** its tile says no message from the reader was found, not a duration

#### Scenario: The count is honoured
- **WHEN** the reader sets the count to 5 and 12 agents exist
- **THEN** exactly 5 agents are shown

### Requirement: The order follows recency and holds under the pointer

While the mode is on, its agents SHALL be ordered most recent first on every poll, not only when
the mode is turned on. While the pointer is over the tab strip, or over the tiles in the grid
layout, the order SHALL NOT change; it SHALL catch up when the pointer leaves. The pointer over an
enlarged agent SHALL NOT hold the order.

#### Scenario: Writing into an agent moves it first
- **WHEN** the reader writes into the third tile and the pointer is not over the tabs or tiles
- **THEN** after the next poll that agent is first

#### Scenario: A newcomer enters at its rank
- **WHEN** the reader writes into an agent that is not shown
- **THEN** after the next poll that agent is shown at its rank and the least recent agent leaves

#### Scenario: The order holds under the pointer
- **WHEN** a poll changes recency while the pointer is over the tab strip or the tile grid
- **THEN** no tab or tile moves until the pointer leaves

### Requirement: No project is selected while the mode is on, and every tile names its project

While latest mode is on, the project column SHALL show no project as selected, and every tile in
the mode SHALL name the project its agent belongs to. Choosing a project in the column SHALL turn
the mode off and select that project.

#### Scenario: Two agents with the same name are told apart
- **WHEN** two shown agents from different projects carry the same name
- **THEN** each tile shows its own project name

#### Scenario: Choosing a project leaves the mode
- **WHEN** the reader selects a project in the column while the mode is on
- **THEN** the mode turns off and that project is shown

### Requirement: The mode uses the fleet's own agent view, with a view memory of its own

The mode SHALL present its agents through the fleet's existing grid, enlarged view, agent tab
strip and column choices, and each tile SHALL act on its own agent's project (its terminal, files
and log) rather than on any selected project. The mode's columns, enlarged tile and open terminals
SHALL be remembered under a key of their own, separate from every project's view memory. An agent
with no terminal SHALL open its log when enlarged. Controls that act on one project's arrangement
— agent drag-reorder, docking, the project's files and board panels — SHALL NOT be offered in the
mode.

#### Scenario: The mode's layout does not leak into a project
- **WHEN** the reader chooses three columns in the mode and later opens a project
- **THEN** that project keeps its own column choice

#### Scenario: A tile acts on its own project
- **WHEN** the reader opens a file link from a tile whose agent belongs to project Q while project P was last selected
- **THEN** the file is resolved against project Q's root

#### Scenario: An agent without a terminal shows its log
- **WHEN** the enlarged agent has no terminal
- **THEN** its log is opened

### Requirement: Latest mode and PM mode are mutually exclusive

Turning latest mode on SHALL turn PM mode off, and turning PM mode on SHALL turn latest mode off.
Both toggles SHALL always show the state that is actually in force.

#### Scenario: PM mode is turned off by latest mode
- **WHEN** PM mode is on and the reader turns latest mode on
- **THEN** PM mode is off and its toggle says so

#### Scenario: Latest mode is turned off by PM mode
- **WHEN** latest mode is on and the reader turns PM mode on
- **THEN** latest mode is off and its toggle says so

### Requirement: The last human input is found beyond the bounded tail

When a transcript's bounded tail holds no human entry, the framework SHALL search further back in
that transcript for the newest human entry, by the same definition of a human entry as the tail
measurement. The result SHALL be remembered in memory per transcript and reused while the
transcript only grows, so the deeper search is not repeated on every poll. An absent human-input
age SHALL then mean *this transcript holds no message from a person*. Nothing found by the search
SHALL be written to disk.

#### Scenario: A long tool run does not hide the reader's message
- **WHEN** a person's last message is followed by more than the bounded tail's worth of tool traffic
- **THEN** the reported human-input age is the age of that message, not absent

#### Scenario: The deep search is not repeated while nothing changed
- **WHEN** the transcript has grown only by entries without human text since the last search
- **THEN** the remembered age is reused without reading further back

#### Scenario: A transcript with no human message stays absent
- **WHEN** no entry in the whole transcript is a human entry
- **THEN** the reported human-input age is absent

### Requirement: Ctrl+Left and Ctrl+Right switch the strip's tab in latest mode

Added 2026-10-20 at the user's request: *"pressing ctrl-left and ctrl-right combinations switch
the panel tab on latest mode layout to the next or prev tab"*.

While latest mode is on and the tab strip is shown, Ctrl+Right SHALL select the next tab and
Ctrl+Left the previous one, in the strip's order, wrapping at both ends. Selecting SHALL perform
the same act as clicking that tab. Only plain Ctrl with the arrow SHALL count; with Shift, Alt or
Meta held, the key SHALL be left alone.

The switch SHALL work while a terminal tile has focus. The user chose this knowing it costs the
terminal its Ctrl+Left/Right word-jump while latest mode is on. Outside latest mode the terminal
SHALL keep the key. A focused input or editor other than a terminal SHALL keep its own word-jump.
When the strip is not shown, the key SHALL change nothing.

#### Scenario: Next and previous, with wrap-around
- **WHEN** latest mode is on with the first of four tabs active, and the reader presses Ctrl+Right, then Ctrl+Left twice
- **THEN** the second tab is active, then the first, then the last

#### Scenario: From inside a terminal
- **WHEN** a terminal tile has focus in latest mode and the reader presses Ctrl+Right
- **THEN** the terminal does not receive the key and the next tab is active

#### Scenario: An input keeps its word-jump
- **WHEN** the count input has focus and the reader presses Ctrl+Right
- **THEN** the active tab does not change

#### Scenario: Outside latest mode
- **WHEN** latest mode is off and the reader presses Ctrl+Right, in a terminal or on the page
- **THEN** the terminal receives the key as before and the active tab does not change
