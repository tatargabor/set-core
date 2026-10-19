## 1. Server — the human input beyond the tail (Layer 1, `lib/set_orch/fleet/state.py`)

- [ ] 1.1 Add a backwards chunked search for the newest human entry, reusing `_last_human_input`'s definition of a human entry (text-carrying `user`, not sidechain, not a tool result) [REQ: the-last-human-input-is-found-beyond-the-bounded-tail]
- [ ] 1.2 Add the in-memory cache `{path: (inode, size_searched, epoch | None)}` with the growth rules from design D5, including reading the gap when the growth exceeds the tail; drop entries for transcripts no longer listed [REQ: the-last-human-input-is-found-beyond-the-bounded-tail]
- [ ] 1.3 Call it from the state pass only when the tail returned no human entry; log bytes read at DEBUG and a large search at WARNING with path and size [REQ: the-last-human-input-is-found-beyond-the-bounded-tail]
- [ ] 1.4 Unit tests: a human message buried under more than `TAIL_BYTES` of tool traffic is found; growth without human text reuses the cache without re-reading (assert the read count); a transcript with no human entry stays `None`; an inode change invalidates. Prove each test fails with the fix stashed [REQ: the-last-human-input-is-found-beyond-the-bounded-tail]
- [ ] 1.5 Re-measure on the live fleet: count agents with `last_human_input_seconds: null` before and after, and record both figures with the command in the commit message [REQ: the-last-human-input-is-found-beyond-the-bounded-tail]

## 2. Selection and placement logic (`web/src/lib/fleetLatest.ts`)

- [ ] 2.1 Implement `initial`, `update` and `resort` as pure functions over the agent list and N (design D3); unmeasured agents after measured ones [REQ: the-mode-shows-the-n-agents-a-person-most-recently-wrote-into-across-all-projects, REQ: placement-is-stable-while-the-mode-is-on]
- [ ] 2.2 Unit tests: N honoured; fewer agents than N gives no empty slots; typing into a slotted agent moves nothing; a newcomer replaces the oldest slot only; a departed agent frees its slot; resort orders most recent first [REQ: placement-is-stable-while-the-mode-is-on]

## 3. The mode on the fleet screen (`web/src/pages/Fleet.tsx`, `web/src/lib/fleetViewState.ts`)

- [ ] 3.1 Header: latest-mode toggle beside the PM toggle, a number control beside it (default 10, remembered per browser through try/catch-guarded storage), and a re-sort control shown only while the mode is on [REQ: latest-mode-is-a-toggle-beside-pm-mode-and-it-changes-nothing-about-the-agents, REQ: placement-is-stable-while-the-mode-is-on]
- [ ] 3.2 Synthetic `active` with no root and the reserved view key `__latest__`; `fleetViewState` never treats the key as a project; turning the mode off restores the previously selected project [REQ: the-mode-uses-the-fleets-own-agent-view-with-a-view-memory-of-its-own, REQ: latest-mode-is-a-toggle-beside-pm-mode-and-it-changes-nothing-about-the-agents]
- [ ] 3.3 Every tile takes its project root, known files and log/terminal target from its own agent's project, never from `active` (design D2) [REQ: the-mode-uses-the-fleets-own-agent-view-with-a-view-memory-of-its-own]
- [ ] 3.4 Hide agent drag-reorder, docking and the project's files/board panels while the mode is on; an enlarged agent without a terminal opens its log [REQ: the-mode-uses-the-fleets-own-agent-view-with-a-view-memory-of-its-own]
- [ ] 3.5 Project column: no selection shown while the mode is on; choosing a project turns the mode off and selects it; each tile in the mode shows its project name [REQ: no-project-is-selected-while-the-mode-is-on-and-every-tile-names-its-project]
- [ ] 3.6 Tiles of unmeasured agents say no message from the reader was found, never a duration [REQ: the-mode-shows-the-n-agents-a-person-most-recently-wrote-into-across-all-projects]
- [ ] 3.7 Mutual exclusion with PM mode through the existing `/api/fleet/pm` toggle path; both toggles reflect the state in force [REQ: latest-mode-and-pm-mode-are-mutually-exclusive]
- [ ] 3.8 Component tests for 3.1–3.7, including a file link from a tile whose project is not the last selected one resolving against its own root [REQ: the-mode-uses-the-fleets-own-agent-view-with-a-view-memory-of-its-own]

## 4. Verification

