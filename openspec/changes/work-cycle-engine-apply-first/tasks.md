## 1. Measure before committing to reuse

<!-- depends: none -->

- [ ] 1.1 Determine whether `GatePipeline` can be pointed at one tree and a subset of gates without inheriting merge semantics (retry policy, baseline-diff scope, new-API-surface detection); record the finding and which of the two acceptable outcomes applies [REQ: the-gate-runs-through-the-project-profile]
- [ ] 1.2 Identify which part of the stream-json consumption in `chat.py` is reusable outside a websocket-bound session, and record what has to be extracted versus re-expressed [REQ: a-work-unit-runs-in-a-fresh-full-agent-context]
- [ ] 1.3 Record both findings in `design.md` under D4, replacing the open question with the measurement [REQ: the-gate-runs-through-the-project-profile]

## 2. Task-group resolution (Layer 1, domain-free)

<!-- depends: none -->

- [ ] 2.1 Parse numbered group headings out of a change's `tasks.md` and bind every task line to exactly one group, including lines preceding the first heading [REQ: task-groups-are-read-from-the-change-s-task-file]
- [ ] 2.2 Parse dependency annotations attached to a group, defaulting an unannotated group to depend on its predecessor, and honouring an explicit declaration of independence [REQ: dependency-edges-are-declared-and-their-absence-is-fail-closed]
- [ ] 2.3 Detect dependency cycles and refuse to declare any group runnable, naming the cycle [REQ: dependency-edges-are-declared-and-their-absence-is-fail-closed]
- [ ] 2.4 Select the next runnable group deterministically, skipping groups awaiting an answer rather than blocking behind them, and reporting per-group reasons when nothing is runnable [REQ: the-next-runnable-group-is-selected-deterministically]
- [ ] 2.5 Cut the slice handed to a run — the group's block only — and honour a caller-supplied task limit within the group [REQ: a-run-receives-its-slice-not-the-whole-file]
- [ ] 2.6 Assemble carry-over: the notes of the most recent completed run for the same group and for the preceding group, dropping older runs [REQ: carry-over-travels-from-the-previous-run]
- [ ] 2.7 Assemble the reading list from every markdown artifact in the change directory except the task file, including artifacts written by earlier runs [REQ: the-reading-list-includes-the-change-s-own-artifacts]
- [ ] 2.8 Unit tests for 2.1–2.7, each verified against the un-fixed code (stash the implementation, confirm the test fails) before being accepted as proof [REQ: the-next-runnable-group-is-selected-deterministically]

## 3. Work-unit engine core

<!-- depends: 1, 2 -->

- [ ] 3.1 Define the work unit and its lifecycle — run, verdict, gate, commit, or set aside — with the unit kind as an attribute so slice, phase and lens are expressible [REQ: a-work-unit-runs-in-a-fresh-full-agent-context]
- [ ] 3.2 Acquire a tree-scoped lock recording a session-scoped seat; refuse a seat that identifies only a project; report a lock whose holder is dead as stale, distinguishably from running [REQ: a-work-unit-is-locked-to-one-seat-and-the-seat-is-session-scoped]
- [ ] 3.3 Run the unit as a full agent session (not a subagent) with the project's hooks and rules active, consuming its event stream as it runs [REQ: a-work-unit-runs-in-a-fresh-full-agent-context]
- [ ] 3.4 Constrain the verdict to a declared schema with outcome, summary and a separate open-decisions field; record a non-conforming return as a reporting failure rather than inferring an outcome [REQ: the-verdict-is-schema-constrained]
- [ ] 3.5 Persist the verdict durably **before** the gate runs, so a run interrupted between verdict and commit stays attributable [REQ: the-verdict-is-durable-before-the-gate-runs]
- [ ] 3.6 Diff the verdict against the task markers in the tree and report divergence in both directions [REQ: the-verdict-is-checked-against-the-tree]
- [ ] 3.7 Resolve gate steps through `resolve_gate_config` and run them per the 1.1 finding; record "no gate ran" as a state distinct from "gate passed" when the profile declares none [REQ: the-gate-runs-through-the-project-profile]
- [ ] 3.8 Commit only behind a green gate, referencing the change and unit; on failure leave the work in the tree, make no commit, and do not advance [REQ: a-commit-happens-only-behind-a-green-gate]
- [ ] 3.9 Derive reported progress from completed task markers, never from turn or event counts [REQ: a-work-unit-runs-in-a-fresh-full-agent-context]
- [ ] 3.10 Unit tests for 3.1–3.9, including a test that fails if progress is ever derived from an activity counter [REQ: the-verdict-is-checked-against-the-tree]
- [ ] 3.11 Allow a unit's input to be other units' verdicts, and preserve every input verdict in full when such a unit is set aside; a projection of the comparison must carry its verdict, not decide for it [REQ: a-unit-may-take-other-units-verdicts-as-input-and-setting-it-aside-preserves-them]

