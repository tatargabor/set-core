## 1. The tool (`bin/set-wave-board`)

- [x] 1.1 `manual_open(data)`, `last_change(data)`, `commits_since(root, iso)` and `staleness(root, data)` per D1–D4; `DEFAULT_STALE_COMMITS = 3`, overridable by `SET_WAVEBOARD_STALE_COMMITS` [REQ: a-board-s-staleness-is-measured-in-commits-since-its-last-change]
- [x] 1.2 The `stale [<job>...]` command, text and `--json`, writing nothing [REQ: a-board-s-staleness-is-measured-in-commits-since-its-last-change]
- [x] 1.3 The `reviewed <job>` command: sets the top-level `reviewed` and leaves `content_of()` unchanged [REQ: an-agent-can-record-that-a-board-was-reviewed]
- [x] 1.4 Tests in `tests/unit/test_wave_board.py` for every scenario of both requirements, each proved to fail with its piece reverted [REQ: a-board-s-staleness-is-measured-in-commits-since-its-last-change]

## 2. The hook (`bin/set-hook-waveboard`)

- [x] 2.1 After the sync, run `stale --json`. Add a review section for each stale job outside its review backoff (`.review-nag`, `SET_WAVEBOARD_REVIEW_SECONDS`), skipping it when `SET_WAVEBOARD_REVIEW=off` [REQ: the-stop-hook-asks-for-a-review-of-a-stale-board]
- [x] 2.2 One block per Stop: the push section first, then the review section; up to 20 items and "+N more" [REQ: the-stop-hook-asks-for-a-review-of-a-stale-board]
- [x] 2.3 Hook tests: the stale block with items and commands, the review backoff, both due in one block, the review off switch, the worktree skip; the existing push tests still pass [REQ: the-stop-hook-asks-for-a-review-of-a-stale-board]

## 3. The fleet summary (`lib/set_orch/fleet/waveboards.py`, Layer 1)

- [x] 3.1 `reviewed`, `manual_open`, `commits_since_change` and `stale` on each readable entry. Run git with a 5 s timeout; a failure gives null and a DEBUG log. Still no item title in the response [REQ: the-summary-carries-the-board-s-staleness]
- [x] 3.2 Tests in `tests/unit/test_fleet_waveboards.py`: a repository moved past, reviewed, no git, and titles still absent [REQ: the-summary-carries-the-board-s-staleness]
- [x] 3.3 A cross-check test: the tool's `stale --json` and `summarise_board` agree on `manual_open`, `commits_since_change` and `stale` for the same fixture repository, and on the default threshold (D9) [REQ: the-summary-carries-the-board-s-staleness]

## 4. The popover (`web/src/lib/fleetWaves.ts`, `web/src/components/FleetWaves.tsx`)

- [x] 4.1 Type the new fields as optional, so an older server still renders. `totals()` gains `stale` [REQ: a-stale-board-is-marked-on-the-closed-chip-and-in-its-row]
- [x] 4.2 Add the chip's amber stale count and the row's amber "N commits since" marker with its tooltip. Add "not measured" to the age tooltip when `commits_since_change` is null. Leave a non-stale row unchanged [REQ: a-stale-board-is-marked-on-the-closed-chip-and-in-its-row]
- [x] 4.3 Unit tests in `web/tests/unit/fleetWaves.test.ts` for `totals().stale`, and for the parser keeping old-shape entries [REQ: a-stale-board-is-marked-on-the-closed-chip-and-in-its-row]

## 5. Verification

