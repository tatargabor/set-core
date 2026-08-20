# Tasks

⚠ **This task list stalls its own engine, deliberately.** Groups 3 and 4 each hold a `- [?]`
task, and `groups.py`'s `is_complete` is `not open_tasks and not awaiting_tasks` — so both
groups stay incomplete and hold their dependants until the four are answered. A run that
stops there is the mechanism working, not a broken engine.

⚠ **Four wire-format decisions are still open** — see `design.md`, *Open Questions*. They are
carried here as `- [?]` tasks, which is this repository's own vocabulary for work that is
held on a person's answer. Nothing in group 3 or 4 may be built with a guessed field name.

## 1. The envelope

- [ ] 1.1 A module for the question envelope, with a declared contract version and a
      refusal — not a parse — for any version outside the supported set
      [REQ: the-envelope-declares-its-version-and-an-unknown-version-is-refused]
- [ ] 1.2 Build an envelope from a change's awaiting tasks, carrying the task's identity,
      the question text and the answer location
      [REQ: the-task-file-is-the-register-and-the-envelope-is-derived-from-it]
- [ ] 1.3 Options as a discrete list; a joined display form may be produced and is never
      parsed back. Test with an option containing the display separator
      [REQ: options-are-structured-and-a-display-form-is-never-read-back]
- [ ] 1.4 A question with no closed choices carries an empty option list, never an invented
      one [REQ: options-are-structured-and-a-display-form-is-never-read-back]
- [ ] 1.5 The envelope carries the answer location, and no reader infers it
      [REQ: the-envelope-states-where-the-answer-is-expected]
- [ ] 1.6 `audience` is required and the framework supplies no value of its own; a project's
      declared default is passed through unchanged
      [REQ: the-audience-is-required-and-the-framework-never-supplies-one]
- [ ] 1.7 Logging records shape, counts and error classes only — no question or answer text
      in any diagnostic, following `project_status.py`'s existing rule
      [REQ: the-framework-persists-nothing-derived-from-the-question-content]

## 2. Raising, and the register

- [ ] 2.1 On `NEEDS_INPUT`, confirm the awaiting task is written and the dependent groups
      stay held before any envelope is produced — assert the ORDER, not just the outcome
      [REQ: the-task-file-is-the-register-and-the-envelope-is-derived-from-it]
- [ ] 2.2 With no outbound declared, the question is registered and the cycle reports that
      nobody was told — distinct from reporting that there is no question
      [REQ: the-task-file-is-the-register-and-the-envelope-is-derived-from-it]

## 3. Reaching an outbound

- [?] 3.1 Field names: agree whether the contract is English and the mapping lives in the
      outbound, or the contract carries both spellings
      [REQ: the-envelope-declares-its-version-and-an-unknown-version-is-refused]
- [?] 3.2 Audience vocabulary: agree whether the contract fixes the values or only requires
      the field [REQ: the-audience-is-required-and-the-framework-never-supplies-one]
- [?] 3.3 Identity: agree whether the key carries a project segment, or the outbound derives
      it from where the question arrived from
      [REQ: the-key-is-a-field-and-unrecognised-entries-are-left-untouched]
- [ ] 3.4 Resolve the outbound from the project's configuration, with no reference to any
      particular one anywhere in the framework
      [REQ: the-outbound-is-declared-by-the-project-and-never-imported]
- [ ] 3.5 A project that declares no outbound still registers questions and holds groups
      [REQ: the-outbound-is-declared-by-the-project-and-never-imported]
- [ ] 3.6 The hand-off is best-effort: a missing command, a timeout and a non-zero exit are
      each reported with their error class and none changes the run's verdict
      [REQ: the-hand-off-is-best-effort-and-cannot-fail-the-cycle]
- [ ] 3.7 An outbound refuses an envelope with no audience, and the question stays unanswered
      rather than being sent to a guessed audience
      [REQ: the-audience-is-required-and-the-framework-never-supplies-one]