- [ ] 4.1 `pnpm build` in `web/` and `tsc -b` (not `tsc --noEmit`, which measures nothing here) [REQ: the-mode-uses-the-fleets-own-agent-view-with-a-view-memory-of-its-own]
- [ ] 4.2 Regression check against a baseline actually run (the `regression-baseline` skill), Python and web suites [REQ: the-last-human-input-is-found-beyond-the-bounded-tail]
- [ ] 4.3 Visual check in the browser against the running dashboard: turn the mode on with agents from several projects, write into one tile and confirm nothing moves, start writing into an agent outside the set and confirm it replaces the oldest, check the project column shows no selection, switch to PM mode and back. Say what was seen; if the browser cannot be reached, this task stays open [REQ: placement-is-stable-while-the-mode-is-on, REQ: no-project-is-selected-while-the-mode-is-on-and-every-tile-names-its-project]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN the reader turns latest mode on THEN no agent receives an instruction and no agent's lifecycle changes [REQ: latest-mode-is-a-toggle-beside-pm-mode-and-it-changes-nothing-about-the-agents, scenario: turning-the-mode-on-does-not-act-on-agents]
- [ ] AC-2: WHEN project P was selected, the mode turned on and off again THEN project P is shown with its arrangement [REQ: latest-mode-is-a-toggle-beside-pm-mode-and-it-changes-nothing-about-the-agents, scenario: turning-it-off-restores-the-previous-project]
- [ ] AC-3: WHEN the most recently written agents belong to three projects THEN all are shown together [REQ: the-mode-shows-the-n-agents-a-person-most-recently-wrote-into-across-all-projects, scenario: agents-from-different-projects-share-one-screen]
- [ ] AC-4: WHEN an agent's human-input age is absent THEN it is placed after every measured agent and its tile names no duration [REQ: the-mode-shows-the-n-agents-a-person-most-recently-wrote-into-across-all-projects, scenario: unmeasured-agents-come-last-and-are-not-called-old]
- [ ] AC-5: WHEN the count is 5 and 12 agents exist THEN exactly 5 are shown [REQ: the-mode-shows-the-n-agents-a-person-most-recently-wrote-into-across-all-projects, scenario: the-count-is-honoured]
- [ ] AC-6: WHEN the reader writes into the third tile THEN no tile changes position [REQ: placement-is-stable-while-the-mode-is-on, scenario: typing-into-a-tile-does-not-move-it]
- [ ] AC-7: WHEN the reader writes into an agent not shown THEN it takes the oldest slot and no other tile moves [REQ: placement-is-stable-while-the-mode-is-on, scenario: a-newcomer-replaces-the-least-recent]
- [ ] AC-8: WHEN the reader presses re-sort THEN tiles are ordered most recent first [REQ: placement-is-stable-while-the-mode-is-on, scenario: re-sort-orders-by-recency]
- [ ] AC-9: WHEN two shown agents from different projects share a name THEN each tile shows its project [REQ: no-project-is-selected-while-the-mode-is-on-and-every-tile-names-its-project, scenario: two-agents-with-the-same-name-are-told-apart]
- [ ] AC-10: WHEN a project is chosen in the column while the mode is on THEN the mode turns off and that project is shown [REQ: no-project-is-selected-while-the-mode-is-on-and-every-tile-names-its-project, scenario: choosing-a-project-leaves-the-mode]
- [ ] AC-11: WHEN three columns are chosen in the mode and a project is opened later THEN the project keeps its own column choice [REQ: the-mode-uses-the-fleets-own-agent-view-with-a-view-memory-of-its-own, scenario: the-modes-layout-does-not-leak-into-a-project]
- [ ] AC-12: WHEN a file link is opened from a tile of project Q while P was last selected THEN it resolves against Q's root [REQ: the-mode-uses-the-fleets-own-agent-view-with-a-view-memory-of-its-own, scenario: a-tile-acts-on-its-own-project]
- [ ] AC-13: WHEN the enlarged agent has no terminal THEN its log opens [REQ: the-mode-uses-the-fleets-own-agent-view-with-a-view-memory-of-its-own, scenario: an-agent-without-a-terminal-shows-its-log]
- [ ] AC-14: WHEN PM mode is on and latest mode is turned on THEN PM mode is off and its toggle says so [REQ: latest-mode-and-pm-mode-are-mutually-exclusive, scenario: pm-mode-is-turned-off-by-latest-mode]
- [ ] AC-15: WHEN latest mode is on and PM mode is turned on THEN latest mode is off and its toggle says so [REQ: latest-mode-and-pm-mode-are-mutually-exclusive, scenario: latest-mode-is-turned-off-by-pm-mode]
- [ ] AC-16: WHEN a person's last message is followed by more than the tail's worth of tool traffic THEN the reported age is that message's age [REQ: the-last-human-input-is-found-beyond-the-bounded-tail, scenario: a-long-tool-run-does-not-hide-the-readers-message]
- [ ] AC-17: WHEN the transcript grew only by non-human entries since the last search THEN the remembered age is reused without reading further back [REQ: the-last-human-input-is-found-beyond-the-bounded-tail, scenario: the-deep-search-is-not-repeated-while-nothing-changed]
- [ ] AC-18: WHEN no entry in the whole transcript is a human entry THEN the age is absent [REQ: the-last-human-input-is-found-beyond-the-bounded-tail, scenario: a-transcript-with-no-human-message-stays-absent]
