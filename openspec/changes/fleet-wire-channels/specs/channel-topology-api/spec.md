## IN SCOPE
- A read-only HTTP route deriving the channel graph from the agent-comm runtime store
- Node derivation: live fleet agents joined to enrolled agent-comm seats
- Edge derivation: shared room membership and direct-pair rooms
- Per-edge activity: sender, direction, and timestamp of the newest channel write
- Degradation when the store is absent, empty, or unreadable
- The confidentiality line: topology and recency cross the route; message content never does

## OUT OF SCOPE
- Reading, returning, or transforming message bodies in any form
- Writing to the agent-comm store, enrolment, or any channel mutation
- A second transport beside the existing agent-comm system
- Message rendering, transcripts, or room archives on any screen

## ADDED Requirements

### Requirement: Channel graph route

The system SHALL expose `GET /api/fleet/channels` returning a channel graph with
`nodes` and `edges`, derived entirely from the agent-comm runtime store and the
fleet's own live-agent discovery.

#### Scenario: Graph returned for a live store

- **WHEN** the route is called while the agent-comm store holds enrolled agents and rooms
- **THEN** the response contains `nodes` (one per live fleet agent, each carrying its
  session identity, project root, seat name, and an `enrolled` flag) and `edges`
  (one per channel, each carrying the room name, the member session identities, and
  the channel's latest activity)

#### Scenario: Members are identities, not content

- **WHEN** an edge is derived from a room's channel files
- **THEN** the edge names the room and the member identities and carries a timestamp
  and sender identity of the newest write
- **AND** no message body, excerpt, or heading text from any channel file is included

### Requirement: Join on session identity

The system SHALL join a fleet agent row to an enrolled agent-comm seat primarily by
session id, falling back to project root when the session id is absent from the
store's registry.

#### Scenario: Session id match

- **WHEN** a live fleet agent's session id equals an enrolled seat's session id
- **THEN** that node is marked `enrolled: true` and carries the seat name

#### Scenario: Fallback on project root

- **WHEN** no enrolled seat's session id matches but exactly one enrolled seat's
  project path equals the fleet agent's project root
- **THEN** the node joins to that seat and is marked `enrolled: true`

#### Scenario: Ambiguous fallback stays unjoined

- **WHEN** more than one enrolled seat shares the same project path and none matches
  by session id
- **THEN** the node is marked `enrolled: false` rather than guessed

### Requirement: Live sessions only

The route SHALL include only agents the fleet reports as live; enrolled seats with
no live fleet agent SHALL NOT appear as nodes.

#### Scenario: Enrolled but not live

- **WHEN** an enrolled seat's session id matches no live fleet agent
- **THEN** no node is emitted for it

### Requirement: Edge activity and direction

For each edge the route SHALL report the sender identity and timestamp of the newest
write in that channel, so the client can animate flow from sender to the other
members without parsing message content itself.

#### Scenario: Recent send establishes direction

- **WHEN** the newest file in a channel directory belongs to seat A and carries a
  parseable addressee heading naming seat B
- **THEN** the edge's `from` is A's identity and `to` lists B
- **AND** the edge's `lastActivity` is that write's timestamp

#### Scenario: Unparseable newest write degrades to broadcast

- **WHEN** the newest write cannot be parsed for an addressee
- **THEN** `from` is still the writing seat and `to` is the channel's other members
  (a broadcast), so a stale or odd file never silently removes the channel

### Requirement: Graceful degradation

The route SHALL return a valid empty graph (zero nodes from the store, zero edges)
with a `sourceAvailable: false` marker when the agent-comm store is absent or
unreadable, instead of erroring.

#### Scenario: Store missing

- **WHEN** the store root does not exist or its registry cannot be read
- **THEN** the response is HTTP 200 with an empty edge list and `sourceAvailable: false`
- **AND** it is NOT an empty graph presented as "no communication" without the marker

### Requirement: Store root is configuration

The store root MUST be resolvable through configuration with the platform default,
not hardcoded per machine, so the route is portable.

#### Scenario: Default resolution

- **WHEN** no override is configured
- **THEN** the route reads the user-level agent-comm data directory