- [ ] 3.8 An optional bus notification alongside the hand-off, carrying a pointer. It is an
      accelerator: no behaviour may depend on it, and nothing promises when it is read
      [REQ: a-file-is-the-record-and-a-message-is-only-sooner]
- [ ] 3.9 The notification addresses the recipient's DURABLE identity, never a single
      session's. Measured 2026-08-20: addressing is stored verbatim, so an entry addressed to
      a session that never returns is undeliverable for the lifetime of the room
      [REQ: a-bus-notification-addresses-an-identity-that-outlives-a-session]
- [ ] 3.10 A question already outstanding is not handed over again on a re-run, restart or
      resume; the run reports it as outstanding rather than newly raised
      [REQ: a-question-is-handed-over-once-however-often-the-cycle-runs]
- [ ] 3.11 An explicit reissue is recorded against the same identity and does not become a
      second answerable question
      [REQ: a-question-is-handed-over-once-however-often-the-cycle-runs]

## 4. Reading the answer back

- [?] 4.1 Answer location: agree the default for an arbitrary project, and state it in the
      contract rather than leaving a second outbound to infer one
      [REQ: the-envelope-states-where-the-answer-is-expected]
- [ ] 4.2 Read answers from the stated location; the key is a field inside the answer and the
      filename is never used to route it
      [REQ: the-key-is-a-field-and-unrecognised-entries-are-left-untouched]
- [ ] 4.3 An answer whose key this reader does not recognise is left byte-for-byte untouched.
      Test with a foreign key present in the same directory
      [REQ: the-key-is-a-field-and-unrecognised-entries-are-left-untouched]
- [ ] 4.4 Quarantine with a stated reason: unparseable, no key, no answer text, or a task
      that is absent or no longer awaiting. Never delete, never apply to a neighbour
      [REQ: a-malformed-answer-is-quarantined-with-a-reason-and-never-deleted]
- [ ] 4.5 An answer arriving by both carriers is applied once; the second is recognised as
      already applied [REQ: a-file-is-the-record-and-a-message-is-only-sooner]
- [ ] 4.6 An answer produced while nothing was running is applied at the next run
      [REQ: a-file-is-the-record-and-a-message-is-only-sooner]
- [ ] 4.7 Apply answers under the engine's existing run scoping; an answer never releases a
      different run's work [REQ: an-answer-is-applied-to-the-run-that-asked]
- [ ] 4.8 Applying an answer records the task as answered and releases the held dependants,
      carrying the answer to the next run through `prompt.py`'s existing `answers` route
      [REQ: applying-an-answer-releases-the-work-it-was-holding]
- [ ] 4.9 A group holding several awaiting tasks keeps holding its dependants until the last
      one is answered [REQ: applying-an-answer-releases-the-work-it-was-holding]

## 5. Evidence

- [ ] 5.1 For every test written alongside a fix in this change, stash the fix and re-run:
      a test that passes without it proves nothing [REQ: the-hand-off-is-best-effort-and-cannot-fail-the-cycle]
- [ ] 5.2 Mutation-test the quarantine and the foreign-key path specifically — both fail in
      the reassuring direction, where a silent deletion looks like a clean directory
      [REQ: a-malformed-answer-is-quarantined-with-a-reason-and-never-deleted]
- [ ] 5.3 Regression check against a baseline worktree using the recipe in `CLAUDE.md`, with
      the import roots asserted — never a bare count
      [REQ: the-framework-persists-nothing-derived-from-the-question-content]

## Acceptance Criteria (from spec scenarios)

<!-- The task file is the register, and the envelope is derived from it -->
- [ ] AC-1: WHEN a work-cycle section returns `NEEDS_INPUT` THEN the question is written into the change's task file as an awaiting task and the groups that depend on it remain held and the envelope produced afterwards carries the identity of that task [REQ: the-task-file-is-the-register-and-the-envelope-is-derived-from-it, scenario: a-section-reports-that-it-needs-a-person]
- [ ] AC-2: WHEN no outbound is declared, or the hand-off fails THEN the question still stands in the task file and the groups are still held and the cycle reports that nobody was told, rather than reporting that there is no question [REQ: the-task-file-is-the-register-and-the-envelope-is-derived-from-it, scenario: nothing-carried-the-question-anywhere]

