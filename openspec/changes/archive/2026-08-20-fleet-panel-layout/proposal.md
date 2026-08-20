## Why

The fleet screen can only lay out ONE kind of panel. Agent tiles go into a 1–4
column grid, and there is no concept of a panel that is not an agent. The next
thing the user asked for — a view that lists changes and bugs, lets them be
selected, and schedules them in waves — has nowhere to be put, and neither does
anything after it.

Stated by the user on 2026-08-20, in the same breath as the view itself:
*"lehet, hogy tudni kéne mind a négy irányba, jobbra, balra, felül, alul, egy
megadott view-t, instance-t, azt mondom neki, hogy te itt jobbra"*, and
*"a projekt oldali elválasztó és az új nézetes elválasztó is állíthatóak
legyenek, megfogom és húzom 2 irányba. ezt is mentsük az appconfigba"*.

⚠ **Part of this shipped before this change existed, and that is the reason the
change is being written now rather than the reason it can be skipped.** Commit
`797f7af5` delivered the draggable divider — including a new route
(`PUT /api/fleet/layout/splits`) and a new field in the stored document
(`splits`). Both are contract changes, which the repository's own rule routes
through OpenSpec; only a measured defect fix may go by direct commit. So the
divider capability below is documented retroactively with its tasks already
checked and its evidence named, exactly as `2026-07-24-consumer-status-contract`
did. The docking half is unbuilt and its tasks are open.

## What Changes

- **A pane's edge can be dragged, and where it ends up is remembered on the
  server.** Not in `localStorage`: the same reasoning the arrangement already
  uses — a position set by hand and relied on should not differ between two
  browsers on the same machine. It rides in the existing `fleet-layout.json`
  under `splits`, so no second store is introduced. **SHIPPED (`797f7af5`).**
- **A divider position is written through its own route**, never through the
  version-guarded whole-document PUT. Routing it there would force a choice
  between two defects: bump the version, and the user's next arrangement edit
  conflicts with their own dragging; or skip the guard, and an unguarded write
  now lives on the route that exists to guard. **SHIPPED (`797f7af5`).**
- **An absent divider position means "never dragged", and is never a zero.** A
  pane stored at zero renders as no pane, and the edge needed to drag it back is
  exactly what is no longer on screen — the false-absence class in its expensive
  direction. **SHIPPED (`797f7af5`).**
- **A panel has a TYPE.** The screen today assumes every panel is an agent
  terminal. A panel type is declared by whatever opens the panel, so a screen
  that meets a type it does not know says so rather than rendering an agent tile
  with missing fields.
- **A view instance can be docked to any of the four edges**, taking its space
  out of the area the column grid then lays itself out in. The grid does not
  learn about docking; it is handed a smaller box.
- **A docked view's edge is draggable and stored**, by the same mechanism and in
  the same document as the project list's — one divider component, not a second
  one that gets the keyboard support left out of it.
- **Nothing that is docked can hide a failure without saying so where the reader
  stands.** `ui-quality.md`'s rule applied to a new hiding place: docking is a
  layout that removes things from view, so a docked view that holds a failing
  item must mark it on its collapsed edge.

Deliberately **out of scope**, and named so a later reader can tell *scheduled*
from *forgotten*: the changes-and-bugs view itself (its content, its selection
model, and the wave scheduling behind it) is the first CONSUMER of what this
change builds, and belongs in its own change together with the wave dispatcher
that `agent-goal-and-lifecycle` already names as depending on it. Worktrees as
first-class places in the fleet is a third, and touches discovery rather than
layout.

## Capabilities

### New Capabilities

- `fleet-panel-dividers`: a pane's edge is draggable with a pointer and reachable
  with a keyboard; its position is stored per divider in the framework's durable
  per-user document, clamped to what the surface can render and recover; an
  absent position is the caller's default rather than a zero; and storing one
  neither disturbs the hand-made arrangement nor moves the version that guards it.
- `fleet-dockable-views`: the screen lays out panels of more than one declared
  type; a view instance may be docked to any edge and takes its space from the
  area the agent grid then fills; a panel type the screen does not recognise is
  reported as unrecognised rather than rendered as the type it is not.

### Modified Capabilities

<!-- None. `agent-fleet-surface` describes what a TILE shows; this change is
     about where panels go and how the space between them is divided. Its delta
     also currently lives unarchived in the `fleet-view` change, so adding a
     second delta for the same capability from here would produce two
     uncoordinated edits to one spec. -->

## Impact

- `lib/set_orch/fleet/layout.py` — `splits` in the stored document, its
  normalisation, and a writer that does not bump the arrangement's version.
- `lib/set_orch/api/fleet.py` — `PUT /api/fleet/layout/splits`; `splits` on the
  whole-document body as an omissible field whose omission preserves.
- `web/src/lib/fleetSplits.ts`, `web/src/components/FleetSplitter.tsx` — the
  client store and the divider component (both axes, both sides).
- `web/src/pages/Fleet.tsx`, `web/src/components/FleetProjectColumn.tsx` — the
  shell that owns the widths, and a column whose width is a prop.
- Unbuilt: a panel-type registry and the docking shell in `web/src`, plus
  whatever of it the stored document has to carry.
- No consumer-facing contract is touched, and no domain reaches the framework:
  a panel type is a framework word, and what a view SHOWS stays on the project's
  side of the abstraction.