## 4. Deferred-work connector

<!-- depends: 3 -->

- [ ] 4.1 Set a unit aside with a machine-readable resume condition that expresses both a human decision and an external dependency; refuse to set one aside with no condition [REQ: a-set-aside-unit-names-its-resume-condition]
- [ ] 4.2 Write an open decision into the change's task file as a durable stop marker carrying the question, surviving engine restart [REQ: an-open-decision-becomes-a-durable-stop-marker]
- [ ] 4.3 Read answers from a directory keyed inside the document on change and task; report an answer for a non-awaiting task as unmatched and leave it in place [REQ: answers-arrive-through-a-keyed-directory]
- [ ] 4.4 Defer an unparseable answer document and retry it on later intake; quarantine with a recorded reason only after a bounded number of failed attempts [REQ: the-connector-tolerates-a-partially-written-answer]
- [ ] 4.5 Accept several documents for one key — newest applied, others retained — and name written documents by source and timestamp so two uploaders cannot collide [REQ: several-answers-may-exist-for-one-key]
- [ ] 4.6 Run answer intake at the engine's entry point on every path, including the status path, so a released task is reported runnable [REQ: answer-intake-runs-at-the-entry-point-on-every-path]
- [ ] 4.7 Stamp consumption on the answer or in the log, and make consumed and unconsumed distinguishable without counting files [REQ: consumption-is-recorded-not-inferred]
- [ ] 4.8 Tests for 4.1–4.7, including one that fails if intake is reachable from only some entry points, and one that writes a truncated document mid-intake [REQ: answer-intake-runs-at-the-entry-point-on-every-path]

## 5. Control surface

<!-- depends: 3, 4 -->

- [ ] 5.1 Add the start operation on the existing change-control API: start the next runnable unit or a named group, returning before the run completes and identifying what was started [REQ: a-work-unit-can-be-started-over-the-api]
- [ ] 5.2 Refuse an unstartable request with the failing condition named — nothing runnable, dependencies unsatisfied, awaiting an answer, or a unit already holding the lock [REQ: an-unstartable-request-is-refused-with-a-reason]
- [ ] 5.3 Add the answer operation, delivering through the ordinary connector so no answer path is privileged; refuse an answer for a non-awaiting task [REQ: an-open-decision-can-be-answered-over-the-api]
- [ ] 5.4 Report the state a surface needs: runnable groups, groups awaiting an answer with their questions, blocked groups with their blockers, and any running unit with its progress; distinguish a stale lock from a live run [REQ: the-state-a-surface-needs-is-queryable]
- [ ] 5.5 API tests for 5.1–5.4, asserting that the API answer path and the directory answer path produce the same engine state [REQ: an-open-decision-can-be-answered-over-the-api]

## 6. Evidence

<!-- depends: 5 -->