<!-- The envelope declares its version and an unknown version is refused -->
- [ ] AC-3: WHEN an envelope declares a version outside the set the reader supports THEN the reader refuses it and states the version it received and no field of that envelope is read [REQ: the-envelope-declares-its-version-and-an-unknown-version-is-refused, scenario: an-envelope-announces-a-version-the-reader-does-not-know]

<!-- The audience is required, and the framework never supplies one -->
- [ ] AC-4: WHEN a project states that questions of a given origin belong to a given audience THEN envelopes from that origin carry that audience and the framework does not alter it [REQ: the-audience-is-required-and-the-framework-never-supplies-one, scenario: a-project-declares-a-conservative-default]
- [ ] AC-5: WHEN an envelope carries no audience, or an empty one THEN the outbound refuses to carry it and states why and the question remains in the task file, unanswered rather than misdirected [REQ: the-audience-is-required-and-the-framework-never-supplies-one, scenario: an-envelope-arrives-with-no-audience]

<!-- Options are structured, and a display form is never read back -->
- [ ] AC-6: WHEN one of the offered choices contains the character used to join them for display THEN the structured list still carries that choice as one value and no reader reconstructs the choices from the joined string [REQ: options-are-structured-and-a-display-form-is-never-read-back, scenario: an-option-contains-the-separator-used-for-display]
- [ ] AC-7: WHEN a question offers no closed set of choices THEN the envelope carries an empty option list rather than an invented one [REQ: options-are-structured-and-a-display-form-is-never-read-back, scenario: the-question-accepts-free-text]

<!-- The envelope states where the answer is expected -->
- [ ] AC-8: WHEN an outbound that has never served this project receives a question THEN it writes the answer to the location the envelope states and it needs no knowledge of the project's layout or of any other outbound [REQ: the-envelope-states-where-the-answer-is-expected, scenario: a-second-outbound-answers-a-question-it-did-not-design-for]
- [ ] AC-9: WHEN the outbound cannot write to the location the envelope states THEN it records the answer somewhere it can write and says that it did so and the answer is not discarded [REQ: the-envelope-states-where-the-answer-is-expected, scenario: the-stated-location-cannot-be-written-to]

<!-- The framework persists nothing derived from the question content -->
- [ ] AC-10: WHEN an envelope is refused, mis-shaped, or fails to reach an outbound THEN the diagnostic names the field, the count and the error class and it contains no part of the question or answer text [REQ: the-framework-persists-nothing-derived-from-the-question-content, scenario: a-question-is-routed-and-something-goes-wrong]

<!-- The outbound is declared by the project and never imported -->
- [ ] AC-11: WHEN a project's configuration names a command that carries questions THEN the framework hands questions to that command and the framework's own code names no outbound [REQ: the-outbound-is-declared-by-the-project-and-never-imported, scenario: a-project-declares-an-outbound]
- [ ] AC-12: WHEN a project's configuration names no outbound THEN questions are still registered in the task file and groups are still held and the cycle reports that no outbound is declared, rather than failing [REQ: the-outbound-is-declared-by-the-project-and-never-imported, scenario: a-project-declares-none]

<!-- The hand-off is best-effort and cannot fail the cycle -->
- [ ] AC-13: WHEN the hand-off fails for any reason THEN the failure is reported with its error class and the run's verdict is what the work produced, unchanged by the hand-off [REQ: the-hand-off-is-best-effort-and-cannot-fail-the-cycle, scenario: the-outbound-is-missing-times-out-or-exits-non-zero]

