## 1. The queue and its hook

- [ ] 1.1 Define the queue entry format (transcript path, project slug, ISO timestamp) and its directory under the framework's durable per-user store; write it down before writing code, because the entry is the contract between two processes [REQ: the-hook-enqueues-and-does-nothing-else]
- [ ] 1.2 Add the `SessionEnd` hook script under `bin/`, doing nothing but writing one entry, and make it fail visibly when the queue directory is unwritable [REQ: the-hook-enqueues-and-does-nothing-else]
- [ ] 1.3 Register the hook on the `SessionEnd` event in the framework's settings, and assert in a test that nothing registers this behaviour on `Stop` — the old carrier must be unable to come back unnoticed [REQ: the-framework-registers-sessionend-never-stop-for-this-purpose]
- [ ] 1.4 Prove the hook's bound: a session with a large transcript produces the same small entry and the hook never opens the transcript (measure by trace or by an unreadable transcript that still yields an entry) [REQ: the-hook-enqueues-and-does-nothing-else]

## 2. Admissibility — every gate a refusal

- [ ] 2.1 Implement the candidate model and the gate chain, where any gate drops the whole candidate and records the deciding rule; no gate may edit a candidate into acceptability [REQ: a-candidate-that-claims-something-about-the-users-state-is-refused]
- [ ] 2.2 Gate: no claim about the user's state. Test it on the two measured strings that the removed detector inverted into anger, and on a genuine stated preference that must pass [REQ: a-candidate-that-claims-something-about-the-users-state-is-refused]
- [ ] 2.3 Gate: no harness artifact stored verbatim — task notification, cross-session message, another agent's system prompt, system reminder, raw transcript fragment [REQ: a-harness-artifact-is-never-stored-verbatim]
- [ ] 2.4 Gate: nothing the repository already records — instruction files, commit history, documented past fixes [REQ: a-candidate-the-repository-already-records-is-refused]
- [ ] 2.5 Every admitted candidate must name where in the session it came from; one that cannot is refused, because that is the only handle on a hallucinated "fact" [REQ: a-run-is-judged-by-its-trace-not-by-its-report]

## 3. Confidentiality, before the write

- [ ] 3.1 Call the existing runtime slug resolution (registry + allowlist) as a library rather than re-implementing it; a second list is a second copy and drifts when written [REQ: confidentiality-is-enforced-before-the-write-not-after]
- [ ] 3.2 Refuse a matching candidate and never echo the matched value into the refusal, the trace, or any log — log the shape, not the content [REQ: confidentiality-is-enforced-before-the-write-not-after]
- [ ] 3.3 When the list cannot be resolved, write nothing and report; an empty list must never be treated as "no matches" [REQ: confidentiality-is-enforced-before-the-write-not-after]
- [ ] 3.4 Test the fail-open direction explicitly: with an unreadable registry the distiller writes zero files, and the test fails if it writes any [REQ: confidentiality-is-enforced-before-the-write-not-after]

## 4. The write path and the budgets

- [ ] 4.1 Write an admitted fact as one file with the native frontmatter (`name`, `description`, `metadata.type`) into the project's own memory directory [REQ: an-admitted-fact-becomes-one-file-plus-one-index-line]
- [ ] 4.2 Append exactly one pointer line to the index, under a POSIX-atomic lock, and re-measure the budget inside the lock rather than before it [REQ: an-admitted-fact-becomes-one-file-plus-one-index-line]
- [ ] 4.3 Deduplicate against existing memories: an equivalent fact updates its file and does not grow the index [REQ: an-admitted-fact-becomes-one-file-plus-one-index-line]
- [ ] 4.4 Enforce the index budget as a refusal at 150 lines / 20 KB, reporting the measured line count and byte size [REQ: the-index-budget-is-a-refusal]
- [ ] 4.5 Assert no second store: a test that fails if the run creates any file outside the project's memory directory and the queue [REQ: an-admitted-fact-becomes-one-file-plus-one-index-line]

