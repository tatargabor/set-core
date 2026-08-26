## 1. The record learns which round it was written in (core)

- [x] 1.1 Add `last_round_at` to the roster document (`lib/set_orch/fleet/roster.py`), written by `record()` with the same `now` it stamps on every entry that round saw, including a round that saw nothing [REQ: the-record-states-when-the-last-discovery-round-happened]
- [x] 1.2 Give `record()` an explicit `full_sweep: bool = True`; when false it writes entries but does NOT move the stamp, and logs that it did not [REQ: the-record-states-when-the-last-discovery-round-happened]
- [x] 1.3 Preserve `last_round_at` across an unparseable-file replacement and across `_prune()` — pruning removes entries, never the observation [REQ: the-record-states-when-the-last-discovery-round-happened]
- [x] 1.4 `read()` reports `last_round_at` on the answer and `in_last_round` per entry: `True` on equality with the stamp, `False` otherwise, `None` for every entry when there is no stamp [REQ: a-read-reports-per-entry-whether-it-was-in-the-last-round]
- [x] 1.5 Entries outside the last round stay in the returned list, unchanged and in the existing newest-first order [REQ: a-read-reports-per-entry-whether-it-was-in-the-last-round]

## 2. Restore accepts a selection (core)

- [x] 2.1 `restore()` takes `keys: Optional[Sequence[str]] = None` — `None` attempts every entry (unchanged), a list attempts exactly those keys [REQ: restore-takes-an-explicit-selection-or-the-whole-recorded-list]
- [x] 2.2 An empty list attempts nothing and reports zero attempted; it must not fall back to the whole record [REQ: restore-takes-an-explicit-selection-or-the-whole-recorded-list]
- [x] 2.3 Iterate the SELECTION, not the entries: a requested key the record does not hold produces a `skipped` outcome naming that, counts in `attempted`, and therefore makes `complete` false [REQ: restore-takes-an-explicit-selection-or-the-whole-recorded-list]
- [x] 2.4 Log the selection size against the record size, so a run is readable after the fact [REQ: restore-takes-an-explicit-selection-or-the-whole-recorded-list]

## 3. The route carries the selection (core, API)

- [x] 3.1 `POST /api/fleet/roster/{project}/restore` accepts an optional JSON body `{"keys": [...]}`; a request with no body keeps today's meaning exactly [REQ: restore-takes-an-explicit-selection-or-the-whole-recorded-list]
- [x] 3.2 Reject a body that is not a list of strings with a 422 rather than coercing it; the known-roots guard stays where it is [REQ: restore-takes-an-explicit-selection-or-the-whole-recorded-list]
- [x] 3.3 `GET /api/fleet/roster/{project}` passes `last_round_at` and per-entry `in_last_round` through untouched, alongside the liveness it already adds [REQ: a-read-reports-per-entry-whether-it-was-in-the-last-round]

## 4. Python tests

- [x] 4.1 Two recorded rounds: only the newest is `in_last_round`, the older entries are returned and marked `False` [REQ: a-read-reports-per-entry-whether-it-was-in-the-last-round]
- [x] 4.2 A round that saw nothing moves the stamp, so a project alive only in the previous round reports an EMPTY composition rather than that round [REQ: a-read-reports-per-entry-whether-it-was-in-the-last-round]
- [x] 4.3 A document with no stamp reports `in_last_round is None` on every entry — assert `is None`, never falsiness [REQ: a-read-reports-per-entry-whether-it-was-in-the-last-round]
- [x] 4.4 `full_sweep=False` writes entries and leaves the stamp where it was [REQ: the-record-states-when-the-last-discovery-round-happened]
- [x] 4.5 Selection tests: `None` → all N; `k` keys → exactly those k attempted and the others untouched; `[]` → nothing; an unknown key → one `skipped` outcome and `complete` false [REQ: restore-takes-an-explicit-selection-or-the-whole-recorded-list]
- [x] 4.6 Route test: bodiless POST still attempts the whole record (the regression this change must not cause) [REQ: restore-takes-an-explicit-selection-or-the-whole-recorded-list]
- [x] 4.7 Proved: the three sources reverted to `HEAD` (copies kept, `sha256sum -c` on the way back), `__pycache__` cleared, **10 of the 11 new tests failed**. The one that passed either way is `test_no_selection_still_attempts_the_whole_record`, and it is meant to — it is the regression control asserting that a bodiless restore is unchanged [REQ: a-read-reports-per-entry-whether-it-was-in-the-last-round]

