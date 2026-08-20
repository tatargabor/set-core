# Docking on the fleet screen belongs to a project, not to the screen

## Why

Docking was stored screen-wide: one flat list in `fleet-layout.json`, on the
reasoning that a docked band is a property of the screen rather than of a
project. The reasoning was tidy and the effect was not.

A dock entry's identity is a panel id, and for the commonest kind — an agent
panel — that id is a terminal label, which belongs to exactly one project. Held
screen-wide, a terminal docked while looking at one project took the same edge
in **every** project. Nothing there could render in it, so the band could only
say *"no running agent with this terminal in <the project you are looking at>"*.

Reported by the user on 2026-08-20 from a screenshot of the live screen —
*"layout nem projekt szinten van hanem globálisan. ez nem jó, projekt szinten
kell értelmezni"* — with the whole right-hand side of the fleet screen taken by
an empty band naming a project they were not looking at.

Measured on the live store the same day: `docks` held
`[{"kind": "agent", "id": "<a project's terminal label>", "edge": "right"}]`,
one entry, rendering in all 51 projects.

The failure direction is the reassuring one: nothing throws, nothing is counted,
and the screen still looks like a layout. It is the false-absence class produced
by the layout itself, which is the class this screen exists to refuse.

## What Changes

- Docking is stored **keyed by project**. `PUT /api/fleet/layout/docks` carries
  the project and replaces only that project's list; the whole-document `PUT`
  takes the same map. A write without a project is refused (400 at the route,
  `ValueError` in the store) rather than defaulting — the missing project IS the
  defect, and a default is how the shape comes back.
- The screen renders the **selected project's** docking and nothing else.
- Docking arranged before this change is **preserved verbatim** under
  `docks_legacy` and rendered by nobody. It is not adopted into a project: the
  document does not say which project each entry belonged to, and guessing is
  what produced the defect. A person re-docks the panel where they want it.
- **BREAKING** for the `docks` shape of `GET/PUT /api/fleet/layout` and
  `PUT /api/fleet/layout/docks`: a list becomes a map keyed by project. Both
  sides ship together; a client reading the old flat shape reads it as nothing
  docked rather than as everyone's docking.

## Impact

- Affected specs: `fleet-dockable-views`
- Affected code: `lib/set_orch/fleet/layout.py`, `lib/set_orch/api/fleet.py`,
  `web/src/lib/fleetDocks.ts`, `web/src/pages/Fleet.tsx`
- Not affected: divider positions (`splits`). The project column's width is the
  screen's, and a docked band's size is keyed by the band's own identity, which
  already carries the project through the label.
