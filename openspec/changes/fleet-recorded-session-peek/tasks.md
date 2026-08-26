## 1. The read (core, API)

- [ ] 1.1 `GET /api/fleet/roster/{project}/{key:path}/peek` — resolve the entry through `roster.read()`, hand its `session_log` to `conversation.read_conversation`, bounded turn count [REQ: a-recorded-session-can-be-read-without-being-resumed]
- [ ] 1.2 A key the record does not hold is a 404; an entry with no session id or no transcript is a 200 carrying the stated problem [REQ: an-unreadable-entry-says-why-and-never-renders-as-an-empty-session]
- [ ] 1.3 The route must not be swallowed by the existing `DELETE`/`{project}` wildcards — check the registration order the file already documents (CB-16) [REQ: a-recorded-session-can-be-read-without-being-resumed]
- [ ] 1.4 Nothing cached: no module-level store, no memo, and the failure log names the file and the failure kind only [REQ: nothing-read-from-a-transcript-is-written-down]

## 2. Python tests

- [ ] 2.1 A recorded, non-running entry with a transcript returns its last turns, and the fake owner is never asked to start anything [REQ: a-recorded-session-can-be-read-without-being-resumed]
- [ ] 2.2 A transcript far longer than the bound returns the bound and reports that earlier turns exist [REQ: a-recorded-session-can-be-read-without-being-resumed]
- [ ] 2.3 An entry with no session id, and one whose transcript is gone, each answer with their own problem — and neither reads as an empty conversation [REQ: an-unreadable-entry-says-why-and-never-renders-as-an-empty-session]
- [ ] 2.4 An unknown key is a 404 [REQ: a-selected-key-that-is-not-recorded-is-reported]
- [ ] 2.5 Two reads of the same entry both read the file — asserted by mutating the transcript between them and seeing the second answer change [REQ: nothing-read-from-a-transcript-is-written-down]
- [ ] 2.6 Prove the tests are proofs: revert the source, re-run, record which fail and which pass either way [REQ: a-recorded-session-can-be-read-without-being-resumed]

## 3. The lineage (web)