- [ ] 6.1 Run the engine on a change of this repository with real group dependencies and at least one human stop; record what the run produced, not that it exited zero [REQ: a-work-unit-runs-in-a-fresh-full-agent-context]
- [ ] 6.2 Confirm the answer written from the surface reaches a stopped unit and releases it, observed end to end rather than asserted per layer [REQ: an-open-decision-can-be-answered-over-the-api]
- [?] 6.3 Coordinate the crossing run on the consuming project's tree and compare it against that project's own engine — requires the other side's participation and their choice of change [REQ: a-commit-happens-only-behind-a-green-gate]

## Acceptance Criteria (from spec scenarios)

<!-- work-unit-engine -->
- [ ] AC-1: WHEN the engine starts a work unit THEN it launches a full agent session with the project's hooks and rules active / it consumes the session's event stream as the run proceeds [REQ: a-work-unit-runs-in-a-fresh-full-agent-context, scenario: unit-runs-as-a-full-session]
- [ ] AC-2: WHEN the engine reports how far a unit has got THEN the figure is derived from completed task markers in the change's `tasks.md` / the count of turns or events is NOT presented as progress [REQ: a-work-unit-runs-in-a-fresh-full-agent-context, scenario: progress-is-measured-from-the-tree-not-from-the-transcript]
- [ ] AC-3: WHEN a work unit is started while another holds the lock for the same tree THEN the engine refuses the second unit and names the holder [REQ: a-work-unit-is-locked-to-one-seat-and-the-seat-is-session-scoped, scenario: a-second-unit-is-refused-while-one-runs]
- [ ] AC-4: WHEN a seat identifier is supplied that identifies the project rather than a session THEN the engine refuses to record it / the refusal states that a seat must identify one session [REQ: a-work-unit-is-locked-to-one-seat-and-the-seat-is-session-scoped, scenario: a-project-scoped-seat-is-refused]
- [ ] AC-5: WHEN a lock exists but the process that took it is no longer alive THEN the engine reports the lock as stale rather than as running / the stale state is distinguishable from a live run in the engine's own output [REQ: a-work-unit-is-locked-to-one-seat-and-the-seat-is-session-scoped, scenario: a-lock-whose-holder-is-gone-does-not-block-forever]
- [ ] AC-6: WHEN a work unit returns output that does not match the verdict schema THEN the engine records the run as failed to report rather than inventing an outcome [REQ: the-verdict-is-schema-constrained, scenario: a-verdict-outside-the-schema-is-refused]
- [ ] AC-7: WHEN a unit describes a decision needing a human in its free-text notes but leaves the open decisions field empty THEN the engine does NOT treat it as a stop point / the notes are carried forward as context only [REQ: the-verdict-is-schema-constrained, scenario: an-open-decision-in-the-notes-does-not-stop-the-cycle]
- [ ] AC-8: WHEN a unit returns one or more entries in the open decisions field THEN the engine marks the corresponding work as awaiting a human answer [REQ: the-verdict-is-schema-constrained, scenario: an-open-decision-in-its-own-field-stops-the-unit]
- [ ] AC-9: WHEN the verdict lists completed work that the file does not mark as complete THEN the engine reports the discrepancy and does not adopt the claim [REQ: the-verdict-is-checked-against-the-tree, scenario: claimed-more-than-was-marked]
- [ ] AC-10: WHEN the file marks work complete that the verdict does not mention THEN the engine reports that discrepancy too [REQ: the-verdict-is-checked-against-the-tree, scenario: marked-more-than-was-claimed]
- [ ] AC-11: WHEN a work unit finishes and a gate is due THEN the steps executed are those the project's profile declares [REQ: the-gate-runs-through-the-project-profile, scenario: gate-steps-come-from-the-profile]
- [ ] AC-12: WHEN the profile declares no gate steps THEN the engine runs no gate and records that no gate was run / it does NOT substitute a default command [REQ: the-gate-runs-through-the-project-profile, scenario: no-declared-gate-means-no-gate]
- [ ] AC-13: WHEN the gate reports a failure THEN no commit is made / the work remains in the working tree / the engine stops rather than starting the next unit [REQ: a-commit-happens-only-behind-a-green-gate, scenario: gate-fails]
- [ ] AC-14: WHEN the gate passes THEN the engine commits the unit's changes with a reference to the change and unit it belongs to [REQ: a-commit-happens-only-behind-a-green-gate, scenario: gate-passes]
- [ ] AC-15: WHEN the engine's process ends after a unit returns its verdict but before the commit completes THEN the recorded verdict survives / the engine's later output shows a started unit with no completion, rather than showing the unit as never attempted [REQ: the-verdict-is-durable-before-the-gate-runs, scenario: killed-between-verdict-and-commit]
- [ ] AC-16: WHEN a unit whose input is several other units' verdicts is set aside instead of producing an outcome THEN every input verdict remains retrievable in full / no input verdict is replaced by a summary of it [REQ: a-unit-may-take-other-units-verdicts-as-input-and-setting-it-aside-preserves-them, scenario: comparing-unit-is-set-aside]
- [ ] AC-17: WHEN the comparison's result is projected into a single outcome for a caller THEN the projection carries the comparison's own verdict rather than deciding on its behalf / where the comparison reached no decision, the projection is a stop rather than a choice [REQ: a-unit-may-take-other-units-verdicts-as-input-and-setting-it-aside-preserves-them, scenario: a-mechanical-projection-of-the-comparison-does-not-decide]

