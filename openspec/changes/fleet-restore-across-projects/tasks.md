## 1. Pure functions (web lib)

- [x] 1.1 `offerAcross(selection)` in `web/src/lib/fleetRoster.ts`: per project, `offerFor()` over the selected entries; totals of restorable agents and of projects with at least one restorable entry; the keys for each project come from `offerFor` — done; the per-project keys come from `offerFor` [REQ: the-fleet-offers-restore-across-projects-from-one-dialog]
- [x] 1.2 `summariseAcross(parts)`: one part per project attempted, either a `RestoreSummary` or an error; summed counts; `complete` only when every part succeeded and was complete; a headline that never says "restored" over a partial — done [REQ: the-fleet-offers-restore-across-projects-from-one-dialog]

## 2. The surface (web)

- [x] 2.1 Extract the lineage list from `TheRest` into a shared `RecordedList`, with no change to how the per-project dialog behaves — done; the per-project suite (`fleetRestoreSurface.test.tsx`) stays green unchanged [REQ: the-fleet-offers-restore-across-projects-from-one-dialog]
- [x] 2.2 `RestoreAcrossProjects`: a chip reading `GET /api/fleet/roster`, drawn only when it lists projects; a dialog with collapsible project rows, each reading its record on first open — done [REQ: the-fleet-offers-restore-across-projects-from-one-dialog]
- [x] 2.3 An armed act naming the agent and project counts, posting each project's keys one after another, then rendering the per-project results and the summed headline — done [REQ: the-fleet-offers-restore-across-projects-from-one-dialog]
- [x] 2.4 Close on ×, Escape and a click on the backdrop; a click inside does not close it — done [REQ: the-fleet-offers-restore-across-projects-from-one-dialog]
- [x] 2.5 Mount it in `FleetProjectColumn`'s attention row, after the status chips — done [REQ: the-fleet-offers-restore-across-projects-from-one-dialog]

## 3. Tests

- [x] 3.1 Vitest over `offerAcross` and `summariseAcross`: a failed project and an incomplete project each make the whole result partial; an error is not counted as zero started — `tests/unit/fleetRestoreAcross.test.tsx`, 4 tests [REQ: the-fleet-offers-restore-across-projects-from-one-dialog]
- [x] 3.2 Vitest over the surface: no chip without a record; no per-project read before a project is opened; one click posts nothing; a confirmed selection posts exactly each project's keys; a 503 project is named — same file, 6 tests [REQ: the-fleet-offers-restore-across-projects-from-one-dialog]
- [x] 3.3 Prove the tests: revert the implementation and confirm the new tests fail — done by mutation rather than a full revert (a revert fails every test on import alone, which proves nothing). Three mutants, each restored from a sha256-checked copy: (M1) an errored project not making the sum partial → 2 tests red; (M2) the armed act running on the first click → 3 red; (M3) every project read eagerly → 1 red. After the restore, `sha256sum -c` OK and 10/10 green [REQ: the-fleet-offers-restore-across-projects-from-one-dialog]
- [x] 3.4 Full web suite green; `tsc -b` clean — `tsc -b` clean. Full vitest: 1461/1464. The 3 failures are pre-existing: `designDrift` fails on a HEAD worktree too, and `fleetArrangement`/`fleetSurface` are flaky on BOTH trees, with a different test failing on each of 3 runs [REQ: the-fleet-offers-restore-across-projects-from-one-dialog]

## 4. Look at it, and close out

- [x] 4.1 Rebuild `web/` so port 7400 serves it; open the fleet screen in the browser, find the chip in the attention row, open the dialog, expand a project, peek an entry, tick one and arm without confirming. Do NOT confirm a restore on the live fleet — LOOKED, 2026-09-21, on the running dashboard. The chip reads `⟲ 525` at the end of the attention row (528 recorded, 3 running). The dialog lists 34 projects; `set-core` opened into its lineages, with blocked entries greyed and their reasons shown; the peek showed 6 turns; one tick each in `set-core` and in a second project armed as `Start 2 agents in 2 projects?`, then cancelled; `/restore` requests made: 0. **The look found a defect the tests could not**: a running entry read `last seen unknown ago`, because the dialog's clock was older than the record read after it. Each row now measures its ages against its own read time; re-checked live, it reads `last seen 5s ago` [REQ: the-fleet-offers-restore-across-projects-from-one-dialog]
- [x] 4.2 `openspec validate fleet-restore-across-projects --strict` passes [REQ: the-fleet-offers-restore-across-projects-from-one-dialog]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN agents are running and the record lists projects THEN the attention row shows the reopen control with no project selected
- [x] AC-2: WHEN the record lists no project or its read fails THEN no control is drawn
- [x] AC-3: WHEN the dialog opens THEN no per-project read has been made; opening one reads only that one
- [x] AC-4: WHEN entries in two projects are ticked and the act is clicked once THEN counts are stated and nothing is posted
- [x] AC-5: WHEN confirmed THEN each project's route receives exactly its ticked keys and no other route is called
- [x] AC-6: WHEN one project's request fails with 503 THEN the result is partial and that project is named with its error
- [x] AC-7: WHEN one project's result is incomplete THEN the cross-project result is partial
