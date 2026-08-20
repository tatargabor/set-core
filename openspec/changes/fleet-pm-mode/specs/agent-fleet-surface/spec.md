## ADDED Requirements

### Requirement: PM mode is a toggle, and it changes nothing about the agents

The fleet screen SHALL offer a control that turns PM mode on and off. Turning it on SHALL NOT
start, stop, instruct or otherwise touch any agent, and turning it off SHALL return the reader to
the arrangement they had.

The mode is a way of looking at the fleet, not a way of operating it. A toggle that also acted on
agents would be a control nobody dares press to find out what it does.

#### Scenario: Turning the mode on does not act on agents
- **WHEN** the reader turns PM mode on
- **THEN** no agent receives an instruction and no agent's lifecycle changes

#### Scenario: Turning it off restores the arrangement
- **WHEN** the reader turns PM mode off
- **THEN** the arrangement they had before is shown again

### Requirement: PM mode selects what the fleet screen shows, and never replaces it

While PM mode is on, the fleet SHALL put the presented agent into its own agent view — selecting
that agent's project and opening that agent — and SHALL keep the rest of the screen intact: the
project list, the agent tabs, the input, the terminal controls and any docked views. The mode SHALL
NOT render a surface of its own in place of the fleet screen.

It SHALL carry, in a strip that does not scroll away, how many further items are queued, how many
agents are idle without a question, and whether the judgement for this cycle is unmeasured.

The first build did replace the screen, with a full-screen overlay, and it was rejected on sight:
*"azt hittem ugyanugy meghagyja a felletet csak az agent view-ba teszi be az aktualis. ehelyett
full screen hasznalhatatlant csinalt."* The overlay discarded every affordance that makes an agent
workable in order to show one terminal — and for an agent the framework holds no terminal for, what
was left was two sentences on a blank page. A mode that chooses what you look at must not also take
away what you look at it with.

The counts remain the price of the mode rather than a decoration beside it: the reader is being
steered, so what they are NOT being steered to has to be visible where they are standing.

#### Scenario: The presented agent is put into the agent view
- **WHEN** the queue presents an agent
- **THEN** that agent's project is selected and that agent is opened in the fleet's own agent view

#### Scenario: The rest of the screen survives
- **WHEN** PM mode is on
- **THEN** the project list, the agent tabs, the input and any docked views are still rendered

#### Scenario: The mode renders no surface of its own in place of the fleet
- **WHEN** PM mode is on
- **THEN** it adds a strip and renders no container that covers the fleet screen

#### Scenario: The pile behind the screen is visible
- **WHEN** items are queued behind the presented one
- **THEN** their number is shown in the strip

#### Scenario: An unmeasured judgment is not shown as an empty queue
- **WHEN** the judgment pass for the cycle could not run
- **THEN** the strip says the judgment is unmeasured, and does not render as "nothing is waiting"

#### Scenario: Idle agents are counted, not queued
- **WHEN** agents have finished their turn without asking anything
- **THEN** their number is shown as a separate count the reader may open

### Requirement: An agent with no terminal is shown through its log, never as an empty panel

Where the framework holds no terminal for the presented agent, the fleet SHALL open that agent's
session log in its place, and SHALL still say that no terminal exists. It SHALL NOT present a panel
whose only content is the absence of one.

Measured 2026-08-20: **3 of 20** live agents had no pty, and **2 of the 4** items the queue held
were among them — half the queue, not an edge case. For every one of them the log endpoint had a
full conversation to give at that moment, so the emptiness was the surface's and not the agent's.

Both directions matter. Saying nothing fills the panel with a warning and blank space; filling it
without saying anything would suggest the agent can be typed into there.

#### Scenario: The log stands in for the terminal
- **WHEN** the presented agent has no terminal the framework holds
- **THEN** its session log is opened in the agent view

#### Scenario: The missing terminal is still stated
- **WHEN** the log is shown in place of a terminal
- **THEN** the panel still says that no terminal is available

### Requirement: The reader can step back and forward through what was presented

The frame SHALL offer a back control and a forward control over the items already presented in this
session of the mode. Back SHALL always be available where an earlier item exists; forward SHALL be
available only while the reader is behind the queue's current position.

#### Scenario: Back reaches the previous item
- **WHEN** the reader activates back
- **THEN** the previously presented item is shown and nothing is marked dealt with

#### Scenario: Forward is unavailable at the queue's head
- **WHEN** the reader is looking at the item the queue currently presents
- **THEN** the forward control is unavailable

### Requirement: A pending switch is announced before it happens, and any keystroke stops it

Where the attention queue offers to switch the presented item, the frame SHALL name what it would
switch to and SHALL show the time remaining. Any input the reader sends to the presented terminal
SHALL cancel it. The frame SHALL NOT show a countdown while the reader is typing.

#### Scenario: The countdown names its destination
- **WHEN** a switch is offered
- **THEN** the frame names the project and agent it would switch to, and the remaining time

#### Scenario: No countdown appears while typing
- **WHEN** the reader has typed into the presented terminal within the declared window
- **THEN** no countdown is shown