<!-- task-group-resolution -->
- [ ] AC-18: WHEN a `tasks.md` contains numbered group headings with task lines beneath them THEN the resolver reports one group per heading, each carrying its own task lines [REQ: task-groups-are-read-from-the-change-s-task-file, scenario: groups-are-identified]
- [ ] AC-19: WHEN task lines appear before the first group heading THEN the resolver reports them as a group rather than discarding them [REQ: task-groups-are-read-from-the-change-s-task-file, scenario: tasks-outside-any-group]
- [ ] AC-20: WHEN a group declares that it depends on specific earlier groups THEN the resolver treats it as runnable only once those groups are complete [REQ: dependency-edges-are-declared-and-their-absence-is-fail-closed, scenario: declared-dependencies]
- [ ] AC-21: WHEN a group carries no dependency annotation THEN the resolver treats it as depending on the immediately preceding group [REQ: dependency-edges-are-declared-and-their-absence-is-fail-closed, scenario: no-annotation-means-serial]
- [ ] AC-22: WHEN a group explicitly declares that it has no dependencies THEN the resolver treats it as runnable regardless of earlier groups [REQ: dependency-edges-are-declared-and-their-absence-is-fail-closed, scenario: explicit-independence]
- [ ] AC-23: WHEN declared dependencies form a cycle THEN the resolver reports the cycle and declares no group runnable / it does NOT pick an arbitrary order [REQ: dependency-edges-are-declared-and-their-absence-is-fail-closed, scenario: a-cycle-is-reported-not-silently-ordered]
- [ ] AC-24: WHEN the lowest-ordered group with open tasks depends on a group that still has open tasks THEN it is not selected [REQ: the-next-runnable-group-is-selected-deterministically, scenario: dependencies-unsatisfied]
- [ ] AC-25: WHEN a group is awaiting a human answer and a later independent group is runnable THEN the later group is selected / the awaiting group remains reported as awaiting [REQ: the-next-runnable-group-is-selected-deterministically, scenario: a-group-awaiting-an-answer-is-skipped-not-blocked-behind]
- [ ] AC-26: WHEN every group with open tasks is either blocked by dependencies or awaiting an answer THEN the resolver reports that no group is runnable, and why for each [REQ: the-next-runnable-group-is-selected-deterministically, scenario: nothing-runnable]
- [ ] AC-27: WHEN a group is selected for a run THEN the handed-over work description contains that group's tasks / it does not contain other groups' tasks [REQ: a-run-receives-its-slice-not-the-whole-file, scenario: only-the-group-s-block-is-handed-over]
- [ ] AC-28: WHEN a caller limits a run to a number of tasks smaller than the group THEN the slice contains at most that many open tasks from the group [REQ: a-run-receives-its-slice-not-the-whole-file, scenario: hard-slicing-within-a-group]
- [ ] AC-29: WHEN a group is selected that a previous run left partially complete THEN that previous run's notes travel with the new slice [REQ: carry-over-travels-from-the-previous-run, scenario: resuming-a-partial-group]
- [ ] AC-30: WHEN a group is selected whose predecessor produced notes THEN those notes travel with the slice [REQ: carry-over-travels-from-the-previous-run, scenario: discoveries-reach-the-next-group]
- [ ] AC-31: WHEN several earlier runs exist for the same group THEN only the most recent one's notes are included [REQ: carry-over-travels-from-the-previous-run, scenario: stale-notes-are-dropped]
- [ ] AC-32: WHEN an earlier run wrote a new markdown artifact into the change's directory THEN a later run's reading list includes it [REQ: the-reading-list-includes-the-change-s-own-artifacts, scenario: an-artifact-produced-by-an-earlier-group-is-included]
- [ ] AC-33: WHEN the reading list is assembled THEN the task file is excluded, because the slice is handed over separately [REQ: the-reading-list-includes-the-change-s-own-artifacts, scenario: the-task-file-is-not-duplicated]

