# Proposal: fleet-wire-channels

## Why

The fleet screen shows who is alive but says nothing about who is talking to whom.
The active `sac` (set-agent-comm) channels — the actual coordination fabric between
agents in different projects — are invisible, so a session watching the fleet cannot
see that a conversation is flowing, in which direction, or between which seats. The
data to derive the channel graph already exists on disk (registry, rooms, per-room
channel files); only the visualisation is missing.

## What Changes

- A new read-only backend route `GET /api/fleet/channels` derives the channel graph
  from the sac runtime store: nodes (live fleet agents joined to sac enrolment on
  session id / project root), edges (shared room membership and DM `pair`s), and
  per-edge activity (sender, direction, timestamp of the newest channel-file write).
  It reads topology and recency only — never message content.
- A new wire-gutter visualisation on the fleet screen: each live agent row gets a
  terminal on the board's right edge; wires route through a dedicated gutter strip;
  rooms with more than two members render as junctions, DMs as direct wires.
- Directional animation: a travelling dash/dot moves sender → addressees on wires
  with recent traffic; idle wires render static grey.
- Show/hide toggle for the wire view, persisted with the other fleet layout state.
  While shown, the wire gutter takes the right-edge space (docked right-edge bands
  yield; they come back when the wire view is hidden).
- Coverage honesty: a live agent with no sac seat renders as "not enrolled" (dim
  socket, no wires) with an enrolment affordance — never as "has no communication".
  Live sessions only; enrolled-but-idle agents are out of scope.

## Capabilities

### New Capabilities

- `channel-topology-api`: the backend route that derives the domain-free channel
  graph (nodes, edges, activity, direction) from the sac runtime store, its shape,
  its degradation behaviour when the store is absent or unreadable, and the rule
  that message content never crosses it.
- `fleet-channel-wires`: the wire-gutter visualisation — terminals per live agent
  row, junction nodes for multi-member rooms, directional flow animation, the
  show/hide toggle, and the not-enrolled affordance.

### Modified Capabilities

- `fleet-dockable-views`: one added requirement — when the wire view is shown it
  owns the right edge, and docked right-edge bands collapse and restore with the
  toggle, without losing their stored arrangement.

## Impact

- `lib/set_orch/api/fleet.py` (or a sibling module it imports) — new route, Layer 1,
  domain-free: reads a configurable store root, no sac-specific vocabulary beyond
  generic channel topology.
- `web/src/pages/Fleet.tsx`, new `web/src/components/FleetWirePanel.tsx`, a new
  layout-derivation lib under `web/src/lib/`, and the layout state helpers in
  `web/src/lib/fleetDocks.ts`.
- New unit tests on both sides (Python: graph derivation and degradation; web:
  layout computation, direction assignment, toggle persistence).
- No contract changes to existing endpoints; no schema/deployment changes; no sac
  code changes — sac is read-only from the outside.
