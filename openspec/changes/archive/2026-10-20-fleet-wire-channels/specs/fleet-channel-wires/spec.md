## IN SCOPE
- A channel-gutter visualisation of the rooms between live agents on the fleet screen, rendered as a ROOM-COLUMN MATRIX: rows are agents, columns are rooms, membership is a cell
- Vertical room names in a fixed header band; rooms whose members are all off-screen draw no column
- The room's newest sender renders as a filled, animated cell; other members render rings; idle memberships render dim
- A show/hide toggle for the view, persisted across reloads
- The not-enrolled affordance for live agents with no agent-comm seat, distinguishing session drift (seats exist, none carries this session) from never-enrolled

## OUT OF SCOPE
- Enrolment execution itself (the affordance points at the existing enrolment path)
- Message content display of any kind
- Columns for enrolled-but-idle agents' rooms where no visible agent sits in them
- Layout editing, column reordering by hand, or manual routing

## ADDED Requirements

### Requirement: Terminal per live agent row

When the wire view is shown, every live agent row on the fleet board SHALL render a
terminal at the board's right edge, positioned against that row's current on-screen
rectangle.

#### Scenario: Live row gets a terminal

- **WHEN** the wire view is shown and the board holds a live agent row
- **THEN** a terminal is drawn at that row's right edge, vertically centred on the row

#### Scenario: Terminals follow the board

- **WHEN** the board scrolls, a group collapses, a row appears or disappears on poll,
  or the window resizes
- **THEN** terminals, columns and cells are recomputed to the new rectangles
- **AND** a column persists while any of its members is visible; a scrolled-out
  row draws no cells, and nothing is left drawn where no row is

### Requirement: Rooms render as columns in a matrix

The gutter SHALL render one column per room that at least one visible enrolled
agent belongs to: a vertical guide line with the room's name running vertically
in a fixed header band. Rooms whose members are all off-screen or not rendered
draw no column. Columns with a fresh write lead; idle columns trail.

#### Scenario: Pair channel

- **WHEN** a channel has exactly two enrolled live members
- **THEN** both rows render a membership cell in the room's column

#### Scenario: Multi-member channel

- **WHEN** a channel has more than two enrolled live members
- **THEN** every member row renders its own cell in the room's column

#### Scenario: Single live member renders a stub column

- **WHEN** a channel has exactly one enrolled live member — the others being
  offline or unenrolled
- **THEN** the column still renders with that member's cell
- **AND** the hover identifies the members and the newest write's age, so the
  reader can see rooms a seat sits in and prune the unwanted ones (`sac part`)

#### Scenario: Room of a non-showing project

- **WHEN** a room's members are all off-screen or not rendered
- **THEN** no column is drawn for it

### Requirement: The sender cell is the direction

For a room whose newest write is within the activity window, the sender's cell
SHALL render filled and animated; the other members' cells render bright rings.
A membership whose room has no fresh write SHALL render static and muted. Who
sent is readable from WHICH CELL is filled — a grid needs no arrows.

#### Scenario: Recent send marks the sender

- **WHEN** a room's newest recorded write is by seat A within the activity window
- **THEN** A's cell renders filled and animated
- **AND** the other members' cells render bright rings

#### Scenario: Idle room is static

- **WHEN** a room's newest write is older than the activity window
- **THEN** its cells render static and muted, with no animation

#### Scenario: Never-written room renders dimmest

- **WHEN** a room has no recorded write at all
- **THEN** its column and cells render in the dimmest tier, and the hover says
  "no recorded write" — the inactive columns exist to be judged and pruned

### Requirement: Show/hide toggle with right-edge ownership

The wire view SHALL have a toggle in the fleet board header. When shown, the wire
gutter owns the board's right edge; docked right-edge bands collapse and restore
when the view is hidden, keeping their stored arrangement.

#### Scenario: Toggle on yields docked bands

- **WHEN** the user turns the wire view on while right-edge bands are docked
- **THEN** the wire gutter takes the right edge and the right-edge bands collapse
  (not lost)

#### Scenario: Toggle off restores them

- **WHEN** the user turns the wire view off
- **THEN** the previously docked right-edge bands render again in their stored
  arrangement and the gutter disappears

#### Scenario: Choice persists

- **WHEN** the user reloads the fleet screen
- **THEN** the wire view's shown/hidden state is as they left it

### Requirement: Not-enrolled affordance

A live agent row whose fleet identity joins to no enrolled seat SHALL render a
dimmed, empty terminal socket — never a wired node — marked as not enrolled, with an
affordance pointing at enrolment.

#### Scenario: Unenrolled live agent

- **WHEN** a live fleet agent matches no seat in the store
- **THEN** its row shows a dim socket with a "not enrolled" marking
- **AND** no wire is drawn to it, and the marking does not read as "no communication"

#### Scenario: Source unavailable

- **WHEN** the topology route reports `sourceAvailable: false`
- **THEN** the wire view says the channel source is unreachable rather than showing
  an all-unenrolled board

### Requirement: Hover identifies the channel

Pointing at a wire or junction SHALL identify the channel — room name, members, and
the age of the newest write — without any message content.

#### Scenario: Cell hover

- **WHEN** the user hovers a cell, column line, or header
- **THEN** a tooltip names the room, lists its member seat names, states the
  newest write's age, and carries the pruning verb (`sac part <room>`)