## 5. Reading a finished transcript

- [ ] 5.1 Read the queued transcript end-to-end and produce candidates; handle the measured record types rather than assuming a flat message list [REQ: a-distillation-reads-only-a-completed-transcript]
- [ ] 5.2 An absent transcript retires its entry with a recorded reason and writes nothing [REQ: a-distillation-reads-only-a-completed-transcript]
- [ ] 5.3 A transcript whose session the runtime still holds open stays queued — determine liveness by identity (the session's own record), never by a remembered PID [REQ: a-distillation-reads-only-a-completed-transcript]

## 6. Trace and retirement

- [ ] 6.1 Write a machine-readable trace per run: the transcript consumed, each candidate's disposition with its deciding rule, and every path written [REQ: a-run-is-judged-by-its-trace-not-by-its-report]
- [ ] 6.2 Retire a queue entry only when a trace exists naming that transcript; a zero exit with no trace is a failure [REQ: a-queue-entry-is-retired-only-against-evidence]
- [ ] 6.3 Move a repeatedly failing entry aside with its reasons preserved — never delete it, never retry forever [REQ: a-queue-entry-is-retired-only-against-evidence]

## 7. Proving it, and shipping it

- [ ] 7.1 Mutation-test each gate: with the gate's condition inverted the suite must go red. Clear `__pycache__` and set `PYTHONDONTWRITEBYTECODE=1` between mutations, assert the mutation pattern is unique, and re-check the file after the restore [REQ: a-candidate-that-claims-something-about-the-users-state-is-refused]
- [ ] 7.2 Run the distiller by hand over real queued entries and read every proposed line; the pass condition is that a person would have written each one, not that files appeared [REQ: a-run-is-judged-by-its-trace-not-by-its-report]
- [ ] 7.3 Regression check by set diff against a properly isolated baseline (the recipe in the project's instruction file, including the import-leak assertion) — never by comparing counts [REQ: a-run-is-judged-by-its-trace-not-by-its-report]
- [ ] 7.4 Decide and record the two open questions from `design.md` — who executes the pass, and whether it deploys to consumer projects by default [REQ: the-framework-registers-sessionend-never-stop-for-this-purpose]
- [ ] 7.5 Update the project's memory rules to state that a distillation exists, what it may write, and that it is the only automatic writer [REQ: an-admitted-fact-becomes-one-file-plus-one-index-line]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN the distiller processes a queue entry naming an existing transcript THEN it reads that file end-to-end and produces zero or more candidates [REQ: a-distillation-reads-only-a-completed-transcript, scenario: a-queued-transcript-is-distilled]
- [ ] AC-2: WHEN a queue entry names an absent transcript THEN the entry is retired with a recorded reason and no memory file is written [REQ: a-distillation-reads-only-a-completed-transcript, scenario: the-named-transcript-no-longer-exists]
- [ ] AC-3: WHEN a transcript belongs to a session still held open THEN the entry stays queued [REQ: a-distillation-reads-only-a-completed-transcript, scenario: a-live-session-is-never-a-source]
- [ ] AC-4: WHEN a candidate is derived from an emphatic user message THEN no memory file is written and the refusal names its rule [REQ: a-candidate-that-claims-something-about-the-users-state-is-refused, scenario: an-exclamation-mark-is-not-anger]
- [ ] AC-5: WHEN the user states a working preference and the candidate records it as a fact THEN the candidate passes the gate [REQ: a-candidate-that-claims-something-about-the-users-state-is-refused, scenario: a-stated-preference-is-admissible]
- [ ] AC-6: WHEN a candidate's body is a task notification or system reminder THEN it is refused and no file is written [REQ: a-harness-artifact-is-never-stored-verbatim, scenario: a-task-notification-reaches-the-distiller]
- [ ] AC-7: WHEN a candidate states a durable fact in the distiller's own words THEN it passes the gate [REQ: a-harness-artifact-is-never-stored-verbatim, scenario: a-fact-learned-from-a-notification-survives]
- [ ] AC-8: WHEN a candidate restates something the project's instruction file already carries THEN it is refused [REQ: a-candidate-the-repository-already-records-is-refused, scenario: a-fact-already-in-the-rule-book]
- [ ] AC-9: WHEN a candidate contains a private slug, partner name or personal name THEN no file is written and the refusal does not reproduce the matched text [REQ: confidentiality-is-enforced-before-the-write-not-after, scenario: a-consumer-project-name-appears-in-a-candidate]
- [ ] AC-10: WHEN the gate needs its pattern list THEN it resolves it at run time and no pattern file naming a consumer exists in this repository [REQ: confidentiality-is-enforced-before-the-write-not-after, scenario: the-list-is-never-committed-to-this-repository]
- [ ] AC-11: WHEN the private-slug list cannot be resolved THEN the distiller writes nothing and reports the failure [REQ: confidentiality-is-enforced-before-the-write-not-after, scenario: the-registry-is-unreadable]
- [ ] AC-12: WHEN a candidate is admitted THEN exactly one new memory file exists and the index grew by exactly one line [REQ: an-admitted-fact-becomes-one-file-plus-one-index-line, scenario: one-fact-one-file-one-line]
- [ ] AC-13: WHEN an admitted fact is already covered by an existing memory THEN that file is updated and the index does not grow [REQ: an-admitted-fact-becomes-one-file-plus-one-index-line, scenario: an-equivalent-memory-already-exists]
- [ ] AC-14: WHEN appending would take the index past 150 lines or 20 KB THEN nothing is appended and the report states the measured size [REQ: the-index-budget-is-a-refusal, scenario: the-index-is-at-the-budget]
- [ ] AC-15: WHEN the index is within budget THEN the pointer line is appended and the measured size is recorded in the trace [REQ: the-index-budget-is-a-refusal, scenario: the-index-is-below-the-budget]
- [ ] AC-16: WHEN a run returns success and its trace names no written file and no refusal THEN the entry is not retired and the run is recorded as failed [REQ: a-run-is-judged-by-its-trace-not-by-its-report, scenario: the-distiller-reports-success-but-wrote-nothing]
- [ ] AC-17: WHEN a candidate is refused THEN the trace names the refusing rule without reproducing any matched confidential value [REQ: a-run-is-judged-by-its-trace-not-by-its-report, scenario: every-refusal-is-attributable]
- [ ] AC-18: WHEN a session ends THEN exactly one queue entry is created for it [REQ: the-framework-registers-sessionend-never-stop-for-this-purpose, scenario: a-session-ends]
- [ ] AC-19: WHEN an assistant turn ends mid-session THEN no queue entry is created [REQ: the-framework-registers-sessionend-never-stop-for-this-purpose, scenario: an-assistant-turn-ends-mid-session]
- [ ] AC-20: WHEN a session with a very large transcript ends THEN the hook writes one small entry and does not read the transcript [REQ: the-hook-enqueues-and-does-nothing-else, scenario: a-long-session-ends]
- [ ] AC-21: WHEN the queue directory is unwritable THEN the hook fails visibly and the session's end is not recorded as processed [REQ: the-hook-enqueues-and-does-nothing-else, scenario: the-hook-cannot-write-its-entry]
- [ ] AC-22: WHEN a distillation subprocess exits zero but leaves no trace naming the transcript THEN the entry stays queued and the failure is recorded [REQ: a-queue-entry-is-retired-only-against-evidence, scenario: a-distiller-reports-done-with-no-trace]
- [ ] AC-23: WHEN an entry has failed a bounded number of times THEN it is moved aside with its failure reasons preserved [REQ: a-queue-entry-is-retired-only-against-evidence, scenario: a-repeatedly-failing-entry]
