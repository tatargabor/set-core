## Context

Three arrangements on the fleet screen are already hand-made and stored: projects in groups
(with an explicit `order` that keeps names discovery did not return), panels docked to edges,
and divider positions in pixels. Each has its own storage route and its own reason for having
one.

The agents inside a project have none. `gridAgents` is `active.agents` filtered by docking —
discovery's order, straight through — and `AgentTabs` renders that same list. So the reader
can arrange everything on this screen except the things they actually look at.

Two pieces of prior art decide most of this design, and using them is the point:

- **`useReorder`** in `FleetProjectColumn.tsx` — a pointer-events reorder with a keyboard
  path, a 4 px engagement threshold, and index-read-from-the-element rather than closed over.
  Every one of those is a defect that was paid for on the live screen (a click that moved a
  row six positions and saved it).
- **The layout document's `order` discipline** — the stored list is authoritative and keeps
  entries discovery did not return, so a project that is temporarily gone does not lose its
  place.

## Goals / Non-Goals

**Goals:**

- Drag a tab, and the agent moves — in the strip and in the grid.
- The order survives a restart of the agents and of the dashboard.
- Nothing the reader placed moves on its own.

**Non-Goals:**

- A computed order (by state, age, activity). A hand-made order and a computed one would
  fight over the same list; if a computed view is ever wanted it is a MODE, like the column's
  live mode, which reorders nothing and stores nothing.
- Moving an agent between projects.
- Ordering the docked agents. A docked panel has left the grid; its place is its edge.

## Decisions

### D1 — The identity is the terminal label, then the name, then the pid

`agentKey(a) = a.terminal_label ?? a.name ?? "pid:" + a.pid`.

A pid is the obvious key and the wrong one: it dies with the process, so an order stored by
pid is forgotten exactly when the reader would notice — after a restart. The terminal label is
what the layout document already keys agent panels by (`PANEL_AGENT`, `id: label`), and the
rename path already carries dock ids (`relabel_dock`), so an ordered agent follows a rename
for free by using the same identity.

`pid:` is prefixed on the fallback so a pid can never collide with a label that happens to be
digits.

### D2 — Its own route: `PUT /api/fleet/layout/agent-order`

Mirrors `PUT /api/fleet/layout/docks` exactly, including the requirement to carry the project:
an order belongs to one project's agents, and a screen-wide store is the defect docking
already had (a terminal docked in one project occupying the same edge in every other).

Not a field on the whole-document PUT, for the reason that route's own docstring gives: it is
guarded by `base_version`, and a drag would have to either bump the version — making the
reader's next group edit conflict with their own dragging — or skip the guard, which puts an
unguarded write on the route that exists to guard.

Last-write-wins, deliberately: what is lost in a race is one sequence, re-dragged in a second.

### D3 — The stored list keeps what is not running

`orderAgents(agents, order)` returns the agents named by `order`, in that order, followed by
every agent the order does not name in discovery's order. The stored list itself is never
pruned to what is running — the same rule the project groups follow, for the same reason: a
stopped agent that lost its slot comes back somewhere else, and the reader's arrangement
rewrites itself.

The two halves fail in opposite directions and both are silent, which is why the spec states
each as its own scenario.

### D4 — `useReorder` is EXTRACTED, not reimplemented

It moves to `web/src/lib/useReorder.ts` and takes an axis (`'y'` for the column, `'x'` for the
strip). Only the axis differs: the midpoint test reads `clientX`/`width` instead of
`clientY`/`height`.

A second copy would be a second place for the four lessons that hook already holds — the
threshold, the engaged flag, the index read off the element, the refocus after a keyboard
move. Those are not preferences; each is a bug that reached the running screen once.

*Alternative considered — HTML5 drag-and-drop for the strip.* Rejected for the reason the hook
already documents: a synthetic `dispatchEvent` in a test only imitates it, while pointer events
are what real input produces, and the keyboard path is what a test can actually assert.

### D5 — One list, sorted once

`gridAgents` is sorted by the order, and `AgentTabs` is handed `gridAgents`. The strip and the
grid therefore cannot disagree, because there is nothing to disagree with: they read the same
array. The alternative — sorting in each place — is the two-copies-of-one-fact shape this
screen has already been bitten by (the header that counted `active.agents.length - 1` above a
strip rendering a filtered list).

### D6 — The order is applied AFTER the dock filter

`gridAgents` filters out docked agents first, then sorts. A docked agent is not in the grid to
be ordered within it, and its stored place is kept for when it returns — which is D3 again,
from the other direction.

## Risks / Trade-offs

- **Two dashboards ordering at once** → last-write-wins, and the loss is one sequence. Named
  rather than guarded, exactly as for the dividers.
- **An agent with neither label nor name** → keyed by `pid:<n>`, so its order does not survive
  a restart. Stated rather than hidden: those are the foreign/orphaned agents the screen did
  not start, and they have no durable identity to offer.
- **The extraction touches the project column** → it is the highest-traffic reorder on the
  screen. The column's existing tests are the check, and they must stay green without being
  edited; a test that had to be adjusted to keep passing would mean the extraction changed
  behaviour.

## Migration Plan

Additive. A layout document with no `agent_order` section behaves exactly as today
(discovery's order), so nothing needs migrating and a rollback is the revert.

The web build must be rebuilt and `set-web` restarted for the new route.

## Open Questions

None.