- [x] 5.1 Run `pnpm build` and `tsc -b` in `web/`, the Python suite as a set diff against a HEAD baseline, and the web unit suite against HEAD's failures — build and `tsc -b` clean. Python: 124 failure entries now against 125 at HEAD (isolated worktree, 0 leaks once the venv is excluded); the only difference is `test_paths.py::TestResolveProjectName::test_resolve_with_explicit_path`, which fails at HEAD and passes here, and is unrelated. Web: 8 failures, all in `designDrift`, `fleetArrangement`, `fleetSurface` and `fleetTileClick`, the files that already failed at HEAD this session; none of `designDrift`'s findings is in a touched file [REQ: a-stale-board-is-marked-on-the-closed-chip-and-in-its-row]
- [x] 5.2 Restart set-web. Compare `/api/fleet/waveboards` on the live machine against the read-only measurement in B-165 — measured after the restart (22:07:17): 9 boards, 6 stale (122, 96, 11, 11, 79, 35 commits since), 3 not (0, 1 or 2, 1). The hook had already fired live before the restart, because `PATH` links to this checkout: in one project the reminder was given at 22:00:06 and the agent committed an updated board 21 s later; in another, the agent ran `reviewed` 13 s after its reminder (21:57:35 → 21:57:48) [REQ: the-summary-carries-the-board-s-staleness]
- [x] 5.3 Browser check: open the fleet, check that the closed chip shows the stale count, open the popover, and read the stale rows' markers and tooltips. Seen 2026-10-20 22:08 in Chrome, through this machine's LAN address because the only connected browser runs on another machine (its own `localhost:7400` is a different, older set-core). Closed chip: `9 · 19 · ⟳6`, with the amber stale count. Open list: the six stale rows end in an amber `⟳ N since`; the three current rows are unchanged. The marker's tooltip names the 5 manual items, the list floats (`position: absolute`) with no horizontal overflow, and a reviewed board's age tooltip says when it was reviewed and that 2 commits followed [REQ: a-stale-board-is-marked-on-the-closed-chip-and-in-its-row]
- [x] 5.4 Close B-165 in `openspec/bugs/README.md` with the commit and the measurement [REQ: the-stop-hook-asks-for-a-review-of-a-stale-board]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a no-evidence `todo` item has 3 commits after its `updated` THEN `stale --json` reports 3, the item as manual, and stale true [REQ: a-board-s-staleness-is-measured-in-commits-since-its-last-change, scenario: commits-after-the-change-make-a-board-with-manual-items-stale]
- [x] AC-2: WHEN an item is set by hand and the job file is committed once THEN stale is false [REQ: a-board-s-staleness-is-measured-in-commits-since-its-last-change, scenario: the-board-s-own-commit-is-not-enough]
- [x] AC-3: WHEN a job holds todo/no-evidence, blocked/evidence, doing/evidence and done/no-evidence items THEN only the first two are manual [REQ: a-board-s-staleness-is-measured-in-commits-since-its-last-change, scenario: only-items-sync-cannot-move-are-manual]
- [x] AC-4: WHEN every open item has evidence and is not blocked THEN stale is false whatever the commits [REQ: a-board-s-staleness-is-measured-in-commits-since-its-last-change, scenario: a-board-whose-items-all-have-evidence-is-never-stale]
- [x] AC-5: WHEN no `updated`, `reviewed` or `created` parses THEN commits is null and stale false [REQ: a-board-s-staleness-is-measured-in-commits-since-its-last-change, scenario: not-measurable-is-null-not-zero]
- [x] AC-6: WHEN `reviewed` runs on a stale job THEN commits is 0 and stale false [REQ: an-agent-can-record-that-a-board-was-reviewed, scenario: a-review-resets-staleness]
- [x] AC-7: WHEN a pushed job is reviewed and synced THEN `pending` does not list it and the stamp remains [REQ: an-agent-can-record-that-a-board-was-reviewed, scenario: a-review-does-not-cause-a-push]
- [x] AC-8: WHEN a stale job without a page URL is seen by the hook in the main checkout THEN one block names the commits, each manual item's id and both commands [REQ: the-stop-hook-asks-for-a-review-of-a-stale-board, scenario: a-stale-board-blocks-the-stop-with-its-items]
- [x] AC-9: WHEN the hook runs again within the review backoff THEN it prints nothing for that review [REQ: the-stop-hook-asks-for-a-review-of-a-stale-board, scenario: the-review-backs-off-on-its-own-clock]
- [x] AC-10: WHEN a job is pending and stale THEN exactly one block holds the push procedure before the review [REQ: the-stop-hook-asks-for-a-review-of-a-stale-board, scenario: both-due-one-block]
- [x] AC-11: WHEN `SET_WAVEBOARD_REVIEW=off` and the job is stale but not pending THEN nothing is printed [REQ: the-stop-hook-asks-for-a-review-of-a-stale-board, scenario: the-review-alone-can-be-switched-off]
- [x] AC-12: WHEN the Stop comes from a linked worktree with a stale job THEN nothing is printed [REQ: the-stop-hook-asks-for-a-review-of-a-stale-board, scenario: a-worktree-is-still-skipped]
- [x] AC-13: WHEN a board has 1 manual item and 5 newer commits THEN the entry carries 1, 5 and stale true [REQ: the-summary-carries-the-board-s-staleness, scenario: a-board-the-repository-moved-past]
- [x] AC-14: WHEN the board's `reviewed.at` is newer than those commits THEN 0 and stale false [REQ: the-summary-carries-the-board-s-staleness, scenario: a-reviewed-board-is-current]
- [x] AC-15: WHEN git cannot count in the board's directory THEN null and stale false [REQ: the-summary-carries-the-board-s-staleness, scenario: a-project-without-git]
- [x] AC-16: WHEN two of three boards are stale THEN the closed chip shows 2 stale [REQ: a-stale-board-is-marked-on-the-closed-chip-and-in-its-row, scenario: stale-boards-are-counted-while-closed]
- [x] AC-17: WHEN a stale board has 438 commits since and 4 manual items THEN the row shows 438 and the tooltip names 4 [REQ: a-stale-board-is-marked-on-the-closed-chip-and-in-its-row, scenario: the-stale-row-says-by-how-much]
- [x] AC-18: WHEN no board is stale THEN no stale count and no row marker [REQ: a-stale-board-is-marked-on-the-closed-chip-and-in-its-row, scenario: a-current-board-is-unchanged]