## 5. The surface (web)

- [x] 5.1 `fleetRoster.ts`: split the offer into the composition (entries `in_last_round`, resumable, not running) and the remainder, each with its own count, and carry `last_round_at` for the age [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 5.2 An unknown composition (`in_last_round === null` / no stamp) falls back to the whole-list offer and carries a stated reason — never a silent whole-list offer dressed as a composition [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 5.3 `FleetRestore.tsx`: the primary armed control posts the composition's keys and states the observation's age via `ageLabel` [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 5.4 An expander lists the remaining recorded entries with per-entry checkboxes and its own armed restore for the checked set; nothing recorded is dropped from the screen [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 5.5 A project whose last round holds nothing says so in words, and offers no composition button [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 5.6 Both offers render through the existing `summarise()` result path, so a partial restore still reads as partial [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 5.7 `RestoreFromEmpty` — the post-reboot panel — offers the composition the same way; it is the placement this feature exists for [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]

## 6. Web tests and a look at the screen

- [x] 6.1 Vitest over the offer split: 24 recorded / 3 in the last round yields a primary offer of 3 and a remainder of 21 [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 6.2 Vitest: an empty last round renders the "nothing was open" sentence and no composition button; an unknown round renders the whole-list fallback with its reason [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 6.3 Vitest: the checkbox selection posts exactly the checked keys, and posts nothing when none is checked [REQ: restore-takes-an-explicit-selection-or-the-whole-recorded-list]
- [x] 6.4 Web: 67 files / 953 tests green. Python: a set diff against a `/tmp/base` worktree baseline with the three import roots and the session-end leak check (**0 leaks**) — baseline 99 failure entries, working tree 98, and the diff is one line in the BASELINE's favour (`test_paths.py::TestResolveProjectName::test_resolve_with_explicit_path`, cwd-dependent). No new failure [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 6.5 LOOK at it in the browser against the running dashboard: open a project with a large record, read the primary offer, expand the remainder, and say what is on screen. If the browser cannot be reached, this task stays open and is named as such in the commit [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]

## 7. Close out

- [x] 7.1 Rebuild `web/` so port 7400 serves the change [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 7.2 Close B-78 in `openspec/bugs/README.md` with the commit sha and the check that went green [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]

## Acceptance Criteria (from spec scenarios)

### the-record-states-when-the-last-discovery-round-happened

- [x] AC-1: WHEN discovery reports agents and the record is written at time `T` THEN the document carries `T` as the time of the last round, and every entry that round saw carries `T` as its last-seen time [REQ: the-record-states-when-the-last-discovery-round-happened, scenario: recording-a-round-stamps-the-document-with-that-rounds-time]
- [x] AC-2: WHEN a record write runs at time `T` with no agents reported THEN the document carries `T` as the time of the last round, and no entry's last-seen time is advanced [REQ: the-record-states-when-the-last-discovery-round-happened, scenario: a-round-that-saw-nothing-still-stamps-the-document]
- [x] AC-3: WHEN a record written before this capability existed is read THEN the last round is reported as unknown, and it is not inferred from any entry's last-seen time [REQ: the-record-states-when-the-last-discovery-round-happened, scenario: a-document-with-no-stamp-reports-the-last-round-as-unknown]

### a-read-reports-per-entry-whether-it-was-in-the-last-round

- [x] AC-4: WHEN a project's record holds entries last seen in three different rounds and the newest round is the document's stamp THEN exactly the entries from the newest round are reported as in the last round, and every other entry is reported as not in it while still being returned [REQ: a-read-reports-per-entry-whether-it-was-in-the-last-round, scenario: only-the-newest-round-is-reported-as-the-composition]
- [x] AC-5: WHEN a project's record holds entries, none of which was seen in the round the document is stamped with THEN no entry is reported as in the last round, and the previous round is not reported as the composition in its place [REQ: a-read-reports-per-entry-whether-it-was-in-the-last-round, scenario: a-project-that-was-not-running-when-the-fleet-was-last-observed-has-an-empty-composition]
- [x] AC-6: WHEN a record with no round stamp is read THEN every entry reports its last-round membership as unknown, and none reports `false` [REQ: a-read-reports-per-entry-whether-it-was-in-the-last-round, scenario: membership-is-unknown-when-the-document-carries-no-stamp]

### restore-takes-an-explicit-selection-or-the-whole-recorded-list

- [x] AC-7: WHEN restore is requested for a project whose record holds `N` entries, with no selection THEN the result carries exactly `N` per-entry outcomes, one per recorded entry [REQ: restore-takes-an-explicit-selection-or-the-whole-recorded-list, scenario: restoring-a-project-attempts-every-recorded-entry]
- [x] AC-8: WHEN restore is requested for a project whose record holds `N` entries, naming `k` of their keys THEN exactly those `k` entries are attempted, the other `N - k` are not attempted at all, and the result carries `k` outcomes [REQ: restore-takes-an-explicit-selection-or-the-whole-recorded-list, scenario: restoring-with-a-selection-attempts-exactly-that-selection]
- [x] AC-9: WHEN restore is requested with a selection that names no keys THEN no agent is started, and the result does not report the whole record as attempted [REQ: restore-takes-an-explicit-selection-or-the-whole-recorded-list, scenario: an-empty-selection-attempts-nothing]
- [x] AC-10: WHEN a selection names a key the project's record does not hold THEN the result carries an outcome for that key stating nothing is recorded under it, rather than omitting it [REQ: restore-takes-an-explicit-selection-or-the-whole-recorded-list, scenario: a-selected-key-that-is-not-recorded-is-reported]
- [x] AC-11: WHEN restore is requested for a project whose record is empty THEN no agent is started and the result reports zero entries attempted [REQ: restore-takes-an-explicit-selection-or-the-whole-recorded-list, scenario: restoring-a-project-with-an-empty-record-changes-nothing]

### the-surface-offers-restore-per-project-and-shows-what-happened

- [x] AC-12: WHEN a project's record holds entries and its screen is opened THEN a restore control is offered stating how many entries would be attempted [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: a-project-with-a-record-offers-restore-and-names-the-count]
- [x] AC-13: WHEN a project's record holds 24 entries of which 3 belong to the last round, and its screen is opened THEN the primary restore control offers those 3, states when that composition was observed, and does not offer to start the other 21 [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: the-primary-offer-is-the-last-composition-with-its-age]
- [x] AC-14: WHEN a project's record holds entries outside the last composition THEN the screen makes those entries reachable and individually selectable for restore, rather than omitting them [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: the-rest-of-the-record-stays-reachable-and-selectable]
- [x] AC-15: WHEN a project's record holds entries but none of them belongs to the last round THEN the screen states that nothing was open when the fleet was last seen, and no earlier round is offered as the composition [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: a-project-that-was-not-open-when-the-fleet-went-down-says-so]
- [x] AC-16: WHEN the record carries no last round at all THEN the screen offers the whole recorded list and states that the composition could not be determined [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: an-undeterminable-composition-is-stated-not-invented]
- [x] AC-17: WHEN restore completes with entries that were skipped or failed THEN the screen shows each of those entries with its reason, rather than a single success or failure message [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: the-outcome-of-every-entry-is-visible-after-restoring]
- [x] AC-18: WHEN a project has no recorded entries THEN no restore control is offered for it [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: an-empty-record-offers-no-restore-control]
