## IN SCOPE
- Reordering the agents of one project by hand, on the tab strip.
- The identity that order is stored by, and what survives a restart.
- The one order governing both the tab strip and the agent grid.
- Where an agent goes when the order does not name it, and what happens to a named agent that
  is not running.
- Storing the order without conflicting with the hand-made project arrangement.

## OUT OF SCOPE
- What a tab or a tile SHOWS. This is about their sequence and nothing else.
- Ordering projects (`fleet-panel-dividers`, the arrangement) or panels (`fleet-dockable-views`).
- Moving an agent between projects — an agent belongs to the project it runs in.
- Sorting by a measured property (state, age, activity). This is a HAND-MADE order; a computed
  one is a different feature and would fight this one for the same list.

## ADDED Requirements

### Requirement: The reader can order a project's agents by hand

The screen SHALL let a person move an agent within its project's tab strip, by a pointer
gesture and by the keyboard, and SHALL store the resulting order.

The keyboard path is NOT a fallback for the pointer one. It is the path that can be exercised
without a layout engine, which is what makes the ordering testable at all; and it is the path
that works for a reader who cannot drag.

#### Scenario: A tab is dragged to a new position

- **WHEN** a person drags a tab past another one and releases it
- **THEN** the agent moves to that position and the new order is stored

#### Scenario: A tab is moved with the keyboard

- **WHEN** a person moves a focused tab with the keyboard
- **THEN** the agent moves one position and the new order is stored

#### Scenario: A click is not a drag

- **WHEN** a person presses a tab and releases it without moving
- **THEN** the order is unchanged and the tab is merely selected — a gesture that looks like
  nothing happening must not rewrite an arrangement nobody is watching a diff of

### Requirement: One order governs the tabs and the grid

The stored order SHALL determine the sequence of the tab strip AND the sequence of the agent
grid. There SHALL NOT be a second ordering for either surface.

The reader ordering the tabs and finding the grid disagreeing would be one fact rendered
twice — the shape this screen has already paid for elsewhere, where the unwatched copy goes
stale.

#### Scenario: The grid follows the strip

- **WHEN** the reader reorders the tabs and returns to the grid
- **THEN** the tiles are laid out in the same order

#### Scenario: The strip follows the grid's order on arrival

- **WHEN** a project is opened with a stored order
- **THEN** both the tabs and the tiles start in that order

### Requirement: The order is stored by a durable identity

An agent's place in the order SHALL be recorded by an identity that outlives the process: its
terminal label where it has one, otherwise its name, and only as a last resort its pid.

A pid dies with the process. An order stored by pid is forgotten on every restart, which is
not an arrangement but a decoration that occasionally looks right.

Where an agent is renamed, its place in the order SHALL follow the new name, exactly as its
docked panel already does.

#### Scenario: The agents restart

- **WHEN** the agents of a project are stopped and started again with new pids
- **THEN** each returns to the position the reader gave it

#### Scenario: An agent is renamed

- **WHEN** an agent is renamed
- **THEN** it keeps its position in the order

### Requirement: What the order does not name, and what is not running

An agent the stored order does not name SHALL appear LAST, in the order discovery returned it.
An agent the order names but discovery did not return SHALL keep its place in the stored list.

Both halves are about the same failure: a reader's arrangement quietly rewriting itself. A new
agent jumping to the front moves everything the reader placed; a stopped agent dropped from
the list loses its slot, and comes back somewhere else.

#### Scenario: A newly started agent

- **WHEN** an agent that the stored order does not name appears
- **THEN** it is shown after the ordered ones, and nothing the reader placed moves

#### Scenario: An agent stops and comes back

- **WHEN** an ordered agent is not running, and later runs again
- **THEN** it returns to the position it had, not to the end

### Requirement: Storing the order does not fight the arrangement

The order SHALL be stored through its own route, and storing it SHALL NOT require or consume
the version guard that protects the hand-made project arrangement.

The guard exists so that two open dashboards cannot silently overwrite each other's groups. A
drag of a tab must not be able to make the reader's own next group edit conflict, and must not
be pushed through the guarded route unguarded — the two are the only ways to get this wrong,
and they are opposite.

What is lost in a race here is one sequence, re-dragged in a second. That is the deliberate
trade, and it is the same one the divider positions already make.

#### Scenario: Ordering while the arrangement is being edited

- **WHEN** an agent order is stored
- **THEN** the project arrangement's version is neither required nor advanced

#### Scenario: The order is per project

- **WHEN** two projects both have a stored order
- **THEN** each project's order applies only to its own agents
