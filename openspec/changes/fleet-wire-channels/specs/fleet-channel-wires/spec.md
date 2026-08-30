## IN SCOPE
- A wire-gutter visualisation of active channels between live agents on the fleet screen
- One terminal per live agent row, wires routed through a dedicated gutter strip
- Junction rendering for channels with more than two members; direct wires for pairs
- Directional flow animation on wires with recent traffic
- A show/hide toggle for the wire view, persisted across reloads
- The not-enrolled affordance for live agents with no agent-comm seat

## OUT OF SCOPE
- Enrolment execution itself (the affordance points at the existing enrolment path)
- Message content display of any kind
- Wires for enrolled-but-idle agents, or a persistent background network view
- Layout editing, wire dragging, or manual routing

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
- **THEN** terminals and wires are recomputed to the new rectangles
- **AND** no wire is left drawn to a rectangle a row no longer occupies

### Requirement: Wires route through the gutter

Wires MUST be drawn in a dedicated gutter strip beside the board, not across board
text: a wire runs from its sender row's terminal into the gutter, routes vertically,
and reaches its target terminal or junction.

#### Scenario: Pair channel

- **WHEN** a channel has exactly two enrolled live members
- **THEN** a single wire connects the two terminals, routed through the gutter

#### Scenario: Multi-member channel renders a junction

- **WHEN** a channel has more than two enrolled live members
- **THEN** one junction node renders in the gutter for that channel
- **AND** each member's terminal connects to the junction with its own wire

### Requirement: Directional flow animation

A wire whose channel has a recent activity record SHALL animate flow from the
sender's terminal toward the addressee terminal or junction; a wire without recent
activity SHALL render static and muted.

#### Scenario: Recent send animates outward

- **WHEN** a channel's newest recorded write is by seat A within the activity window
- **THEN** the wire segment(s) from A's terminal animate in the direction of travel
- **AND** the animation reads as motion (travelling dash or dot), not as a colour change alone

#### Scenario: Idle channel is static

- **WHEN** a channel's newest write is older than the activity window
- **THEN** its wires render static and muted, with no animation

#### Scenario: Broadcast reaches every member

- **WHEN** the newest write names no specific addressee
- **THEN** the animation flows from the sender toward every other member's terminal
  via the junction or direct wires

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

#### Scenario: Wire hover

- **WHEN** the user hovers a wire or junction
- **THEN** a tooltip names the channel, lists its member seat names, and states the
  newest write's age
