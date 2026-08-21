## 1. The roster module — a durable record keyed on session identity

- [x] 1.1 Create `lib/set_orch/fleet/roster.py` with `default_roster_path()` resolving `$XDG_DATA_HOME/set-core/fleet-roster.json` (fallback `~/.local/share`), mirroring `layout.default_layout_path()`, and module logging per the code-quality rule [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity]
- [x] 1.2 Define the document shape — project → session id → `{label, cwd, kind, first_seen, last_seen}` — and an `EMPTY` constant, with a normaliser that survives an unknown or malformed entry rather than raising [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity]
- [x] 1.3 `record(agents, path=…)`: upsert one entry per interactive agent, keyed on **session id**, advancing `last_seen` and leaving `first_seen` alone on a repeat sighting; never write two entries for one session id [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity]
- [x] 1.4 Record an agent that has no session id as an entry whose session id is explicitly absent (a stated absence, not a dropped row), and give it a stable synthetic key that cannot collide with a real session id [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity]
- [x] 1.5 Skip `kind == "oneshot"` entirely — CB-8: those are the framework's own `-p` subprocesses, not sessions anyone is sitting at [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity]
- [x] 1.6 Write atomically (`tempfile` + `os.replace` in the same directory), as `layout.py` does; no conflict/version guard (design D9) [REQ: the-record-survives-the-loss-of-every-live-process]
- [x] 1.7 Assert the record carries identity only: no transcript content, no message text, no tool output — enumerated fields, and anything else dropped by the normaliser rather than passed through [REQ: the-record-carries-identity-only]

## 2. Reading the roster back — the reboot case

- [x] 2.1 `read(project, path=…)` returning every stored entry, consulting NO live state: not `/proc`, not `~/.claude/sessions`, nothing a reboot destroys [REQ: the-record-survives-the-loss-of-every-live-process]
- [x] 2.2 A project with no record returns an empty entry list plus an explicit "no record exists" flag — an absent key is not an empty value [REQ: the-record-survives-the-loss-of-every-live-process]
- [x] 2.3 Compute `resumable` **at read time** via `discovery._session_log_for()` (design D4) — never store the boolean, and reuse that resolver rather than writing a second transcript lookup [REQ: each-entry-states-whether-it-is-resumable-right-now]
- [x] 2.4 Return an unresumable entry with `resumable: false` and a reason naming the missing transcript — it must NOT be filtered out (false-absence class) [REQ: each-entry-states-whether-it-is-resumable-right-now]
- [x] 2.5 An unparseable record file reports "unreadable" and is replaced on the next write, rather than raising [REQ: recording-never-breaks-discovery]

## 3. Forgetting and retention

- [x] 3.1 `forget(project, key)` removing one named entry and leaving the rest untouched [REQ: an-entry-can-be-forgotten-and-stale-entries-are-bounded]
- [x] 3.2 Prune on write any entry whose `last_seen` is older than the retention bound (one named constant, default 30 days), logging session id and age — pruning is reported, never silent [REQ: an-entry-can-be-forgotten-and-stale-entries-are-bounded]

## 4. Wiring the write into discovery's caller — without giving a query a side effect

- [x] 4.1 Call `roster.record()` from the API call site that already holds a full discovery answer (`api/fleet.py`), NOT from inside `discovery.py`; discovery's signature and return value stay unchanged (design D2) [REQ: recording-never-breaks-discovery]
- [x] 4.2 Swallow a write failure with respect to discovery's answer: log at WARNING with the failure named, return the normal agent list [REQ: recording-never-breaks-discovery]
- [x] 4.3 Test: with the store unwritable, `GET /api/fleet/agents` returns exactly what it returns with a writable store — assert equality of the answers, not merely a 200 [REQ: recording-never-breaks-discovery]

## 5. The restore module — per-entry decisions, outside the owner service

