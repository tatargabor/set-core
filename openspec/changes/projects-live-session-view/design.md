## Context

The projects screen (`web/src/pages/Manager.tsx`, route `/projects`) polls `GET /api/projects`
every 5 s and renders one table. The fleet screen (`web/src/pages/Fleet.tsx`, route `/`) polls
`GET /api/fleet/agents` and already owns the typed shapes for that payload in
`web/src/lib/fleetTypes.ts` (`FleetResponse`, `FleetProject`, `FleetAgent`).

So both facts this change needs are already shipping, in a shape another screen already reads.
Nothing here needs a new endpoint, and nothing needs a Python change.

Measured, 2026-08-24, against the running dashboard on port 7400:

- `GET /api/projects` -> 39 rows.
- `GET /api/fleet/agents` -> 72 829 bytes in 0.30 s; 52 `projects`, of which 6 have a non-empty
  `agents` array (`set-core` 10, a consumer project 5, and four with one each).
- 2 of the fleet's projects arrive with `sources: ["messaging"]` and no registry entry.

## Goals / Non-Goals

**Goals**
- A reader arriving at `/projects` can, in one click, see only where work is live.
- The live-session fact is visible without switching view, because the column next to it
  (`status`) is measured unreliable in the calm direction.
- A live project missing from the registry is visible rather than silently absent.
- The fleet being unreachable degrades the screen honestly instead of turning it into zeros.

**Non-Goals**
- Grouping or sorting controls. The existing `sortByLastUpdated` order stays.
- Acting on agents from this screen — that is the fleet's surface and it stays there.
- Fixing, or trusting, the orchestration `status` column.
- Any change to either endpoint's payload.

## Decisions

### D1 — Liveness is `project.agents.length`, carried from the fleet, never inferred here
`FleetProject.agents` is the fleet's own measurement of live agent processes. The projects
screen counts that array and does nothing else with it.

*Alternative rejected:* deriving liveness from `ProjectInfo.status === 'running'` — that field
is the orchestration record, which is exactly what was measured saying "Stopped, 24 days ago"
with six agents inside the project. Using it would rebuild the defect the change removes.

*Alternative rejected:* a new `/api/projects?live=true` server-side filter. It moves a display
decision into the API, and the screen would still need per-row counts for the All view.

### D2 — Three states for the count, not two: a number, a measured zero, and unmeasured
The fleet result is held as `FleetResponse | null`, and `null` propagates to every row as
`liveSessions: null`. A row renders `null` as an explicit unmeasured mark, never as `0`.

This is the repo's recurring shape error — "a zero with an empty breakdown is a shape error
until the input's shape has been inspected", and "a gap is not a zero". A fleet outage that
rendered 39 calm zeros would be more convincing than the screen it replaced.

### D3 — A pure model module, `web/src/lib/projectsView.ts`
One exported function turns `(ProjectInfo[], FleetResponse | null, {view, query})` into
`{ rows, hiddenByView, hiddenByFilter, totalAll, totalLive, liveMeasured }`. `Manager.tsx`
renders that and holds only `view` and `query` in state.

Follows the established `fleet*.ts` split (model in `lib/`, render in the page), which is what
makes the counting testable in `tests/unit/` without a DOM — and the hidden-row counts are the
part most worth testing, because they are how the screen stays honest.

### D4 — Unregistered live projects are synthesised rows, live view only
A fleet project with `agents.length > 0` and no matching `ProjectInfo` becomes a row with
`registered: false`, appended to the live view. It carries the name, the count and a mark; it
carries no `Link`, because the project route it would point at does not resolve.

They are **not** added to the All view: that view's contract is "what the projects endpoint
returned", and injecting rows would make the two views disagree about what a project is. The
live view's own count is where they become visible, which is where the reader is asking.

### D5 — Both facts are polled on the existing 5 s cycle, and they fail independently
The poll in `Manager.tsx` fetches both, tolerating either failing on its own. A fleet failure
leaves `fleet = null` (D2) and the listing intact; a projects failure keeps the existing
back-off behaviour.

*Trade-off:* the fleet payload is 71 KB per poll (measured above), against ~4 KB for the
projects list. Accepted: the fleet screen already polls it at the same rate, so this adds one
more consumer of an existing cost rather than a new cost class. A narrower endpoint would be
an API change, which this proposal excludes.

### D6 — View and filter live in component state, not in the URL or `localStorage`
The spec requires the screen to open on All. Persisting the view would violate that on the
second visit, and persisting a filter is how a reader ends up looking at three rows and
believing they are all of them.

*Alternative deferred, not rejected:* a URL query parameter, which would make a narrowed view
shareable. It is worth having, and it is not worth coupling to this change's honesty rules.

## Risks / Trade-offs

- **A view control is a compaction mechanism with whole rows as its blast radius** -> every
  narrowing states its own hidden count next to the table, and one control clears back to All.
  This is the requirement the unit tests target first.
- **The fleet payload doubles this screen's poll traffic** -> measured 71 KB / 0.30 s, on a
  dashboard that already polls it from another screen at the same interval. Revisit only if a
  measurement shows it costing something.
- **`sources: ["messaging"]` may not be the only way a project reaches the fleet without a
  registry entry** -> the code keys on "no matching `ProjectInfo`", not on the `sources` value,
  so a new source is handled without a change here.
- **A screenshot-green change can still be an unreadable screen** -> `ui-quality.md` requires a
  browser look at `/projects` in both views before this is called done; it is a task, and if
  the browser cannot be reached the task stays open and says so.

## Migration Plan

Additive, front-end only. No data migration, no API change, no deploy step beyond the usual
`pnpm build` in `web/` so port 7400 serves the updated bundle. Rollback is reverting the
commit; nothing persists any new state.

## Open Questions

- Should the live view eventually show the agents' *states* (working / waiting / quiet) rather
  than only a count? The fleet already carries them per agent. Left out here because a state
  breakdown on this screen starts duplicating the fleet screen, and the question the projects
  screen answers is "where", not "what".
