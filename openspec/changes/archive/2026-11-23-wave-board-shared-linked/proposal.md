## Why

The owner gave two orders for wave boards on 2026-11-08. Both reached set-core through a consumer's session:

- *„wave baordokat olyan artifactba kell tenni amit mindenki tud írni … ha akarunk waveboardokat”*. A board must sit
  in an Artifact that every person on the team can write.
- *„a wave boardokat is összevonva kell kezelni, marmint lehetnek külön csak közös alapok, függőségek stb”*. Boards
  may stay separate, but they need a shared base and dependencies between them.

What exists today falls short in three measured ways:

- **Sharing is left to chance.** Only the account that published a board, or an invited editor, can push to it. No
  command says who those editors are or which account should publish. A measurement across the team's boards found
  them published from two different accounts. The hook's own advice for a refused push is
  `SET_WAVEBOARD_PUSH=off`, which silences the board on that machine for good. It should send the agent to ask for
  access instead.
- **No board can wait on another.** Jobs in different projects depend on each other: a migration waits for a tool
  that another board is still building. Today this lives only in a note, which no reader counts and nothing
  enforces.
- **The combined view shows counts only.** The fleet's wave list sums every project's boards, but it does not say
  which board is held up by which.

## What Changes

- **Editor list and share step.** `set-wave-board` reads a machine-local editor list:
  `~/.config/set-core/waveboard-editors.json`, or the path in `SET_WAVEBOARD_EDITORS`. It holds `owner_account` and
  `editors`, and is never written into a repository. `init` and `link` print the share step: claude.ai Share, those
  editors, edit access. They also name the account the session is signed in as, and say whether it is the owner
  account. A new `share [<job>...]` prints the same step for boards that already exist.
- **A refused push asks for access.** When the push is refused for lack of access, the hook's procedure tells the
  agent to ask the owner account for edit access. It no longer offers `SET_WAVEBOARD_PUSH=off`. The skill says the
  same.
- **Cross-board dependencies.** An item may carry `depends_on`, a list of `{project?, job, item}`. A missing
  `project` means this repository; otherwise the project resolves by registry name, the same way `project` evidence
  does. They are set with `add --depends-on` and with `depend` / `undepend`. On each sync the payload gets:
  - `waiting_on` for each open item: its unmet dependencies. An unresolved reference is unmet, never met.
  - `blocks`: the items on any registered project's board that depend on this item.
- **Waiting is blocking.** A dependency is met only when the item it points to is `done`. While a dependency is
  unmet:
  - `set` refuses `doing` and `done` on the item, unless `--force` is given;
  - the page draws a waiting `todo` item as blocked, with a "waits on" chip;
  - the page shows "blocks" on the item that holds others up.
- **The combined view.** Each fleet board summary now carries its dependency edges, by item id and never by title.
  The row shows "waits on N" and "blocks N". The closed chip counts dangling references. `set-wave-board overview`
  prints every registered project's boards and the edges between them.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `wave-board`: the editor list and share step, the access-asking refusal, `depends_on` with `waiting_on` and
  `blocks` in the payload, the `set` guard, the page's waits-on and blocks chips, and `overview`.
- `fleet-wave-overview`: dependency edges in the summary, the row markers, and the dangling-reference count on the
  chip.

## Impact

- `bin/set-wave-board`: editors, account, `share`, `depend`, `undepend`, `overview`, dependency resolution in
  `sync`, and the `set` guard.
- `bin/set-hook-waveboard`: the refusal paragraph.
- `templates/waveboard/page.html`: the waits-on and blocks chips, and the effective blocked status.
- `lib/set_orch/fleet/waveboards.py` (core): dependency edges across the boards it reads.
- `web/src/lib/fleetWaves.ts` and `web/src/components/FleetWaves.tsx`: the markers.
- `.claude/skills/set/wave-board/SKILL.md`: sharing and dependencies.
- Tests: `tests/unit/test_wave_board.py`, `tests/unit/test_fleet_waveboards.py`, and the web unit tests.
- Existing boards: the job-file schema stays `set-wave-board/1` and `depends_on` is optional. A page published from
  the old template ignores the new payload fields until it is republished.