- [x] 5.1 Create `lib/set_orch/fleet/restore.py`; `owner.py` and `ownerd.py` are NOT modified (design D5 — the owner's lifetime is the agents' lifetime, and every restart of it kills them all) [REQ: each-entry-is-restored-by-starting-an-agent-that-resumes-its-session]
- [x] 5.2 `restore(project)` iterating the recorded list in order, producing one outcome per entry and attempting every entry even after one fails [REQ: restore-is-a-per-project-act-over-the-whole-recorded-list]
- [x] 5.3 For a resumable, non-live entry: call `OwnerClient.recover(unit=…, session_id=…, cwd=…, label=…)` passing NO `resume_argv`, so the owner's own default argv is used and cannot drift from the interactive one [REQ: each-entry-is-restored-by-starting-an-agent-that-resumes-its-session]
- [x] 5.4 Measure the owner's actual refusal behaviour on a label already held, then settle design D5's open question: derive a fresh label and report it in the outcome (preferred), or skip with a reason. Record the measurement in the change [REQ: each-entry-is-restored-by-starting-an-agent-that-resumes-its-session]
- [x] 5.5 A live session is `skipped` with a reason naming it — never resumed, never stopped; reuse the question `owner._refuse_if_the_session_is_running()` asks rather than re-implementing liveness [REQ: a-live-session-is-skipped-never-resumed]
- [x] 5.6 Indeterminate liveness is treated as LIVE and skipped, with the reason stating it was indeterminate — the fail direction that cannot fork a conversation [REQ: a-live-session-is-skipped-never-resumed]
- [x] 5.7 An entry with no transcript is `skipped` (not `failed`) with a reason naming the missing transcript, and appears in the result [REQ: an-unresumable-entry-is-skipped-with-its-reason]
- [x] 5.8 An entry whose `cwd` no longer exists is `skipped` with a reason naming the missing directory [REQ: an-unresumable-entry-is-skipped-with-its-reason]
- [x] 5.9 An empty record attempts nothing and reports zero attempted — no agent started [REQ: restore-is-a-per-project-act-over-the-whole-recorded-list]
- [x] 5.10 Restore is never triggered by discovery, by a page load, or by the framework starting — assert no call site other than the route [REQ: restore-is-a-per-project-act-over-the-whole-recorded-list]

## 6. The routes

- [x] 6.1 `GET /api/fleet/roster/{project}` returning the entries with `resumable`, its reason, `label`, `cwd`, `kind`, `first_seen`, `last_seen`, plus the "no record exists" flag [REQ: each-entry-states-whether-it-is-resumable-right-now]
- [x] 6.2 `POST /api/fleet/roster/{project}/restore` returning `{attempted, started[], skipped[], failed[]}` with a reason on every non-started entry and counts of all three classes [REQ: the-result-reports-every-entry-separately-and-a-partial-restore-reads-as-partial]
- [x] 6.3 The route takes no `argv` and no per-entry selection — narrower than the owner socket on purpose, matching the reasoning already recorded on `StartAgentBody` [REQ: each-entry-is-restored-by-starting-an-agent-that-resumes-its-session]
- [x] 6.4 Owner unavailable → explicit 503, with no entry reported as started [REQ: each-entry-is-restored-by-starting-an-agent-that-resumes-its-session]
- [x] 6.5 `DELETE /api/fleet/roster/{project}/{key}` for forgetting one entry [REQ: an-entry-can-be-forgotten-and-stale-entries-are-bounded]

## 7. The screen