- [ ] 3.1 `fleetRoster.ts`: `groupByLabel(entries)` returning single entries and multi-entry lineages, newest first inside and between, an unlabelled entry grouped under its own key [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 3.2 A lineage states its label, how many conversations it holds and the newest one's age [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 3.3 A label with exactly one entry renders as that entry, with no group to open [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 3.4 Selection stays PER ENTRY inside a group — there is no act that restores a lineage as a unit [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 3.5 A group whose every entry is blocked says so at the group level, so a compacted row cannot hide that nothing in it can come back [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]

## 4. The peek (web)

- [ ] 4.1 A per-entry control fetches the peek and renders the turns inline: role, time, text, and a tool-only turn rendered as what it did rather than as a blank line [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 4.2 The number of turns shown is stated, so a short answer cannot read as a whole conversation [REQ: a-recorded-session-can-be-read-without-being-resumed]
- [ ] 4.3 A stated problem renders in place of the turns; a read that fails at the transport renders as a stated failure, never as an empty conversation [REQ: an-unreadable-entry-says-why-and-never-renders-as-an-empty-session]
- [ ] 4.4 Peeking must not arm, select or start anything — it is a read, and it sits away from the restore control [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 4.5 Nothing from the peek reaches `localStorage` or any other store — component state only [REQ: nothing-read-from-a-transcript-is-written-down]

## 5. Web tests and a look at the screen

- [ ] 5.1 Vitest over `groupByLabel`: six same-label entries become one lineage of six; a single-entry label stays an entry; ordering is newest first [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 5.2 Vitest: opening a lineage exposes its entries, each with its own checkbox, and the selection posts exactly the checked keys [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 5.3 Vitest: the peek renders turns, states how many, and renders a problem in place of them when one is returned [REQ: an-unreadable-entry-says-why-and-never-renders-as-an-empty-session]
- [ ] 5.4 Vitest: peeking posts nothing and arms nothing [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 5.5 Full web suite and the Python fleet tests; Python compared as a set diff against a baseline actually run [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 5.6 LOOK at it in the browser on a project whose record holds a repeated label: open the lineage, peek at one entry, and say what is on screen. If the browser cannot be reached the task stays open and the commit says so [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]

## 6. Close out

- [ ] 6.1 Rebuild `web/` so the running dashboard serves it [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 6.2 Close B-80 in the register with the sha and the check that went green [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]

## Acceptance Criteria (from spec scenarios)

### a-recorded-session-can-be-read-without-being-resumed

- [ ] AC-1: WHEN a read is requested for a recorded entry whose transcript exists THEN the last turns of that transcript are returned, and no process is started and no session is resumed [REQ: a-recorded-session-can-be-read-without-being-resumed, scenario: the-last-turns-of-a-recorded-session-are-readable]
- [ ] AC-2: WHEN a read is requested for an entry whose transcript holds far more turns than the bound THEN only the end of the transcript is read, and the answer states that earlier turns exist rather than implying the session begins there [REQ: a-recorded-session-can-be-read-without-being-resumed, scenario: a-long-transcript-costs-no-more-than-a-short-one]

### an-unreadable-entry-says-why-and-never-renders-as-an-empty-session

- [ ] AC-3: WHEN a read is requested for an entry whose transcript is gone THEN the answer carries a problem naming the missing transcript, and it is distinguishable from a transcript that was read and was empty [REQ: an-unreadable-entry-says-why-and-never-renders-as-an-empty-session, scenario: a-missing-transcript-is-named-not-drawn-as-emptiness]
- [ ] AC-4: WHEN a read is requested for an entry that has no session id recorded THEN the answer states that there is no session to read, rather than reporting an empty conversation [REQ: an-unreadable-entry-says-why-and-never-renders-as-an-empty-session, scenario: an-entry-that-was-never-given-a-session-id-is-refused-with-that-reason]
- [ ] AC-5: WHEN a read is requested for a key the project's record does not hold THEN the request fails as not-found, and no answer describing a conversation is returned [REQ: an-unreadable-entry-says-why-and-never-renders-as-an-empty-session, scenario: a-key-that-is-not-recorded-is-a-not-found-not-an-empty-read]

### nothing-read-from-a-transcript-is-written-down

- [ ] AC-6: WHEN a transcript cannot be read and the failure is logged THEN the log line names the file and the failure kind, and carries no line of the transcript [REQ: nothing-read-from-a-transcript-is-written-down, scenario: a-failed-read-logs-the-failure-without-the-content]
- [ ] AC-7: WHEN the same entry is read twice THEN the transcript is read again both times, and no copy of its content is held between the two reads [REQ: nothing-read-from-a-transcript-is-written-down, scenario: the-answer-is-not-cached]

### the-surface-offers-restore-per-project-and-shows-what-happened

- [ ] AC-8: WHEN the recorded list holds six entries carrying the same label THEN they render as one row naming that label, how many conversations it holds and the newest one's age, which opens to the six entries, each still selectable [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: six-entries-under-one-label-read-as-one-lineage]
- [ ] AC-9: WHEN a label holds exactly one recorded entry THEN it renders as that entry, with no group to open [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: a-label-with-one-entry-is-not-dressed-up-as-a-lineage]
- [ ] AC-10: WHEN the reader asks to see a recorded entry THEN the last turns of its session are shown inline, and no agent is started and no session is resumed [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: an-entry-can-be-read-before-it-is-picked]
- [ ] AC-11: WHEN the reader asks to see an entry whose transcript is gone or which never had a session id THEN the reason is shown in place of the turns, rather than an empty panel [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: an-entry-that-cannot-be-read-says-which-reason-applies]
