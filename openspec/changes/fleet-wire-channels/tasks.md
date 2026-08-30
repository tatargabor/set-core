## 1. Backend derivation module (pure, Layer 1)

- [x] 1.1 New module `lib/set_orch/fleet/channels.py`: `derive_channel_graph(store_root, live_agents, now)` returning the nodes/edges payload — no I/O beyond reading the given root [REQ: channel-graph-route]
- [x] 1.2 Join logic: session id first; unique project-root fallback; ambiguous or absent → `enrolled: false` [REQ: join-on-session-identity]
- [x] 1.3 Live-only filter: enrolled seats with no live agent produce no node [REQ: live-sessions-only]
- [x] 1.4 Edge derivation: shared rooms and `pair` DM rooms → channels; members as session identities [REQ: channel-graph-route]
- [x] 1.5 Direction: parse newest channel file's `→` addressee heading; fall back to broadcast to other members; `lastActivity` from mtime [REQ: edge-activity-and-direction]
- [x] 1.6 Degradation: absent/unreadable store → empty graph + `sourceAvailable: false`; store-root resolution via config with platform default [REQ: graceful-degradation] [REQ: store-root-is-configuration]
- [x] 1.7 Python unit tests: fake store trees in tmp dirs — join order, ambiguity, DM pairs, multi-member rooms, direction parse, broadcast fallback, degradation; assert a message body string never appears in the payload [REQ: members-are-identities-not-content]

## 2. Backend route

- [x] 2.1 `GET /api/fleet/channels` in the fleet API router: feed the live roster and resolved store root to the pure module; log at DEBUG (shape only, never content) [REQ: channel-graph-route]
- [x] 2.2 Route test: registered before project routers, 200 with empty graph + `sourceAvailable: false` when store missing [REQ: graceful-degradation]

## 3. Frontend layout + data plumbing

- [x] 3.1 `web/src/lib/fleetWireLayout.ts`: pure `{rects, edges, gutter}` → terminal positions, junction positions, SVG path segments per wire, per-segment direction (sender at near or far end) [REQ: wires-route-through-the-gutter]
- [x] 3.2 Unit tests for the layout lib: pair wires, junction fan (3+ members), sender-side direction per segment, missing-rect handling (row gone → segment dropped, never drawn to a stale rect) [REQ: terminals-follow-the-board]
- [x] 3.3 Fetch `/api/fleet/channels` on the fleet poll cycle; wire `sourceAvailable` and the 30-minute activity window into derived view state [REQ: directional-flow-animation] [REQ: source-unavailable]
- [x] 3.4 Persist the wire-view shown/hidden flag beside the dock persistence (server-backed, local fallback) [REQ: choice-persists]

## 4. FleetWirePanel component

- [x] 4.1 New `web/src/components/FleetWirePanel.tsx`: SVG layer — gutter strip, terminals anchored to agent-row rects (data attributes + `getBoundingClientRect`), recompute on scroll/resize/poll/row changes [REQ: terminal-per-live-agent-row] [REQ: terminals-follow-the-board]
- [x] 4.2 Render wires and junction nodes from layout output; pair channels as direct gutter wires, multi-member channels as junction + fan [REQ: wires-route-through-the-gutter]
- [x] 4.3 Direction animation: dash-offset motion from sender toward addressee(s), broadcast fans to all members; idle wires static and muted [REQ: directional-flow-animation] [REQ: broadcast-reaches-every-member]
- [x] 4.4 Toggle in the board header; while shown, right-edge dock bands collapse and restore with stored edge/size/collapsed state [REQ: show/hide-toggle-with-right-edge-ownership]
- [x] 4.5 Not-enrolled rows: dim socket + "not enrolled" tooltip with enrolment pointer; `sourceAvailable: false` renders a source-down note, never an all-socket board [REQ: not-enrolled-affordance]
- [x] 4.6 Hover tooltip on wires/junctions: channel name, member seat names, newest write age — no message content [REQ: hover-identifies-the-channel]
- [x] 4.7 Component tests: toggle persistence, junction vs pair rendering, unenrolled socket rendering, source-down note [REQ: not-enrolled-affordance] [REQ: source-unavailable]

## 5. Verification

- [x] 5.1 `tsc -b` and targeted vitest files green; Python route + module tests green; no new regressions vs the regression-baseline set-diff [REQ: channel-graph-route]
- [x] 5.2 Visual check in the browser against a store with a live DM and a multi-member room: terminals align to rows, wire leaves the gutter, animation direction matches the newest sender, docked right-edge bands yield and restore — the screen is LOOKED at, per the UI-quality rule; if the browser cannot be reached this task stays open and says so [REQ: terminal-per-live-agent-row] [REQ: directional-flow-animation] [REQ: show/hide-toggle-with-right-edge-ownership]

## Acceptance Criteria (from spec scenarios)

### channel-topology-api