<!-- deferred-work-connector -->
- [ ] AC-34: WHEN a unit is set aside because a decision needs a person THEN the recorded condition identifies the decision awaiting an answer [REQ: a-set-aside-unit-names-its-resume-condition, scenario: awaiting-a-human-answer]
- [ ] AC-35: WHEN a unit is set aside because a system it depends on is unavailable THEN the recorded condition names that dependency / the engine does NOT describe the unit as waiting for a human [REQ: a-set-aside-unit-names-its-resume-condition, scenario: awaiting-an-external-system]
- [ ] AC-36: WHEN a unit is set aside with no condition given THEN the engine refuses, because a condition that is not named cannot be observed [REQ: a-set-aside-unit-names-its-resume-condition, scenario: a-unit-cannot-be-set-aside-without-a-condition]
- [ ] AC-37: WHEN a unit returns an open decision naming a task THEN that task is marked in the file as awaiting a human answer / the question text is recorded with it [REQ: an-open-decision-becomes-a-durable-stop-marker, scenario: open-decision-is-written-into-the-task-file]
- [ ] AC-38: WHEN the engine is restarted after a unit returned an open decision THEN the marked task is still reported as awaiting an answer [REQ: an-open-decision-becomes-a-durable-stop-marker, scenario: the-marker-outlives-the-run]
- [ ] AC-39: WHEN an answer document naming a change and an awaiting task is placed in the directory THEN the engine records the answer against that task and the task is no longer awaiting [REQ: answers-arrive-through-a-keyed-directory, scenario: an-answer-releases-its-task]
- [ ] AC-40: WHEN an answer names a task that is not awaiting an answer THEN the engine reports it as unmatched and leaves it in place rather than discarding it [REQ: answers-arrive-through-a-keyed-directory, scenario: an-answer-for-an-unknown-task]
- [ ] AC-41: WHEN an answer document cannot be parsed on its first intake THEN it is deferred and remains eligible for a later intake / it is NOT quarantined on that first failure [REQ: the-connector-tolerates-a-partially-written-answer, scenario: half-written-file-is-retried-not-quarantined]
- [ ] AC-42: WHEN a document has failed to parse on the configured number of successive intakes THEN it is quarantined and the reason is recorded alongside it [REQ: the-connector-tolerates-a-partially-written-answer, scenario: persistently-malformed-file-is-quarantined-with-its-reason]
- [ ] AC-43: WHEN a document that was deferred parses successfully on a later intake THEN it is consumed as any other answer [REQ: the-connector-tolerates-a-partially-written-answer, scenario: a-deferred-file-that-later-parses-is-consumed-normally]
- [ ] AC-44: WHEN two answer documents for the same key are present THEN the most recent is applied / the other is retained [REQ: several-answers-may-exist-for-one-key, scenario: two-uploaders-answer-the-same-question]
- [ ] AC-45: WHEN an answer document is written by an uploader THEN its name carries the uploader's identity and a timestamp / a second uploader writing for the same key produces a different name [REQ: several-answers-may-exist-for-one-key, scenario: names-do-not-collide]
- [ ] AC-46: WHEN the engine is asked to run one work unit THEN pending answers are taken in before the unit is selected [REQ: answer-intake-runs-at-the-entry-point-on-every-path, scenario: intake-happens-on-a-single-unit-run]
- [ ] AC-47: WHEN the engine is asked what is runnable THEN pending answers are taken in before the answer is computed / a task released by a pending answer is reported as runnable [REQ: answer-intake-runs-at-the-entry-point-on-every-path, scenario: intake-happens-on-a-status-query]
- [ ] AC-48: WHEN an answer is applied to a task THEN the time of consumption is recorded [REQ: consumption-is-recorded-not-inferred, scenario: a-consumed-answer-is-stamped]
- [ ] AC-49: WHEN answers are present in the directory THEN those already consumed are distinguishable from those not yet consumed / neither state is concluded from the number of files present [REQ: consumption-is-recorded-not-inferred, scenario: an-unconsumed-answer-is-distinguishable]

