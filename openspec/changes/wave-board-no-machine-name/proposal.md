## Why

`wave-board-assignees` removed the machine name from board items, and the spec now says no
command writes a machine name into the job file or the payload. Two writers were missed, and the
spec still required one of them:

- `set-wave-board reviewed` writes `reviewed: {at, by: <hostname>}` into the TRACKED job file
  (`docs/waveboard/<job>.json`). The requirement for `reviewed` demands that `by`, which
  contradicts the assignees requirement in the same spec. Reported over the bus by a peer
  session (set-core relay, 2026-11-13).
- `sync` writes `synced_by: <hostname>` into the state and combined payloads, which the agent
  pushes into the published board's database. The board page shows it in the "blocks" tooltip
  ("Read from the boards on <host>"), and the combined page shows it on the sync line. Measured
  on 2026-11-13: `bin/set-wave-board:804` and `:826` write it, `templates/waveboard/page.html:540`
  and `templates/waveboard/combined.html:364` render it.

A machine name tells the board's readers nothing. In a tracked file or a published page it
leaks a hostname.

## What Changes

- `reviewed` records `{at}` only, and a legacy `reviewed.by` is dropped on the next write
  (the same rule `_drop_by` applies to items).
- `sync` and the combined seed no longer carry `synced_by`. `synced_at` stays.
- The page tooltip and the combined sync line no longer render a machine. The tooltip says
  where the dependency was read from, without naming a machine.
- `pushed.json` keeps its local `by`: it is per-machine state, gitignored, never published.

## Capabilities

### Modified Capabilities

- `wave-board`: the sync payload fields, and the shape of the `reviewed` stamp.

## Impact

`bin/set-wave-board`, `templates/waveboard/page.html`, `templates/waveboard/combined.html`,
`tests/unit/test_wave_board.py`. Boards already published keep the old page until republished;
the old page falls back to its own text when `synced_by` is absent.
