## Why

Projects now keep wave boards — one tracked job file per multi-step job, published as a
read-only Kanban page — so where development stands, what is planned and how fast it moves
is recorded per project. But each board is reachable only from inside its own project, so
seeing the state of every project means opening every project. The user asked (2026-10-11)
for the fleet, the cross-project screen, to carry them: one place to see every board, and
from it a way into the project and onto the board page. "Do not overthink it" was part of
the ask.

Measured 2026-10-11 on this machine: 6 boards in 5 of 53 registered projects, all in the
same `set-wave-board/1` format, 5 of them with a published page.

## What Changes

- A read-only endpoint, `GET /api/fleet/waveboards`, reads `docs/waveboard/*.json` from
  every project the fleet knows and returns one summary per board: project, job, title,
  page URL, per-status counts, the current wave, and when an item last changed. A file that
  cannot be read is returned as an unreadable entry, never dropped.
- A header chip on the fleet screen: the board count, and the blocked count in red when
  any item anywhere is blocked. It opens a floating list (an overlay — it pushes nothing):
  one row per board with a progress bar, the project name (selects that project in the
  fleet) and the board title (opens the board page in a new tab).
- The selected project's boards are listed first.
- Nothing is written anywhere: no new storage, no schema change, no write to a project.

## Capabilities

### New Capabilities
- `fleet-wave-overview`: the fleet's cross-project view of the projects' wave boards — the
  read endpoint and the header chip with its floating list.

### Modified Capabilities
<!-- none: the wave-board job file format and its page are read, not changed -->

## Impact

- New: `lib/set_orch/fleet/waveboards.py` (Layer 1 reader — the wave-board format is a
  framework format, so this is domain-free), a route in `lib/set_orch/api/fleet.py`,
  `web/src/components/FleetWaves.tsx`, `web/src/lib/fleetWaves.ts`, a chip in
  `web/src/pages/Fleet.tsx`.
- Tests: `tests/unit/test_fleet_waveboards.py`, `web/tests/unit/fleetWaves.test.ts`.
- The running `set-web` service must be restarted and `web/` rebuilt for the screen to
  show it.
