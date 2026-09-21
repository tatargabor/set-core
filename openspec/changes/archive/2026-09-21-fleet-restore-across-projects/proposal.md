## Why

Restore is reachable only one project at a time. To bring back an earlier session, the user
has to select its project in the column, open that project's "recorded here, not open" dialog,
tick, confirm, and then do the same for the next project. The one place that lists every
project with a record, `RestoreFromEmpty`, renders only when **nothing** is running anywhere,
so it cannot be reached while any agent is running, which is the ordinary state.

The user asked for it directly on 2026-09-21 (dictated): reopen any past session, from any
project, **in one window, without doing it one by one from the project folder**, from an icon
placed right after the status icons at the top of the fleet's project column.

The volume is what makes the per-project route expensive. Measured on this machine the same
day with `GET /api/fleet/roster`: **34 projects, 527 recorded entries, 2 running**.

## What Changes

- A **fleet-wide reopen control** in the project column's attention row, right after the
  status chips. It works without a selected project and renders only when the record holds
  something.
- It opens **one dialog** listing every project that has a record, newest first. Each project
  expands to its recorded entries, grouped into lineages and with the per-entry peek, both
  reused from the per-project dialog. Each project's list is read only when that project is
  opened.
- **Selection spans projects.** A single armed act states the number of agents and projects
  before it runs (`Start 5 agents in 3 projects?`), then posts each project's selection to the
  existing per-project restore route.
- The result is reported **per project** and summed across projects, and it reads as
  complete only when every project's own result was complete and no project's request failed.
  A project whose request failed (for example a 503 because the owner is unreachable) is named
  together with its error.
- **No backend change.** The existing routes already carry everything this needs
  (`GET /api/fleet/roster`, `GET /api/fleet/roster/{project}`,
  `POST /api/fleet/roster/{project}/restore` with `keys`, and the peek route).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-fleet-restore`: adds a cross-project restore surface beside the per-project one.

## Impact

- `web/src/components/FleetRestore.tsx`: the lineage list is extracted for reuse, and a new
  `RestoreAcrossProjects` component is added.
- `web/src/lib/fleetRoster.ts`: two new pure functions, `offerAcross()` and `summariseAcross()`.
- `web/src/components/FleetProjectColumn.tsx`: mounts the control in the attention row.
- Tests: `web/tests/unit/fleetRoster.test.ts` and `web/tests/unit/fleetRestoreSurface.test.tsx`.
