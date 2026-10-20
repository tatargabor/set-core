## Why

The Project Status screen is honest and unusable at the size real answers have reached. Both
halves of that sentence are measured, and the second is now the binding one: the user asked
for the screen to be brought to the dashboard's own standard — terminal-styled, dense,
navigable, using the screen it has — and the release-preparation work makes this screen a
decision surface rather than a viewer.

Measured on `HEAD` and on a live answer:

1. **The page is capped at `max-w-5xl`** (`ProjectStatus.tsx:209`) on a screen more than twice
   that wide. A live answer runs to dozens of rows across nine columns; the later columns sit behind
   a horizontal scrollbar inside a container using half the available width.
2. **There is no filter, no search and no sort.** Every row renders in delivery order, every cell
   wrapping to its natural height, so a row is 3–5 lines tall and a screenful holds about
   eight of them. Finding one item means scrolling and reading.
3. **Density is unmanaged, not chosen.** `max-w-[26rem]` per cell (`StatusValue.tsx:400`) is
   the only constraint; a long title decides the height of every column in its row.

The screen's existing rules are not the problem — they are what makes this worth specifying
rather than restyling. *Compacting must never hide a failure* already governs the one place
the surface shortens anything. A filter is a compaction mechanism with a much larger blast
radius: it can hide **rows**, and the reader chose it, which is exactly when a hidden failure
is least likely to be looked for.

## What Changes

- **The screen uses the width it has.** The layout cap is removed; the table scrolls
  horizontally inside its own container so the page itself never does.
- **One line per row, with the complete record one click away.** Cells clip rather than wrap;
  opening a row shows every field of it, untruncated, with the deprecation and emphasis rules
  unchanged.
- **Search and facet filters derived from the SHAPE of the data**, never from a column name.
  A column becomes a facet when its values are scalars and few enough to be a category; the
  chip counts come from the data, exactly as the deprecation count does.
- **Sorting that can be undone back to the project's own order**, because the delivery order is
  the project's decision and this surface has already learned once that position carries
  meaning (`sections`).
- **Every hidden row is stated where the reader is standing**, and clearing is one click. A
  filtered table says how many rows it is not showing, always.
- **Terminal styling consistent with the rest of the dashboard** — monospace, hairline rules,
  sticky header, `tabular-nums` — reusing the existing TUI vocabulary for the frame **only**.

## What This Deliberately Does NOT Change

- **No field name is recognised, anywhere.** The facet mechanism is shape-driven for the same
  reason the renderer is: a surface coupled to one project's vocabulary stops working for the
  second project, and this one is meant to be reused.
- **The `tui.tsx` status vocabulary is NOT applied to contract data.** `TuiStatus` colours
  `done` / `running` / `failed` — set-core's words for set-core's runs. Colouring a project's
  `status` cell with them would be name recognition arriving through a styling helper, and it
  would silently mean *set-core decided what the project's word means*.
- **Nothing is persisted, and that now includes the URL.** A chosen facet value is the
  consumer's domain data. `localStorage` and the address bar both reach disk, so filter state
  stays in memory — see the design's D2.
- **The unmarked-bad-news gap is not addressed here.** A command answering `ok: true` while its
  data reports blockers needs the project to declare which values are problem indicators; that
  is a contract change, not a layout change, and it is recorded as its own candidate.

## Impact

- `web/src/pages/ProjectStatus.tsx` — layout width, the table region, filter and search state.
- `web/src/components/StatusValue.tsx` — the table: clipping, row detail, sort, facets.
- `web/tests/unit/statusValue.test.tsx` — the existing honesty tests stay; new ones cover the
  hiding.