<!-- work-cycle-control-api -->
- [ ] AC-50: WHEN a start request is made for a change with a runnable group THEN the engine starts that group as a work unit / the response identifies the change and the group started [REQ: a-work-unit-can-be-started-over-the-api, scenario: starting-the-next-runnable-unit]
- [ ] AC-51: WHEN a start request names a group THEN that group is started if it is runnable [REQ: a-work-unit-can-be-started-over-the-api, scenario: targeting-a-specific-group]
- [ ] AC-52: WHEN a work unit is started over the API THEN the response is returned before the unit completes [REQ: a-work-unit-can-be-started-over-the-api, scenario: the-call-does-not-block-on-the-run]
- [ ] AC-53: WHEN a start request is made and no group is runnable THEN the request is refused with a reason naming the blocking condition per group [REQ: an-unstartable-request-is-refused-with-a-reason, scenario: nothing-runnable]
- [ ] AC-54: WHEN a start request is made while a unit holds the lock for that tree THEN the request is refused and the response identifies the running unit [REQ: an-unstartable-request-is-refused-with-a-reason, scenario: already-running]
- [ ] AC-55: WHEN a start request names a group whose dependencies are unsatisfied THEN the request is refused and the unsatisfied dependencies are named [REQ: an-unstartable-request-is-refused-with-a-reason, scenario: targeted-group-is-not-runnable]
- [ ] AC-56: WHEN an answer is submitted for a task awaiting a human THEN the task is no longer reported as awaiting / its group becomes runnable if nothing else blocks it [REQ: an-open-decision-can-be-answered-over-the-api, scenario: answering-releases-the-task]
- [ ] AC-57: WHEN an answer is submitted for a task that is not awaiting an answer THEN the request is refused with a reason [REQ: an-open-decision-can-be-answered-over-the-api, scenario: answering-an-unknown-task]
- [ ] AC-58: WHEN an answer is submitted over the API THEN it is delivered through the same answer connector other uploaders use [REQ: an-open-decision-can-be-answered-over-the-api, scenario: the-api-answer-uses-the-ordinary-connector]
- [ ] AC-59: WHEN the state of a change is queried THEN each task awaiting a human is listed with the question recorded for it [REQ: the-state-a-surface-needs-is-queryable, scenario: awaiting-decisions-are-listed-with-their-questions]
- [ ] AC-60: WHEN a unit is running for the change THEN the response identifies it and reports progress derived from completed task markers [REQ: the-state-a-surface-needs-is-queryable, scenario: a-running-unit-is-reported-with-its-progress]
- [ ] AC-61: WHEN a lock exists whose holding process is no longer alive THEN the response distinguishes that state from a live run [REQ: the-state-a-surface-needs-is-queryable, scenario: a-stale-run-is-not-reported-as-running]

<!-- összesen: 61 -->