- [ ] 7.1 Fetch the project's roster and offer a restore control ONLY when the record is non-empty — no control that would do nothing [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 7.1a **`AnsweredEmpty` (`Fleet.tsx`) — the primary placement, because it is where a reboot lands.** With no agent anywhere, the project column offers nothing to click, so this panel carries a LIST: one row per project with a non-empty roster, its entry count and its newest `last_seen`, each with its own restore control. Without this the feature is unreachable in exactly the state it exists for [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 7.1b **The selected project's agent-panel header** — the per-project act and where the per-entry outcome is rendered. This is the placement that covers the partial case: the project has 2 agents running and 7 recorded [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 7.1c **`FleetProjectColumn` row — an indicator, NOT a control.** A count of restorable entries only; clicking the row selects the project as it does today. The row already carries name, counts, agent count, conflict marker, archived marker, `⋯` and `ProjectFacts`; a seventh control there breaks the density rule. And it must NOT go in the `⋯` menu: that menu is about ARRANGEMENT (group / park), and a menu that has only ever rearranged things must not start processes [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 7.2 State the count of entries that would be attempted BEFORE the act, and show each entry's `last_seen` age so a stale list is visible before it is acted on [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [ ] 7.3 Render the per-entry outcome afterwards with the reason for every entry that did not start — never a single "Restored" message over a partial result (ui-quality: compacting must never hide a failure) [REQ: the-result-reports-every-entry-separately-and-a-partial-restore-reads-as-partial]
- [ ] 7.4 An unresumable entry is shown in the list as present-and-not-resumable, marked, rather than omitted [REQ: each-entry-states-whether-it-is-resumable-right-now]
- [ ] 7.5 All user-visible strings in ENGLISH, per the product-language rule; translate the tests in the same commit as the strings they assert [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]

## 8. Proving it, and looking at it

- [ ] 8.1 For every test written alongside a fix or guard, stash the implementation and re-run it — a test that passes without the code proves nothing. Record which tests were checked this way [REQ: recording-never-breaks-discovery]
- [ ] 8.2 Test the mixed restore explicitly: entries that start, entries skipped for each distinct reason, entries that fail — assert the three counts and every reason, not just a 200 [REQ: the-result-reports-every-entry-separately-and-a-partial-restore-reads-as-partial]
- [ ] 8.3 Test the reboot case with no live state at all: a roster on disk, nothing in `/proc`, no session records — the read must still return every entry [REQ: the-record-survives-the-loss-of-every-live-process]
- [ ] 8.4 Confidentiality test: record an entry for a session whose transcript contains message text, then grep the stored file for that text — it must not appear [REQ: the-record-carries-identity-only]
- [ ] 8.5 **Look at the screen in a browser** (Claude in Chrome against the running dashboard): open a project with a roster, read what the restore control says, take the act on a snapshot with at least one unresumable entry, and report what is actually visible. If the browser cannot be reached, this task stays OPEN and is stated as open in the commit and to the user [REQ: the-surface-offers-restore-per-project-and-shows-what-happened]
- [x] 8.7 **Reboot-faithful verification against this machine's REAL roster**, not a fixture: record the live agents, then read the roster back in a process that can see neither `/proc` nor the runtime's session-record directory, and compare the entry set to what was recorded. A synthetic fixture cannot catch a field that only real discovery produces [REQ: the-record-survives-the-loss-of-every-live-process]
- [ ] 8.8 **A check to run after an ACTUAL reboot** — `set-fleet-roster --verify` (or equivalent) printing, per project, how many entries the roster holds, how many are resumable right now, and the newest `last_seen`. This is the only evidence that survives the one event nobody can arrange to be present for; a simulation is a model of a reboot, not a reboot [REQ: the-record-survives-the-loss-of-every-live-process]
- [ ] 8.6 Regression check against a properly isolated baseline (`git worktree add --detach`, `PYTHONPATH` at the worktree's three source roots, session-end leak assertion) — a set diff of failures, never a count comparison [REQ: recording-never-breaks-discovery]

## Acceptance Criteria (from spec scenarios)

### agent-fleet-snapshot

- [x] AC-1: WHEN discovery reports an interactive agent with session id S, label L and cwd C THEN the project's record contains an entry keyed S carrying L, C, its kind, a first-seen time and a last-seen time [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity, scenario: a-discovered-agent-is-recorded]
- [x] AC-2: WHEN discovery reports session id S again later, possibly under a different pid THEN last-seen advances, first-seen is unchanged, and exactly one entry for S exists [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity, scenario: seeing-the-same-session-again-updates-last-seen-and-never-duplicates]
- [x] AC-3: WHEN discovery reports an interactive agent with no session id THEN an entry exists whose session id is explicitly absent, and it is not silently dropped [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity, scenario: an-agent-without-a-session-id-is-recorded-as-such]
- [x] AC-4: WHEN discovery reports an agent whose kind is oneshot THEN no entry is written for it [REQ: the-framework-records-each-discovered-agent-durably-keyed-on-session-identity, scenario: one-shot-subprocesses-are-not-recorded]
- [x] AC-5: WHEN the record holds entries and none of the recorded pids or session records exist any more THEN reading the project's record returns every entry it held, unchanged [REQ: the-record-survives-the-loss-of-every-live-process, scenario: the-record-is-readable-after-every-process-is-gone]
- [x] AC-6: WHEN a project has no record file THEN reading it returns an empty entry list and reports that no record exists, rather than raising [REQ: the-record-survives-the-loss-of-every-live-process, scenario: a-project-never-seen-has-an-empty-record-not-an-error]
- [x] AC-7: WHEN an entry's session has a transcript on disk THEN the entry is reported with resumable true [REQ: each-entry-states-whether-it-is-resumable-right-now, scenario: a-resumable-entry-is-reported-as-resumable]
- [x] AC-8: WHEN an entry's session has no transcript on disk THEN the entry is still returned, with resumable false and a reason naming the missing transcript [REQ: each-entry-states-whether-it-is-resumable-right-now, scenario: an-entry-whose-transcript-is-gone-is-kept-and-marked]
- [x] AC-9: WHEN an entry is written for a session whose transcript contains message text THEN the stored entry contains none of that text, and its fields are limited to identity and timestamps [REQ: the-record-carries-identity-only, scenario: no-content-is-written]
- [x] AC-10: WHEN the record cannot be written THEN discovery returns its normal answer and a warning naming the failure is logged [REQ: recording-never-breaks-discovery, scenario: an-unwritable-store-leaves-discovery-intact]
- [x] AC-11: WHEN the existing record file cannot be parsed THEN reading reports it unreadable and writing replaces it rather than raising [REQ: recording-never-breaks-discovery, scenario: a-corrupt-record-file-is-not-fatal]
- [x] AC-12: WHEN removal is requested for session id S on a project THEN S is absent afterwards and the remaining entries are unchanged [REQ: an-entry-can-be-forgotten-and-stale-entries-are-bounded, scenario: a-named-entry-is-removed]
- [x] AC-13: WHEN the record is written and an entry's last-seen is older than the retention bound THEN that entry is removed and the removal is logged with the session id and its age [REQ: an-entry-can-be-forgotten-and-stale-entries-are-bounded, scenario: an-entry-unseen-beyond-the-retention-bound-is-pruned]

### agent-fleet-restore

- [x] AC-14: WHEN restore is requested for a project whose record holds N entries THEN the result carries exactly N per-entry outcomes [REQ: restore-is-a-per-project-act-over-the-whole-recorded-list, scenario: restoring-a-project-attempts-every-recorded-entry]
- [x] AC-15: WHEN restore is requested for a project whose record is empty THEN no agent is started and the result reports zero entries attempted [REQ: restore-is-a-per-project-act-over-the-whole-recorded-list, scenario: restoring-a-project-with-an-empty-record-changes-nothing]
- [x] AC-16: WHEN an entry is resumable, its session is not live, and restore runs THEN an agent is started in the entry's cwd resuming that session id, and the outcome is started carrying the new label [REQ: each-entry-is-restored-by-starting-an-agent-that-resumes-its-session, scenario: a-resumable-entry-comes-back-as-a-resumed-session]
- [x] AC-17: WHEN restore runs and the owner service cannot be reached THEN the request fails with an explicit unavailable answer and no entry is reported as started [REQ: each-entry-is-restored-by-starting-an-agent-that-resumes-its-session, scenario: the-owner-service-being-unavailable-is-reported-not-swallowed]
- [x] AC-18: WHEN an entry's session is bound to a live process THEN that entry is skipped with a reason naming the live session, no resume is attempted, and the running agent is not stopped [REQ: a-live-session-is-skipped-never-resumed, scenario: an-already-running-session-is-skipped]
- [x] AC-19: WHEN it cannot be determined whether an entry's session is live THEN the entry is skipped rather than resumed, with the reason stating liveness was indeterminate [REQ: a-live-session-is-skipped-never-resumed, scenario: an-indeterminate-liveness-is-treated-as-live]
- [x] AC-20: WHEN an entry has no transcript and restore runs THEN its outcome is skipped with a reason naming the missing transcript, and it appears in the result [REQ: an-unresumable-entry-is-skipped-with-its-reason, scenario: an-entry-with-no-transcript-is-skipped-and-named]
- [x] AC-21: WHEN restore runs over 9 entries of which 3 start, 4 are skipped and 2 fail THEN the result reports 3 started, 4 skipped, 2 failed, with a reason on each of the 6 that did not start [REQ: the-result-reports-every-entry-separately-and-a-partial-restore-reads-as-partial, scenario: a-mixed-restore-reports-its-parts]
- [x] AC-22: WHEN an entry fails to start THEN the remaining entries are still attempted and the failure is reported against that entry alone [REQ: the-result-reports-every-entry-separately-and-a-partial-restore-reads-as-partial, scenario: one-entry-failing-does-not-abandon-the-rest]
- [ ] AC-23: WHEN a project's record holds entries and its screen is opened THEN a restore control is offered stating how many entries would be attempted [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: a-project-with-a-record-offers-restore-and-names-the-count]
- [ ] AC-24: WHEN restore completes with entries that were skipped or failed THEN the screen shows each of those entries with its reason, rather than a single success or failure message [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: the-outcome-of-every-entry-is-visible-after-restoring]
- [ ] AC-25: WHEN a project has no recorded entries THEN no restore control is offered for it [REQ: the-surface-offers-restore-per-project-and-shows-what-happened, scenario: an-empty-record-offers-no-restore-control]
