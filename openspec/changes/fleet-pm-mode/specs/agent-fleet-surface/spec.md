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

### Requirement: The presented agent fills the screen, and what is behind it is counted where the reader stands

While PM mode is on, the fleet SHALL present one agent's terminal full screen. It SHALL show, in
the frame that is always visible, how many further items are queued, how many agents are idle
without a question, and whether the judgment for this cycle is unmeasured.

Compacting must never hide a failure. A full-screen presentation is the strongest hiding this
surface does: everything else is off screen, and a queue that silently grows behind it looks
exactly like a fleet with nothing left to do. The counts are the price of the freeze, not a feature
beside it.

#### Scenario: The pile behind the screen is visible
- **WHEN** items are queued behind the presented one
- **THEN** their number is shown in the always-visible frame

#### Scenario: An unmeasured judgment is not shown as an empty queue
- **WHEN** the judgment pass for the cycle could not run
- **THEN** the frame says the judgment is unmeasured, and does not render as "nothing is waiting"

#### Scenario: Idle agents are counted, not queued
- **WHEN** agents have finished their turn without asking anything
- **THEN** their number is shown as a separate count the reader may open

### Requirement: The mode presents only agents it can actually present

PM mode SHALL present an agent full screen only where the framework holds a terminal for it. For a
queued agent it cannot present that way, it SHALL show what it does have — the agent's identity,
its project and the means of addressing it that exists — and SHALL say plainly that no terminal is
available.

Measured 2026-08-20: 16 of 18 agents on this machine had a framework-held terminal, and 2 did not.
Presenting an empty frame for those two would be the false-absence class: the reader would conclude
the agent had nothing to show rather than that this surface cannot show it.

#### Scenario: An agent with no framework terminal
- **WHEN** a queued agent has no terminal the framework holds
- **THEN** it is presented with its identity and the available means of addressing it, and the
  absence of a terminal is stated

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
