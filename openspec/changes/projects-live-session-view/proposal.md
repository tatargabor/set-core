## Why

The projects screen answers "which projects exist", and the reader almost always arrives
asking a narrower question: **where is anything actually happening right now.** Today that
question has no answer on this screen, and the answer it does give points the wrong way.

Measured on `HEAD`, 2026-08-24, against the running dashboard on port 7400:

1. **`GET /api/projects` returns 39 rows and `Manager.tsx` renders all 39**, sorted by
   `last_updated`, with no filter, no search, and no view control of any kind
   (`web/src/pages/Manager.tsx:73-181` — the only affordance above the table is the
   `show N archived` toggle).
2. **`GET /api/fleet/agents` knows 52 projects, and exactly 6 of them hold a live agent
   session** (`set-core` 10, a consumer project 5, and four framework repos with one
   each). None of that reaches the projects screen.
3. **Two of those six are not in the registry at all** (`tg`, `blackbelt-web` arrive with
   `sources: ["messaging"]`), so a project with a live session can be **absent** from the
   projects table rather than merely mis-stated.
4. The `status` column this screen leans on is the orchestration record, which is already
   known to go stale in the reassuring direction — the fleet became the landing screen
   precisely because the overview reported a project "Stopped, 24 days ago" while six agents
   were working inside it (`web/src/App.tsx:210-222`).

So the screen shows 39 rows of mostly-dormant projects, is silent about the 6 that are live,
and can omit a live one entirely. The reader's own filtering — scrolling and reading — is the
only mechanism on offer.

## What Changes

- **A view control at the top of the projects screen**, switching between the default
  `All` listing and a `Live sessions` view that shows only projects the fleet measures as
  holding at least one live agent session.
- **A name filter** next to it. Typing narrows the rows in either view.
- **A live-session column in BOTH views**, not only in the live one. The count is the fact
  that the stale `status` column cannot carry, and hiding it behind a view mode would leave
  the default screen exactly as misleading as it is today.
- **Projects the fleet sees but the registry does not are shown in the live view, marked.**
  Dropping them would reproduce the false absence this change exists to remove; showing them
  unmarked would claim a registration that does not exist. They are not linkable to a project
  route, and the view says why.
- **Every hidden row is counted where the reader is standing.** A filtered or view-narrowed
  table always states how many rows it is not showing, and clearing is one click. This is
  `ui-quality.md`'s rule ("compacting must never hide a failure") applied to a mechanism that
  hides *rows* and that the reader chose — which is exactly when a hidden failure is least
  likely to be looked for.
- **The fleet being unreachable is a stated absence, never an empty live view.** Zero live
  sessions and "the measurement did not arrive" must not render alike.

- **The same way of looking on the FLEET's project column** — the left panel where the reader
  actually stands, whose hand-made groups, parked section and collapsed blocks are exactly the
  places a live project can hide. It writes nothing: no project moves, no order is saved, and
  the arrangement returns untouched. Its attention header keeps counting the whole column in
  both ways of looking, by construction.
- **Entries sharing a project name are merged, not overwritten.** Measured mid-change: the
  fleet answers with one project twice (a checkout and a worktree of it), and keyed assignment
  let the empty entry erase five live sessions on both surfaces.

Not in this change: grouping, sorting controls, or any change to what
`GET /api/projects` or `GET /api/fleet/agents` return. The screen consumes both as they are.

## Capabilities

### New Capabilities
- `projects-live-session-view`: the view mode, the name filter, the live-session column, the
  unregistered-but-live rows, and the hidden-row accounting on the projects screen.

### Modified Capabilities
<!-- None. `projects-overview` describes a card layout with per-project process controls that
     this screen no longer has (it is a table since the unified-project-routes work); adding
     deltas against text that does not match the code would make the drift harder to see, not
     easier. This change owns the new behaviour and leaves that spec's staleness visible. -->

## Impact

- `web/src/pages/Manager.tsx` — the projects screen (route `/projects`, `web/src/App.tsx:225`).
- `web/src/lib/` — a new pure module for the view/filter model, following the `fleet*.ts`
  pattern (model separate from render, unit-tested without a DOM).
- `web/src/lib/api.ts` — a typed reader for the live-session counts from the existing
  `GET /api/fleet/agents` payload.
- `web/src/components/FleetProjectColumn.tsx` and a second pure module for its view model —
  the fleet screen's project column.
- No Python, no API, no schema change. Read-only consumption of two endpoints that already ship.
