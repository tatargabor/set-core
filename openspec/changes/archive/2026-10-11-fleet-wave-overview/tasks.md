## 1. Reader and endpoint (Layer 1 core + API)

- [x] 1.1 `lib/set_orch/fleet/waveboards.py`: `summarise_board(path)` and `read_waveboards(projects)` — per-status counts, wave count, current wave, latest `updated`, unreadable entries with a reason; no item title or note in the output; logging per the code-quality rule [REQ: the-fleet-summarises-every-known-project-s-wave-boards]
- [x] 1.2 Unreadable files (bad JSON, wrong schema) become entries, never omissions [REQ: a-board-that-cannot-be-read-is-reported-never-dropped]
- [x] 1.3 `GET /api/fleet/waveboards` in `lib/set_orch/api/fleet.py`, projects from `discover_projects([], registered, messaging)` [REQ: the-fleet-summarises-every-known-project-s-wave-boards]
- [x] 1.4 `tests/unit/test_fleet_waveboards.py`: counts + current wave, finished board, no directory, malformed file beside a good one, no item title/note in the payload; each test shown to fail against a mutated reader [REQ: the-fleet-summarises-every-known-project-s-wave-boards]

## 2. Fleet screen (web)

- [x] 2.1 `web/src/lib/fleetWaves.ts`: types, `orderBoards(boards, selected)`, `totals(boards)`, `barSegments(counts)` [REQ: the-chip-opens-a-floating-list-of-the-boards]
- [x] 2.2 `web/src/components/FleetWaves.tsx`: the chip (board count, blocked count in the failure colour, unreadable count) — hidden when no board exists; fetch on mount and every 60 s [REQ: the-fleet-header-carries-a-wave-board-chip]
- [x] 2.3 The floating list: absolute + z-index, close button, Escape, outside click; rows with project jump, title link (new tab) or "not published", progress bar, blocked count, current wave, age [REQ: the-chip-opens-a-floating-list-of-the-boards]
- [x] 2.4 Mount in `web/src/pages/Fleet.tsx` header; project jump calls `setSelected` [REQ: the-chip-opens-a-floating-list-of-the-boards]
- [x] 2.5 `web/tests/unit/fleetWaves.test.ts`: ordering (selected first, then by name), totals, bar math, unreadable counted [REQ: the-fleet-header-carries-a-wave-board-chip]

## 3. Verification

- [x] 3.1 `pnpm build` in `web/`, restart `set-web`, and LOOK at the fleet in Chrome: chip, open list, project jump, page link, nothing pushed, phone width [REQ: the-chip-opens-a-floating-list-of-the-boards]
- [x] 3.2 Run the new pytest and vitest files and the existing fleet API tests [REQ: the-fleet-summarises-every-known-project-s-wave-boards]

## Acceptance Criteria (from spec scenarios)

### The fleet summarises every known project's wave boards
- [x] AC-1: WHEN a job file has wave w0 all done and w1 with one doing and one todo THEN the entry counts them and names w1 current [REQ: the-fleet-summarises-every-known-project-s-wave-boards, scenario: a-board-s-counts-and-current-wave]
- [x] AC-2: WHEN every item is done or skipped THEN the current wave is null [REQ: the-fleet-summarises-every-known-project-s-wave-boards, scenario: a-finished-board]
- [x] AC-3: WHEN a known project has no docs/waveboard/ THEN no entry and no error [REQ: the-fleet-summarises-every-known-project-s-wave-boards, scenario: a-project-without-boards]

### A board that cannot be read is reported, never dropped
- [x] AC-4: WHEN one job file is invalid JSON and another is valid THEN an unreadable entry and a full entry are both returned [REQ: a-board-that-cannot-be-read-is-reported-never-dropped, scenario: malformed-job-file]

### The fleet header carries a wave-board chip
- [x] AC-5: WHEN two boards hold 3 and 11 blocked THEN the closed chip shows 14 blocked in the failure colour [REQ: the-fleet-header-carries-a-wave-board-chip, scenario: blocked-items-are-visible-on-the-closed-chip]
- [x] AC-6: WHEN no project has a board THEN no chip is shown [REQ: the-fleet-header-carries-a-wave-board-chip, scenario: no-boards]

### The chip opens a floating list of the boards
- [x] AC-7: WHEN the reader activates a row's project name THEN the fleet selects it and the list closes [REQ: the-chip-opens-a-floating-list-of-the-boards, scenario: jumping-to-a-project]
- [x] AC-8: WHEN a board has a page URL and its title is activated THEN the page opens in a new tab [REQ: the-chip-opens-a-floating-list-of-the-boards, scenario: opening-a-board-page]
- [x] AC-9: WHEN a board's page URL is null THEN its title is plain text marked not published [REQ: the-chip-opens-a-floating-list-of-the-boards, scenario: unpublished-board]
- [x] AC-10: WHEN project B is selected and boards exist in A and B THEN B's are listed first [REQ: the-chip-opens-a-floating-list-of-the-boards, scenario: selected-project-first]

## Verification record (2026-10-11)

- `pytest tests/unit/test_fleet_waveboards.py` — 10 passed. Mutation round on the reader: 7 mutants (skipped holding a wave open, unreadable boards dropped, the last open wave taken as current, unknown status dropped, non-https URL offered as a link, an item note in the payload, the same root read twice) — all 7 caught.
- `vitest run tests/unit/fleetWaves.test.ts` — 10 passed. `tsc -b` clean.
- Live endpoint against this machine's registry: every board the job files hold is returned (measured with a direct call and over HTTP after a `set-web` restart).
- LOOKED at it in Chrome on the running dashboard: the closed chip shows the board count and the blocked total in red; the list floats under the header (header height and the shell's top edge identical before and after opening); Escape and an outside click close it; a project click selected that project and closed the list, and on reopening that project's boards came first; every published board's title is a new-tab link (`target=_blank`, `rel=noopener noreferrer`, https only); the unpublished one reads "not published".
- Phone width (390 px, headless — this Chrome window cannot be resized): the first build squeezed the bar to nothing and clipped the age; rows now stack below `sm` and the bar keeps a minimum width. Re-shot after the fix: the list sits inside the viewport, `scrollWidth` 390 = viewport.
- Regression: the failures in `test_fleet_api.py` (rename carries `agent_order`) and in `fleetArrangement` / `fleetSurface` / `fleetTileClick` also fail on a clean HEAD worktree, and the flaky set moves between runs on both sides — already registered (B-130, B-136, the rename entry). Not caused by this change.
