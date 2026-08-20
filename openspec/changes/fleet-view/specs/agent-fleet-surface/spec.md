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
an input for instructing it. Under any density that still renders a TILE, the tile SHALL retain its
state and its input.

The input belongs on the tile rather than behind an opened view: the reason the screen exists is to
answer a waiting agent without changing context. A density that drops the input reintroduces the
step it was built to remove.

**NARROWED 2026-08-19, deliberately, and this is the whole of the narrowing.** The clause used to
read *"under any density"*, written when the densest layout was a row list and every agent had a
row with an input in it. The tab strip replaced the rows (see the enlarge requirement below), and a
tab carries no tile and therefore no input. So the guarantee holds wherever a tile is drawn, and an
agent shown only as a tab is instructable in one further act — selecting it. The step this
requirement was built to remove is *changing context to answer somebody*; one click inside the same
panel is not that step, whereas the original defect — an agent becoming uninstructable with nothing
on screen to say so — is still forbidden.

#### Scenario: A tile shows what the agent is doing
- **WHEN** an agent is inside a tool
- **THEN** the tile names the tool and how long it has been running

#### Scenario: A tile shows why an agent is waiting
- **WHEN** an agent has ended its turn
- **THEN** the tile shows the last lines of its log, so the reason for waiting is readable

#### Scenario: Density does not remove state or input
- **WHEN** the number of agents forces a denser layout
- **THEN** each tile still shows its state and its input, with other content shortened instead

#### Scenario: An agent shown only as a tab is one act from an input
- **WHEN** a tile is enlarged and another agent is therefore drawn as a tab
- **THEN** selecting that tab makes it the enlarged tile, with its input

#### Scenario: A tile whose binding is a guess says so
- **WHEN** an agent's session log was bound heuristically
- **THEN** the tile marks the log as unconfirmed

### Requirement: A tile can be enlarged, and the other agents stay visible as a tab strip

The surface SHALL allow one agent tile to be enlarged, giving it a larger log area. While a tile is
enlarged, every other agent of that project SHALL remain visible in a single-line tab strip carrying
at least its state and any marker that calls for attention, and selecting a tab SHALL enlarge that
agent instead.

Visible rather than hidden, because hiding the others would put an agent that is stuck behind a screen
that looks calm — the one thing this surface may not do. The strip carries state specifically so that
choosing which agent to open is a decision rather than a guess.

One line for all of them rather than one line each: rows cost a line per agent, so with eight agents
the tile that was enlarged in order to show more was back to the size it had in the grid. The strip
SHALL scroll sideways rather than wrap, because a strip that grows downwards is the row list again.

**What the strip may compact, and what it may not.** State, the unconfirmed-binding mark and a
contradicted declaration are alarms and SHALL ride on the tab itself — state as a colour is
acceptable where the word does not fit, provided the word remains in the tab's accessible name.
Branch, age and pid are not alarms and MAY move into the tab's accessible name alone.

**The instructing cost is accepted and stated.** A tab is too small to carry an input, so an agent
that is not selected SHALL be instructable in exactly one further act — selecting it. This narrows
the guarantee below, and it is written here rather than left to be discovered.

#### Scenario: Enlarging one tile
- **WHEN** an agent tile is enlarged
- **THEN** it shows a larger log area and the other agents appear as tabs in one strip

#### Scenario: The other agents are still readable
- **WHEN** a tile is enlarged while another agent is waiting
- **THEN** that agent's tab shows its waiting state

#### Scenario: A tab is the way back
- **WHEN** a tab is selected
- **THEN** that agent becomes the enlarged tile

#### Scenario: The strip does not become a row list
- **WHEN** more agents are in the project than fit across the strip
- **THEN** the strip scrolls sideways and stays one line high

### Requirement: The arrangement is the user's, and it never becomes the inventory

The surface SHALL let the user arrange projects by hand in two levels — ordered groups, and projects
ordered within their own group — SHALL let a project be assigned to a group and parked out of the way
by explicit acts, and SHALL persist that arrangement per user so it survives a reload and is the same
in every browser on the machine. Group membership SHALL be stored as a fact rather than derived from a
name pattern.

The arrangement SHALL be joined to what discovery found rather than substituted for it: a project that
exists but was never arranged SHALL still appear, and a project named in the arrangement that no longer
exists SHALL be reported as missing rather than silently dropped.

This is the D-2 decision (2026-08-19) and its reason: the user places related projects next to each
other, so the unit that must move is the group. It is stored on the server because arranging 45
projects is work done once and relied on, unlike a collapse toggle. Membership is stored rather than
derived because a name rule re-evaluates — renaming a project would silently move it, and a new project
whose name matched would land somewhere nobody put it.

The join is what keeps arrangement and inventory apart. Dropping a vanished name would make the
arrangement appear to have edited itself; omitting an unarranged project would make a registered
project simply not exist on screen, and an empty place looks exactly like nothing to show.

#### Scenario: A project nobody arranged still appears
- **WHEN** a project is discovered that appears in no group and is not parked
- **THEN** it is shown in the ungrouped section rather than omitted

#### Scenario: A project that vanished is reported
- **WHEN** the stored arrangement names a project discovery no longer finds
- **THEN** the surface reports it as missing rather than removing it silently

#### Scenario: A project belongs to exactly one place
- **WHEN** an arrangement would place a project in two groups, or in a group and parked
- **THEN** it occupies only the first, so its position cannot depend on iteration order

