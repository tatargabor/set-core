## Why

The wave-board page answers "where is the job, wave by wave", but not "what is in flight and
what is stuck right now" — for that a reader has to scan every wave's list. A board owner
asked for a kanban-style view beside the wave view, over the same data, so the status columns
read at a glance.

## What Changes

- The board page gains a second view, **Kanban**, beside the existing wave view (**Waves**).
  A toggle switches between them; the choice is remembered per viewer in browser storage and
  the page works without it (falls back to Waves).
- Kanban shows four columns — to do, in progress, blocked, done — with one card per item.
  Skipped items are not a column: they sit folded in a collapsed strip under the board, with
  their count visible.
- Each card shows the item id and title, its wave as a coloured tag, the updated time and
  machine, and the note as a collapsed body the reader can open.
- A wave filter narrows the Kanban view to one wave; "All waves" is the default.
- No new storage, no change to the `board/state` payload or the seed, and the page still
  never writes. The header summary (overall counts and strip) is shared by both views.
- UI strings stay English (set-core is public); the light theme stays the default.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `wave-board`: the board page gains a Kanban view with a per-viewer view toggle and a wave
  filter (one added requirement); the existing read-only/offline requirement is unchanged.

## Impact

- `templates/waveboard/page.html` — the only code file (CSS + the inline script).
- `tests/unit/test_wave_board.py` — assertions on the rendered page.
- No change to `bin/set-wave-board`, the hook, the payload schema, or deployed settings.
  Existing boards pick the view up the next time their owner runs `set-wave-board render`
  and republishes.
