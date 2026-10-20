# Design: fleet-wire-channels

## Context

The fleet screen (`web/src/pages/Fleet.tsx`) lists project groups with agent
sub-rows; the right edge is dockable panel space (`fleet-dockable-views`,
`FleetDockBand`). The `sac` agent-comm system (`set-agent-comm`, external repo)
keeps its runtime store under the user data directory:

- `registry.json` → `agents`: per seat (`<name>#<short>`): `project` path, `session`
  uuid, `rooms: []`, `lastSeen`.
- `rooms.json` → rooms; DM rooms carry `pair: [seatA, seatB]`.
- `channels/<room>/<seat>.md` → one append-only markdown file per member; the newest
  `##` heading carries `<ISO timestamp> — KIND → <seat>#<short>` (addressee).

The fleet payload already carries per-agent `session_id`, `project_root` and `seat`,
so the fleet ↔ sac join is a pure backend concern. Measured on this machine: the
store exists, DM rooms and multi-member rooms both occur, and per-member channel
files carry parseable addressee headings.

## Goals / Non-Goals

**Goals:**

- See, on the fleet screen, which live agents are talking, through which channel,
  and in which direction — without opening anything.
- Derive everything from the store read-only; zero sac-side changes.
- Keep the fleet board readable: wires live in a gutter, never across board text.

**Non-Goals:**

- Enrolment execution, message transcripts, room archives, message content.
- A persistent idle-network view (enrolled-but-idle agents).
- Any second transport beside sac; the view surfaces sac only.

## Decisions

### 1. One new read-only route; derivation in a pure module

`GET /api/fleet/channels` in the fleet API router. The graph derivation lives in a
pure, store-root-parameterised module (Layer 1, domain-free): given a store root and
the live-agent roster, return nodes/edges. The route is a thin adapter that resolves
the store root (config override → platform default) and feeds it the roster from the
existing discovery path.

*Why pure:* the derivation is the testable core — a fake store tree in tmp dirs
covers join, edges, direction, degradation without sac installed.

### 2. Join: session id first, unique project root second, never a guess

`agent.session_id == seat.session`; else exactly one seat whose `project` equals the
agent's `project_root`; else `enrolled: false`. Ambiguous multi-seat projects stay
unjoined — a wrong wire is worse than a missing one.

### 3. Channel model: rooms are channels; DM rooms are pair channels

Every room two or more enrolled live agents share is one channel. `pair` rooms are
pair channels; other rooms are multi-member channels (junction). Edge direction:
parse the newest channel file's leading `##` heading for `→` addressees; on no
parse, broadcast to the other members. `lastActivity` from the file mtime (heading
timestamp as display refinement, not the join key — mtimes are cheaper and cannot
fail to exist).

### 4. Rendering: SVG gutter beside the board, anchors from live DOM rects

`FleetWirePanel` renders an absolutely-positioned SVG layer composed of (a) a gutter
strip and (b) terminals overlaid on the board's right edge. Rects come from
`data-agent-id` attributes on agent rows, read via `getBoundingClientRect` on each
render pass and on `ResizeObserver`/scroll/poll ticks. Wires are cubic curves:
terminal → gutter x, vertical run, junction/terminal. A pure layout lib
(`web/src/lib/fleetWireLayout.ts`) turns `{rects, edges}` into SVG path data — that
lib carries the unit tests; the component stays thin.

*Alternative rejected:* beziers drawn directly board-to-board (no gutter) —
unreadable with collapsed groups and multi-member rooms, and crosses text.

### 5. Direction animation: CSS dash-offset motion, sender-side origin

Flowing motion = `stroke-dasharray` + animated `stroke-dashoffset`, reversed
per-segment when the sender is the far end; a broadcast animates all non-sender
segments. Activity window: `lastActivity` newer than 30 minutes (constant, one
place). Static wires: muted grey, no animation. Direction must read as motion, per
spec — colour alone is forbidden.

### 6. Toggle state rides the existing fleet layout persistence

A boolean beside the dock persistence (`fleetDocks.ts` load/save path, server-backed
with local fallback, same as dock state). While shown, the panel suppresses
right-edge dock bands from layout (their entries stay stored, untouched) —
satisfying the fleet-dockable-views delta without new dock plumbing.

### 7. Not-enrolled: dim socket + tooltip affordance

Unenrolled live rows get a hollow socket glyph and "not enrolled" tooltip; the
affordance is a pointer to the enrolment path (documented in the tooltip), not a
parallel messaging path. `sourceAvailable: false` renders a one-line source-down
note in the gutter — never an all-socket board.

## Risks / Trade-offs

- **Rect churn makes wires jitter** (rows reorder on poll) → layout recomputes from
  rects every render; motion transitions kept short so a jump reads as a jump, not a
  smear. Accepted cost of anchoring to live data.
- **sac file shapes are an external contract we do not own** → derivation isolates
  every read behind the pure module; a shape change is one module's fix, and
  degradation paths (unparseable heading, missing file) are specified, not
  incidental.
- **mtimes lie after a copy/restore of the store** → direction still correct (from
  heading), only recency window may misfire; degradation to static is safe.
- **Confidentiality** → route returns identities and timestamps only; tests assert
  message body text never appears in a response.
- **Performance** → store reads are small JSON + directory mtimes per channel,
  cached per poll cycle like the rest of the fleet payload.

## Migration Plan

Purely additive: new route, new component, new persistence key. No existing endpoint
or stored shape changes; rollback = hide the toggle commit-wise (revert restores the
old layout exactly).

## Open Questions

- None blocking. Seat-name display on terminals uses the fleet row's own label; sac
  seat short-ids appear only in tooltips if both are needed to disambiguate.
