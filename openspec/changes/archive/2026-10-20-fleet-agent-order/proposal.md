## Why

The agents of a project appear in whatever order discovery returns them. On a project with
four or eight agents that order is not meaningless — it is arbitrary — and it decides two
things the reader cares about: which tab sits first in the strip, and where each agent lands
in the grid.

Asked for 2026-08-26: *"a tabokat akarom tudni húzva rendezni felül és a sorrendet mentve
kialakítani. azt tudjam rendezni a tabokat melyik legyen az első, a gridben is, hogy hova
tartozik"* — drag the tabs, save the order, and have the grid follow it.

The screen already lets the reader arrange everything else by hand: projects into groups, in
an order that is stored; panels to an edge; dividers to a pixel. The agents inside a project
are the one arrangement they cannot make.

## What Changes

- **New**: the agents of a project have a hand-made order. The reader drags a tab to move it,
  or moves it with the keyboard, and the order is saved.
- **New**: that same order lays out the grid. One list governs both surfaces — a screen where
  the tabs say one thing and the grid another would be two answers to one question.
- **New**: an endpoint that stores the order per project, beside the ones that already store
  docking and divider positions.
- The order is by a DURABLE identity — the agent's terminal label, its name, or its pid as a
  last resort — never by pid alone: a pid dies with the process, and an order that forgets
  itself on every restart is not an arrangement.
- An agent the stored order does not name appears LAST, in discovery's order. An agent the
  order names but discovery did not return keeps its place in the stored list, so it returns
  where the reader put it.

## Capabilities

### New Capabilities
- `fleet-agent-order`: the hand-made order of a project's agents — the gesture, the durable
  identity it is stored by, and the two surfaces it governs.

### Modified Capabilities

## Impact

- `lib/set_orch/fleet/layout.py` and `lib/set_orch/api/fleet.py` — one more per-project
  section of the layout document and its own PUT route, following `docks` exactly.
- `web/src/pages/Fleet.tsx` — the tab strip becomes reorderable; `gridAgents` is sorted by
  the stored order.
- `web/src/components/FleetProjectColumn.tsx` — its `useReorder` hook moves to a shared
  module and gains an axis, so the horizontal strip is not a second implementation of a
  gesture whose defects are already paid for.
- No change to discovery, to the agent payload, or to what a tab shows.
