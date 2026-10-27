## 1. Template

- [x] 1.1 Split the page script's render into a shared header and per-view renderers; keep the wave view's output unchanged [REQ: the-board-page-offers-a-kanban-view]
- [x] 1.2 Add the Waves / Kanban toggle, persisted under `waveboard.view` with every storage access in try/catch and Waves as the fallback [REQ: the-board-page-offers-a-kanban-view]
- [x] 1.3 Render the Kanban columns (to do, in progress, blocked, done) with counts, one card per item: id, title, wave tag, updated/by, note in a collapsed `<details>` [REQ: the-board-page-offers-a-kanban-view]
- [x] 1.4 Render skipped items in a collapsed strip with the count in its summary [REQ: the-board-page-offers-a-kanban-view]
- [x] 1.5 Add the wave filter (all waves by default, not persisted) that states the blocked count it hides [REQ: the-board-page-offers-a-kanban-view]
- [x] 1.6 Keep view and filter across live `board/state` snapshots [REQ: the-board-page-offers-a-kanban-view]
- [x] 1.7 Wave tag palette as tokens with dark counterparts; columns stack below 720 px with no horizontal scroll [REQ: the-board-page-offers-a-kanban-view]

## 2. Tests

- [x] 2.1 Unit tests in `tests/unit/test_wave_board.py`: the rendered page carries both views, the storage key inside try/catch, the four columns and the skipped strip, and still no db write call; prove each new assertion fails against the old template [REQ: the-board-page-offers-a-kanban-view]
- [x] 2.2 Behaviour check of the page script in a real browser against a local render seeded with a copy of a real board's state: column counts, skipped strip, filter + hidden-blocked note, view persistence, storage-throws fallback, live-update keeps the view [REQ: the-board-page-offers-a-kanban-view]

## 3. Visual check

- [x] 3.1 Open the rendered page in Chrome and LOOK at both views, light and dark, desktop and phone width; record what was seen [REQ: the-board-page-offers-a-kanban-view]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a viewer switches to Kanban and reopens the page in the same browser THEN it opens on Kanban [REQ: the-board-page-offers-a-kanban-view, scenario: the-view-choice-is-remembered]
- [x] AC-2: WHEN browser storage throws or returns nothing THEN the page opens on Waves and the toggle still works for the visit [REQ: the-board-page-offers-a-kanban-view, scenario: no-browser-storage]
- [x] AC-3: WHEN the state holds items of every status THEN the four non-skipped ones are cards in their columns with matching counts and the skipped one is only in the collapsed strip with its count [REQ: the-board-page-offers-a-kanban-view, scenario: items-land-in-their-status-column]
- [x] AC-4: WHEN an item in wave w2 has a note THEN its card shows a w2 tag and the note is hidden until opened [REQ: the-board-page-offers-a-kanban-view, scenario: a-card-carries-its-wave-and-a-folded-note]
- [x] AC-5: WHEN the filter is set to one wave and another wave holds a blocked item THEN only that wave's cards show and the filter states the blocked count outside it [REQ: the-board-page-offers-a-kanban-view, scenario: the-filter-does-not-hide-a-blocked-item-silently]
- [x] AC-6: WHEN a new snapshot arrives while Kanban is shown with a filter THEN the new data renders in Kanban with the same filter [REQ: the-board-page-offers-a-kanban-view, scenario: a-live-update-keeps-the-readers-place]

## Verification record (2026-10-11)

- Browser behaviour check (headless Chromium, 22 checks, three consecutive runs all 22/22): default Waves, column order and counts, skipped only in the folded strip, wave tag, folded note, filter narrowing and the hidden-blocked notice, view remembered and filter not, storage-throws fallback, live snapshot keeps view + filter + an opened note, no write call, no horizontal scroll at 390 px in both views. The live path was driven through a stubbed `window.claude` db; the real platform runtime is confirmed only once a board owner republishes.
- Found and fixed on the way, both pre-existing: the overall strip forced a 466 px minimum width on a 67-item board (4 px segments + 3 px gaps), so the page scrolled sideways on a phone; and `.summary { display: flex }` overrode the `hidden` attribute.
- Visual check in Chrome (desktop, light and dark, a copy of a real 66-item board) and screenshots at 390 px: columns, tags, notes, filter notice, skipped strip read correctly.
- The new unit test fails against the previous template and passes against this one; the template was restored byte-identical (sha256 prefix 509857d4f8f94e82 before and after).
- Live runtime confirmed after the owner republished (page version 2): the published artifact shows "Live", Kanban renders the live db data with the same column counts, and after a reload it reopens on Kanban. The viewer preference was set back to Waves afterwards.
