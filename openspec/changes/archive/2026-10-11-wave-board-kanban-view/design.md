## Context

The board page (`templates/waveboard/page.html`) is one self-contained file: tokens and CSS,
a static shell, and an inline script that renders `board/state` from the `db` capability or
from the embedded seed. `set-wave-board render` replaces the seed marker and nothing else, so
anything added to the template reaches every board on its next render. The page is a
published artifact, so it follows the artifact contract: light tokens on `:root`, dark under
the system preference and `data-theme="dark"`, no horizontal scroll at phone width.

## Goals / Non-Goals

**Goals:**
- A second view over the same items, switchable in place, remembered per viewer.
- Columns that answer "what is in flight, what is stuck" without scanning waves.

**Non-Goals:**
- Moving cards (drag and drop) — the page is read-only by requirement; status comes from
  evidence, not from a click.
- Any change to the payload, the seed, `bin/set-wave-board`, or the hook.
- A per-board default view chosen by the owner.

## Decisions

- **One render function per view, one shared header.** `render(state)` keeps the header
  (title, sync line, overall summary and strip) and dispatches to `renderWaves` or
  `renderKanban` on the kept state. Switching views or filters re-renders from the kept
  state, so there is no second copy of the data to drift. Alternative considered: render both
  views and hide one with CSS — rejected, it doubles the DOM and makes a hidden view's
  content reachable by find-in-page.
- **localStorage key `waveboard.view`, every access in try/catch.** Per the artifact
  contract browser storage can throw or come back empty; the fallback is Waves. The wave
  filter is NOT persisted: a filter remembered across visits would open a board narrowed
  without the reader having chosen it that day.
- **Skipped as a `<details>` strip, notes as `<details>`.** Native disclosure: keyboard and
  screen-reader behaviour for free, no script state, and opening one never shifts other
  columns (each card grows inside its own column).
- **Wave tag colour from the wave's index**, cycling a small fixed palette defined as
  tokens with a dark-mode counterpart. Index rather than a hash of the id, so neighbouring
  waves never collide by accident; stable as long as wave order is stable, which it is in a
  given job.
- **Column order to do → in progress → blocked → done.** Left-to-right flow; blocked sits
  next to in progress where the reader is already looking, and is coloured with the existing
  `--blocked` token so red keeps one meaning.
- **Phone width:** columns stack into one column below 720 px, each keeping its header and
  count, so nothing scrolls sideways.

## Risks / Trade-offs

- [A long board makes the Kanban columns very tall] → cards are compact (one title line,
  folded note); the wave filter narrows it.
- [The filter hides a blocked item] → the filter control states the hidden blocked count
  (spec scenario), and the header's overall legend still counts every blocked item.
- [Existing published boards do not change until re-rendered] → expected; the owner
  re-renders and republishes, which is the existing update path.