<!-- A file is the record and a message is only sooner -->
- [ ] AC-14: WHEN the answer is produced while no session of the asking project is running THEN the answer is on disk when a session next runs and it is applied then [REQ: a-file-is-the-record-and-a-message-is-only-sooner, scenario: nothing-is-running-when-the-answer-is-given]
- [ ] AC-15: WHEN an answer arrives both as a message and as a file THEN the task is answered once and the second arrival is recognised as already applied rather than applied again [REQ: a-file-is-the-record-and-a-message-is-only-sooner, scenario: both-carriers-deliver]

<!-- A question is handed over once, however often the cycle runs -->
- [ ] AC-16: WHEN a cycle runs again and the same task is still awaiting an answer THEN the question is not handed to the outbound a second time and the run reports it as already outstanding rather than as newly raised [REQ: a-question-is-handed-over-once-however-often-the-cycle-runs, scenario: the-nightly-cycle-restarts-while-a-question-is-outstanding]
- [ ] AC-17: WHEN an outstanding question is explicitly reissued, for example because it went unanswered for too long THEN the reissue is recorded as such against the same identity and it does not become a second, independently answerable question [REQ: a-question-is-handed-over-once-however-often-the-cycle-runs, scenario: a-question-is-deliberately-re-raised]

<!-- A bus notification addresses an identity that outlives a session -->
- [ ] AC-18: WHEN a notification is addressed to the recipient's durable identity and every session of that recipient has since ended THEN a later session of the same recipient is still addressed by that entry [REQ: a-bus-notification-addresses-an-identity-that-outlives-a-session, scenario: the-recipient-s-session-ends-before-it-reads]
- [ ] AC-19: WHEN a notification is addressed to one session's identity and that session never returns THEN the entry is undeliverable for the lifetime of the room and the contract forbids this form of addressing for questions and answers [REQ: a-bus-notification-addresses-an-identity-that-outlives-a-session, scenario: a-session-identity-is-used-by-mistake]

<!-- The key is a field, and unrecognised entries are left untouched -->
- [ ] AC-20: WHEN the directory holds answers whose keys belong to another reader THEN this reader applies only the ones it recognises and the others are neither moved, altered, nor deleted [REQ: the-key-is-a-field-and-unrecognised-entries-are-left-untouched, scenario: two-readers-share-one-answer-directory]
- [ ] AC-21: WHEN an answer's filename suggests one task and its key names another THEN the key decides and the filename is not used to route the answer [REQ: the-key-is-a-field-and-unrecognised-entries-are-left-untouched, scenario: the-filename-disagrees-with-the-key]

<!-- A malformed answer is quarantined with a reason and never deleted -->
- [ ] AC-22: WHEN an answer's key names a task that is absent or no longer awaiting THEN the answer is quarantined with that reason and no neighbouring task is answered in its place [REQ: a-malformed-answer-is-quarantined-with-a-reason-and-never-deleted, scenario: the-answer-names-a-task-that-no-longer-exists]
- [ ] AC-23: WHEN an answer cannot be parsed THEN it is quarantined with the parse error's class and the original content is preserved [REQ: a-malformed-answer-is-quarantined-with-a-reason-and-never-deleted, scenario: the-answer-is-not-readable]

<!-- An answer is applied to the run that asked -->
- [ ] AC-24: WHEN an answer arrives for a question raised by one of them THEN only that run's held groups are released and the other run is unaffected [REQ: an-answer-is-applied-to-the-run-that-asked, scenario: two-runs-of-the-same-project-are-in-flight]

<!-- Applying an answer releases the work it was holding -->
- [ ] AC-25: WHEN the last awaiting task of a group is answered THEN that group is no longer holding its dependants and the answer is available to the next run as context, through the route that already exists rather than a second one [REQ: applying-an-answer-releases-the-work-it-was-holding, scenario: the-held-group-runs]
- [ ] AC-26: WHEN a group holds more than one awaiting task and one is answered THEN that task is recorded as answered and the group continues to hold its dependants until the rest are answered [REQ: applying-an-answer-releases-the-work-it-was-holding, scenario: one-of-several-questions-is-answered]