- [x] AC-1: WHEN the route is called while the store holds enrolled agents and rooms THEN the response contains nodes (session identity, project root, seat name, enrolled flag) and edges (room name, member identities, latest activity) [REQ: channel-graph-route, scenario: graph-returned-for-a-live-store]
- [x] AC-2: WHEN an edge is derived from a room's channel files THEN it names room, members, sender and timestamp of the newest write, and no message body/excerpt/heading text is included [REQ: members-are-identities-not-content, scenario: members-are-identities-not-content]
- [x] AC-3: WHEN a live fleet agent's session id equals an enrolled seat's session id THEN the node is enrolled with that seat name [REQ: join-on-session-identity, scenario: session-id-match]
- [x] AC-4: WHEN no session id matches but exactly one seat's project path equals the agent's project root THEN the node joins that seat [REQ: join-on-session-identity, scenario: fallback-on-project-root]
- [x] AC-5: WHEN multiple seats share the project path and none matches by session id THEN the node stays `enrolled: false` [REQ: join-on-session-identity, scenario: ambiguous-fallback-stays-unjoined]
- [x] AC-6: WHEN an enrolled seat matches no live fleet agent THEN no node is emitted for it [REQ: live-sessions-only, scenario: enrolled-but-not-live]
- [x] AC-7: WHEN the newest channel file belongs to seat A and carries an addressee heading naming seat B THEN `from` is A, `to` lists B, `lastActivity` is that write's timestamp [REQ: edge-activity-and-direction, scenario: recent-send-establishes-direction]
- [x] AC-8: WHEN the newest write has no parseable addressee THEN `from` stays the writer and `to` is the other members (broadcast) [REQ: edge-activity-and-direction, scenario: unparseable-newest-write-degrades-to-broadcast]
- [x] AC-9: WHEN the store root is missing or unreadable THEN the response is 200 with empty edges and `sourceAvailable: false` [REQ: graceful-degradation, scenario: store-missing]
- [x] AC-10: WHEN no override is configured THEN the route reads the platform-default agent-comm data directory [REQ: store-root-is-configuration, scenario: default-resolution]

### fleet-channel-wires

- [x] AC-11: WHEN the wire view is shown and a live agent row exists THEN a terminal is drawn at that row's right edge, vertically centred [REQ: terminal-per-live-agent-row, scenario: live-row-gets-a-terminal]
- [x] AC-12: WHEN the board scrolls, collapses, gains/loses a row, or resizes THEN terminals and wires recompute and no wire points at a rectangle no row occupies [REQ: terminals-follow-the-board, scenario: terminals-follow-the-board]
- [x] AC-13: WHEN a channel has exactly two enrolled live members THEN one gutter-routed wire connects the terminals [REQ: wires-route-through-the-gutter, scenario: pair-channel]
- [x] AC-14: WHEN a channel has more than two members THEN one junction renders and each member has its own wire to it [REQ: wires-route-through-the-gutter, scenario: multi-member-channel-renders-a-junction]
- [x] AC-15: WHEN a channel's newest write is by seat A within the window THEN segments from A animate in the direction of travel as motion [REQ: directional-flow-animation, scenario: recent-send-animates-outward]
- [x] AC-16: WHEN a channel's newest write is older than the window THEN its wires are static and muted [REQ: directional-flow-animation, scenario: idle-channel-is-static]
- [x] AC-17: WHEN the newest write names no addressee THEN animation flows from the sender toward every other member [REQ: broadcast-reaches-every-member, scenario: broadcast-reaches-every-member]
- [x] AC-18: WHEN the wire view toggles on with right-edge bands docked THEN the gutter takes the edge and the bands collapse intact [REQ: show/hide-toggle-with-right-edge-ownership, scenario: toggle-on-yields-docked-bands]
- [x] AC-19: WHEN the wire view toggles off THEN the right-edge bands return with their stored arrangement [REQ: show/hide-toggle-with-right-edge-ownership, scenario: toggle-off-restores-them]
- [x] AC-20: WHEN the fleet screen reloads THEN the wire view state is as left [REQ: choice-persists, scenario: choice-persists]
- [x] AC-21: WHEN a live agent matches no seat THEN it shows a dim socket marked not enrolled, with no wires and no "no communication" reading [REQ: not-enrolled-affordance, scenario: unenrolled-live-agent]
- [x] AC-22: WHEN `sourceAvailable: false` THEN the view states the source is unreachable rather than an all-unenrolled board [REQ: not-enrolled-affordance, scenario: source-unavailable]
- [x] AC-23: WHEN hovering a wire or junction THEN a tooltip names the channel, its member seats, and the newest write's age, with no message content [REQ: hover-identifies-the-channel, scenario: wire-hover]
- [x] AC-24: WHEN right-edge bands yield to the wire view and it toggles off THEN they return with the same edge, size, and collapsed state [REQ: the-wire-view-owns-the-right-edge-while-shown, scenario: right-edge-bands-yield-and-return]