#### Scenario: A second tab does not silently overwrite the first
- **WHEN** an arrangement is saved against a version that is no longer current
- **THEN** the save is refused with the reason, and the stored arrangement is unchanged

### Requirement: What is hidden by arrangement still reports what it holds

Every control that hides projects — a collapsed group, the parked section — SHALL carry the count of
agents awaiting a human answer inside it, and the surface SHALL carry a marker that does not scroll
away, counting across every group and the parked section, with a way to reach the first.

Manual ordering makes this stricter rather than looser, and that is why it is a requirement of its own.
The rejected options bounded where a waiting agent could hide: automatic attention-ordering puts it on
top by construction, and a workspace filter has a fixed tab strip to hang a count on. A hand-maintained
order has neither — a project dragged to position 30 six weeks ago is below the fold today and nothing
will move it. Without this, hand-made arrangement is the one option that can hide waiting work behind a
screen the user themselves arranged to look calm.

#### Scenario: A waiting agent inside a collapsed group
- **WHEN** a group is collapsed and an agent inside it is awaiting an answer
- **THEN** the collapsed group shows that count, and the non-scrolling marker includes it

#### Scenario: A waiting agent in a parked project
- **WHEN** a parked project holds an agent awaiting an answer
- **THEN** the parked section shows that count, and the non-scrolling marker includes it

### Requirement: View state is remembered per project

The surface SHALL remember, per project, which tile is enlarged and the grid density, and SHALL
restore them when that project is selected again. A remembered view SHALL never determine state: if
the remembered agent no longer exists, the surface falls back to the grid.

Switching between projects is the motion this screen replaces window-switching with, and a view that
resets on every switch reintroduces the cost it removed.

**Composed but unsent text is deliberately NOT remembered, and this reverses what this requirement
first said.** It was included because losing a half-written answer is the most expensive small
failure a surface like this has — which is true, and it is outranked. An instruction being typed can
carry a consumer's own words; one live `declared.focus` on this machine named a partner company and
an unpaid invoice. The standing rule is that such content may be displayed and must never reach
`localStorage`, a log or a cache, and a remembered draft would put exactly that into the browser's
store, keyed by project, surviving every reload. The `draft` field stays in the stored shape,
unwritten, so that reopening this question is a deliberate act rather than an accident.

#### Scenario: Returning to a project restores its view
- **WHEN** a project is selected, a tile enlarged, another project visited, and the first selected again
- **THEN** the same tile is enlarged

#### Scenario: A remembered agent that is gone
- **WHEN** the remembered enlarged agent is no longer running
- **THEN** the grid is shown, and no empty enlarged tile

#### Scenario: An unsent draft is not written to the browser's store
- **WHEN** text is typed into an agent's input and the reader moves around the screen
- **THEN** nothing of what was typed reaches `localStorage`, and the loss of an unsent draft on a
  project switch is accepted as the price

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

### Requirement: An install offered from the screen goes through the module installer, and shows what it did not do

Where the screen offers to wire a capability into a project, it SHALL do so by asking the module
installer to install the module that provides it, and SHALL NOT carry an install path of its own for
any individual capability. The screen SHALL show the installer's own report: every file it skipped
and why, a run that changed nothing said as such, and a refusal naming the requirement that was
missing. It SHALL NOT offer to place a module's executable part into a project, and asking for a
module SHALL be treated as what it is — an edit to a file the project owns.

This requirement exists because the affordance was already implied and had nothing behind it. The
capability report distinguishes *not connected* from *unknown* on the stated ground that "not
connected invites wiring it in" — and an invitation with no way to accept it is decoration. Until
now the acceptance was a single task with no requirement above it, describing a bespoke install for
one capability and resting on an ownership check that was measured not to exist.

**The reporting half is not politeness, it is the same rule this screen is built on.** The
installer's contract states that a silent skip is a defect of the same class as a silent overwrite,
and that a run which changed nothing must say so. Those are requirements on the installer's output —
and a surface that runs the installer and renders "done" has re-created the silence one layer up,
where the reader is actually standing. An install that left six files alone because the project had
edited them is a *good* outcome and a *misleading* screen, unless the screen says it.

**And it is the most dangerous action this screen can take.** Everything else here reads; this
writes into a repository the framework does not own. The refusal cases therefore surface as refusals
rather than as options: a module whose requirement is missing is not offered with a warning, it is
refused with the missing name — because a warning is a thing a reader can click past, and the state
it leads to is a half-installed project nobody chose.

#### Scenario: The install is the installer's, not the screen's
- **WHEN** the screen offers to wire a capability into a project
- **THEN** it invokes the module installer for the module that provides it, and no capability-specific
  install path exists on the surface

#### Scenario: Skips are shown, not swallowed
- **WHEN** an install leaves files alone because the project modified them
- **THEN** each skipped file and its reason appear on the screen, not only in the installer's output

#### Scenario: A run that changed nothing says so
- **WHEN** an install writes no files
- **THEN** the screen states that outcome, rather than reporting a plain success

#### Scenario: A missing requirement is a refusal, not a warning
- **WHEN** a module requires another that the project does not have
- **THEN** the install is refused and the missing requirement is named, and no control offers to
  proceed regardless

#### Scenario: The executable part is never offered into a project
- **WHEN** the screen presents what can be installed into a project
- **THEN** a module's machine-wide executable part is not among it

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
