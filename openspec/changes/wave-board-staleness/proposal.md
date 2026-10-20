## Why

Wave boards go stale, and nothing says so (bug register B-165). Measured on 2026-10-20 across 8
boards: the evidence-driven `sync` was at a fixed point on every one, yet the repositories had
moved 1 to 438 commits past each board's last change. One board tracked a release that had
been tagged the day after it last moved, and it still showed open and blocked items.

The cause is structural, not a broken run. **70 of the 168 unfinished items carry no evidence**,
and a `blocked` item cannot be moved by evidence by design. Both kinds change only when an agent
runs `set-wave-board set`. The Stop hook blocks only when there is an unpushed payload, so a
board whose manual items were never updated has nothing to push and never prompts.

The fleet popover then shows that stale board as an ordinary "in progress" row, with its
blocked count on the header chip, so the screen reports a calm nobody has measured.

## What Changes

- **A review reminder in the Stop hook.** When a board has open items that only an agent can
  move, and the repository has at least N commits on `HEAD` since the board last changed, the
  hook blocks the stop. It lists those items and the command to run, and backs off per job,
  separately from the push reminder.
  - When both reminders are due, they go out in one block.
- **`set-wave-board reviewed <job>`.** It records in the tracked job file that an agent checked
  the manual items and found them current, so a board that is right but quiet stops reading as
  stale. It is not part of the pushed content, so it never causes a push.
- **`set-wave-board stale`.** It lists each board's staleness (commits since its last change,
  and its manual open items) for a person or the hook. It is read-only.
- **A staleness measurement in `GET /api/fleet/waveboards`.** Each readable board gains:
  - `reviewed`;
  - `commits_since_change`, which is null when it cannot be measured, never zero;
  - `manual_open`;
  - `stale`.
- **A stale marker in the fleet popover row and a stale count on the closed chip.** A stale
  board is visible without opening anything, the same way a blocked or unreadable one is.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `wave-board`: the job file may carry a `reviewed` stamp. The Stop hook gains a review
  reminder beside the push reminder. The tool gains `reviewed` and `stale`.
- `fleet-wave-overview`: the summary gains the staleness fields. The popover row and the
  closed chip mark a stale board.

## Impact

- `bin/set-wave-board`: the `reviewed` and `stale` commands, and the staleness computation.
- `bin/set-hook-waveboard`: the review reminder, its backoff and its off switch, and the
  combined block.
- `lib/set_orch/fleet/waveboards.py` (Layer 1): the staleness fields. It reads git
  (`rev-list --count`) under a timeout, and nothing is written.
- `web/src/lib/fleetWaves.ts` and `web/src/components/FleetWaves.tsx`: the row marker and the
  chip count.
- Tests: `tests/unit/test_wave_board.py`, `tests/unit/test_fleet_waveboards.py` and
  `web/tests/unit/fleetWaves.test.ts`.
- **Reach.** `set-hook-waveboard` and `set-wave-board` are linked from this checkout onto
  `PATH`, so every project with a `docs/waveboard/` directory gets the new reminder on its next
  Stop, with no redeploy. The reminder asks the project's own agent to edit the project's own
  tracked job file. set-core itself writes nothing into a project tree beyond the existing
  machine-local `.set/waveboard/` stamps.
