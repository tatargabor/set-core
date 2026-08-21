# Tasks

⚠ **This change does not start until `work-cycle-answer-is-data` has landed.** B-38: an
answer is interpolated verbatim into a full-session prompt under *"act on them rather than
asking again"* (`prompt.py:95-101` → `runner.py:60-81`). Today only somebody at this machine
can write an answer; this change is precisely what extends that write surface to whoever can
post in a chat channel. Wiring an outbound first would ship the hole.

⚠ **Four wire-format decisions are still open** — `design.md`, *Open Questions*. They are
`- [?]` tasks below, which is this repository's own vocabulary for work held on a person's
answer. ⚠ **They hold nothing on their own:** an awaiting group is skipped, not blocked
behind, and dependants are held only where a group declares `<!-- depends: … -->`. No group
here does, so group 1 is runnable while group 3 — which decides what group 1's field names
should BE — is open. Task 5.4 exists because prose is not a gate.

## 1. The envelope

- [ ] 1.1 A module for the question envelope, with a declared contract version emitted on
      every produced envelope, and a refusal — not a parse — for any version outside the
      supported set
      [REQ: the-envelope-declares-its-version-and-an-unknown-version-is-refused]
- [ ] 1.2 Build an envelope from a change's awaiting tasks, carrying the task identity and the
      question text, derived from the register rather than replacing it
      [REQ: the-awaiting-task-is-the-register-and-the-envelope-is-derived-from-it]
- [ ] 1.3 Options as a discrete list; a joined display form may be produced and is never
      parsed back. Test with an option containing the display separator
      [REQ: options-are-structured-and-a-display-form-is-never-read-back]
- [ ] 1.4 A question with no closed choices carries an empty option list, never an invented
      one [REQ: options-are-structured-and-a-display-form-is-never-read-back]
- [ ] 1.5 `audience` is required; the framework supplies no value of its own, a project's
      declared default passes through unaltered, and no envelope is produced without one
      [REQ: the-audience-is-required-and-the-framework-never-supplies-one]
- [ ] 1.6 The envelope carries no absolute path, no account name and no local directory name;
      the answer's destination is expressed in a form the framework resolves locally
      [REQ: the-envelope-states-where-the-answer-belongs-without-publishing-a-local-path]
- [ ] 1.7 A second outbound with no knowledge of this project can deliver an answer from the
      envelope alone — tested against a fake outbound that is given nothing else
      [REQ: the-envelope-states-where-the-answer-belongs-without-publishing-a-local-path]
- [ ] 1.8 Diagnostics record field, count and error class only — no question text. The
      ANSWER document's fields are enumerated by `work-cycle-answer-is-data`, not here
      [REQ: the-framework-keeps-the-question-content-only-where-the-register-is]

## 2. The register, and what happens when nobody is told

- [ ] 2.1 The task is marked awaiting BEFORE any envelope is produced — assert the order, not
      only the outcome
      [REQ: the-awaiting-task-is-the-register-and-the-envelope-is-derived-from-it]
- [ ] 2.2 With no outbound declared, the question is registered, the dependent groups are
      held, and the cycle reports that nobody was told — distinct from reporting that there
      is no question
      [REQ: the-awaiting-task-is-the-register-and-the-envelope-is-derived-from-it]

## 3. Wire format — HELD on the existing implementation's answer

- [?] 3.1 Field names: agree whether the contract is English and the mapping lives in the
      outbound, or the contract carries both spellings
      [REQ: the-envelope-declares-its-version-and-an-unknown-version-is-refused]
- [?] 3.2 Audience vocabulary: agree whether the contract fixes the values or only requires
      the field [REQ: the-audience-is-required-and-the-framework-never-supplies-one]
- [?] 3.3 Identity: agree whether the key carries a project segment, or the outbound derives
      it from where the question arrived from
      [REQ: the-awaiting-task-is-the-register-and-the-envelope-is-derived-from-it]
- [?] 3.4 How the answer's destination is expressed without a path, in a form a second
      outbound can satisfy
      [REQ: the-envelope-states-where-the-answer-belongs-without-publishing-a-local-path]

## 4. Reaching an outbound

- [ ] 4.1 Resolve the outbound from the project's configuration, with no reference to any
      particular one anywhere in the framework
      [REQ: the-outbound-is-declared-by-the-project-and-never-imported]
- [ ] 4.2 An operator-held opt-in, OUTSIDE the project tree, is required before any outbound
      runs; without it the cycle reports "declared but not enabled" and names where the
      opt-in belongs
      [REQ: a-declared-command-that-reaches-a-network-requires-an-explicit-operator-opt-in]
- [ ] 4.3 A unit that edits its own tree's declaration cannot thereby cause a command to run
      [REQ: a-declared-command-that-reaches-a-network-requires-an-explicit-operator-opt-in]
- [ ] 4.4 A project that declares no outbound still registers questions and holds groups
      [REQ: the-outbound-is-declared-by-the-project-and-never-imported]
- [ ] 4.5 Restate the guards `project_status.py` puts around a declared command and decide
      each one explicitly: flag-shaped value refusal, a cap on the child's output, stderr
      length logged and never content, and what environment the child receives
      [REQ: a-declared-command-that-reaches-a-network-requires-an-explicit-operator-opt-in]
- [ ] 4.6 The hand-off is best-effort: a missing command, a timeout and a non-zero exit are
      each reported with their error class and none changes the run's verdict
      [REQ: the-hand-off-is-best-effort-and-cannot-fail-the-cycle]
- [ ] 4.7 Three-valued state — not handed over / handed over / never succeeded — persisted
      per question, so "already outstanding" is a fact rather than an inference
      [REQ: a-question-that-is-already-outstanding-is-not-handed-over-again]
- [ ] 4.8 A question whose hand-off has never succeeded is retried on later cycles and is
      reported as UNHEARD, not as awaiting a person
      [REQ: a-failed-hand-off-is-retried-and-an-unheard-question-is-reported-as-unheard]
- [ ] 4.9 A successful hand-off suppresses re-sending while the question is outstanding
      [REQ: a-failed-hand-off-is-retried-and-an-unheard-question-is-reported-as-unheard]
- [ ] 4.10 An explicit reissue is recorded against the same identity and does not become a
      second answerable question
      [REQ: a-question-that-is-already-outstanding-is-not-handed-over-again]
- [ ] 4.11 An optional bus notification addressing the recipient's DURABLE identity, never a
      session's. Nothing depends on it being read
      [REQ: a-bus-notification-addresses-an-identity-that-outlives-a-session]

## 5. Evidence

- [ ] 5.1 For every test written alongside a fix here, stash the fix and re-run: a test that
      passes without it proves nothing
      [REQ: the-hand-off-is-best-effort-and-cannot-fail-the-cycle]
- [ ] 5.2 Mutation-test the opt-in gate and the three-valued state specifically — both fail
      in the reassuring direction, where "outstanding" reads as "a person has it"
      [REQ: a-failed-hand-off-is-retried-and-an-unheard-question-is-reported-as-unheard]
- [ ] 5.3 Run the adversarial review BEFORE committing the implementation, not after. The
      first version of this plan was reviewed afterwards and four commits had to be unwound
      [REQ: a-declared-command-that-reaches-a-network-requires-an-explicit-operator-opt-in]
- [ ] 5.4 Make the precondition STRUCTURAL, not prose: a test that fails while an answer can
      reach a unit prompt undelimited. A warning above a checklist is not a gate — measured,
      no group in this file declares a dependency, so nothing here is actually held
      [REQ: a-declared-command-that-reaches-a-network-requires-an-explicit-operator-opt-in]

## Acceptance Criteria (from spec scenarios)

<!-- The awaiting task is the register, and the envelope is derived from it -->
- [ ] AC-1: WHEN a work unit reports an open decision that stops it THEN the task is marked awaiting in the change's task file with its question and any group that declares a dependency on that group is held and the envelope produced afterwards carries the identity of that task [REQ: the-awaiting-task-is-the-register-and-the-envelope-is-derived-from-it, scenario: a-unit-reports-an-open-decision]
- [ ] AC-2: WHEN no outbound is declared, or the hand-off fails THEN the question still stands in the task file, and the groups that depend on it are still held and the cycle reports that nobody was told, rather than reporting that there is no question [REQ: the-awaiting-task-is-the-register-and-the-envelope-is-derived-from-it, scenario: nothing-carried-the-question-anywhere]

<!-- The envelope declares its version and an unknown version is refused -->
- [ ] AC-3: WHEN the framework produces an envelope THEN it carries a contract version [REQ: the-envelope-declares-its-version-and-an-unknown-version-is-refused, scenario: a-produced-envelope-carries-a-version]
- [ ] AC-4: WHEN an envelope declares a version outside the set the reader supports THEN the reader refuses it, states the version it received, and acts on no other field [REQ: the-envelope-declares-its-version-and-an-unknown-version-is-refused, scenario: an-envelope-announces-a-version-the-reader-does-not-know]

<!-- The audience is required, and the framework never supplies one -->
- [ ] AC-5: WHEN a project declares that questions raised by a given part of its work belong to a given audience THEN envelopes from that part carry that audience unaltered by the framework [REQ: the-audience-is-required-and-the-framework-never-supplies-one, scenario: a-project-declares-a-conservative-default]
- [ ] AC-6: WHEN no audience is declared for a question THEN the framework produces no envelope for it and says why and the question remains awaiting, unanswered rather than misdirected [REQ: the-audience-is-required-and-the-framework-never-supplies-one, scenario: no-audience-can-be-determined]

<!-- Options are structured, and a display form is never read back -->
- [ ] AC-7: WHEN one of the offered choices contains the character used to join them for display THEN the structured list still carries that choice as one value and no reader reconstructs the choices from the joined string [REQ: options-are-structured-and-a-display-form-is-never-read-back, scenario: an-option-contains-the-separator-used-for-display]
- [ ] AC-8: WHEN a question accepts free text THEN the envelope carries an empty option list rather than an invented one [REQ: options-are-structured-and-a-display-form-is-never-read-back, scenario: the-question-offers-no-closed-set]

<!-- The envelope states where the answer belongs, without publishing a local path -->
- [ ] AC-9: WHEN an envelope is handed to an outbound that posts it where people can read it THEN it contains no absolute path, no account name and no local directory name [REQ: the-envelope-states-where-the-answer-belongs-without-publishing-a-local-path, scenario: the-envelope-leaves-the-machine]
- [ ] AC-10: WHEN an outbound that has never served this project receives an envelope THEN what the envelope states is sufficient to deliver an answer and it needs no knowledge of the project's layout or of any other outbound [REQ: the-envelope-states-where-the-answer-belongs-without-publishing-a-local-path, scenario: a-second-outbound-answers-a-question-it-did-not-design-for]

<!-- The framework keeps the question content only where the register is -->
- [ ] AC-11: WHEN an envelope is refused, mis-shaped, or fails to reach an outbound THEN the diagnostic names the field, the count and the error class, and contains no question text [REQ: the-framework-keeps-the-question-content-only-where-the-register-is, scenario: a-question-is-routed-and-something-goes-wrong]

<!-- The outbound is declared by the project and never imported -->
- [ ] AC-12: WHEN a project's configuration names a command that carries questions THEN the framework hands questions to that command and no name of any outbound appears in the framework's own source [REQ: the-outbound-is-declared-by-the-project-and-never-imported, scenario: a-project-declares-an-outbound]
- [ ] AC-13: WHEN a project's configuration names no outbound THEN questions are still marked awaiting and still hold the groups that depend on them and the cycle reports that no outbound is declared, which is not the same as reporting that there is no question [REQ: the-outbound-is-declared-by-the-project-and-never-imported, scenario: a-project-declares-none]

<!-- A declared command that reaches a network requires an explicit operator opt-in -->
- [ ] AC-14: WHEN a project's configuration names an outbound and no operator opt-in is present THEN no outbound is run and the cycle reports that an outbound is declared but not enabled, naming where the opt-in belongs [REQ: a-declared-command-that-reaches-a-network-requires-an-explicit-operator-opt-in, scenario: the-project-declares-an-outbound-and-the-operator-has-not-opted-in]
- [ ] AC-15: WHEN a unit changes the declared outbound in the tree it is running in THEN the changed declaration cannot by itself cause a command to be run on the next cycle and the opt-in, which lives outside that tree, still governs [REQ: a-declared-command-that-reaches-a-network-requires-an-explicit-operator-opt-in, scenario: a-work-unit-edits-its-own-tree-s-configuration]

<!-- The hand-off is best-effort and cannot fail the cycle -->
- [ ] AC-16: WHEN the hand-off fails for any reason THEN the failure is reported with its error class and the run's verdict is what the work produced, unchanged by the hand-off [REQ: the-hand-off-is-best-effort-and-cannot-fail-the-cycle, scenario: the-outbound-is-missing-times-out-or-exits-non-zero]

<!-- A failed hand-off is retried, and an unheard question is reported as unheard -->
- [ ] AC-17: WHEN every hand-off attempt for a question has failed THEN later cycles attempt it again and the question is reported as never handed over, not as awaiting a person [REQ: a-failed-hand-off-is-retried-and-an-unheard-question-is-reported-as-unheard, scenario: the-outbound-is-unreachable-overnight]
- [ ] AC-18: WHEN a retried hand-off succeeds THEN the question is recorded as handed over and it is not handed over again while it remains outstanding [REQ: a-failed-hand-off-is-retried-and-an-unheard-question-is-reported-as-unheard, scenario: the-hand-off-eventually-succeeds]

<!-- A question that is already outstanding is not handed over again -->
- [ ] AC-19: WHEN a cycle runs again and the same task is still awaiting an answer that was handed over successfully THEN the question is not handed to the outbound a second time and the run reports it as outstanding rather than as newly raised [REQ: a-question-that-is-already-outstanding-is-not-handed-over-again, scenario: the-nightly-cycle-restarts-while-a-question-is-outstanding]
- [ ] AC-20: WHEN an outstanding question is explicitly reissued THEN the reissue is recorded against the same identity and it does not become a second, independently answerable question [REQ: a-question-that-is-already-outstanding-is-not-handed-over-again, scenario: a-question-is-deliberately-reissued]

<!-- A bus notification addresses an identity that outlives a session -->
- [ ] AC-21: WHEN a notification is addressed to one session's identity and that session never returns THEN the entry is undeliverable for the lifetime of the room [REQ: a-bus-notification-addresses-an-identity-that-outlives-a-session, scenario: a-session-identity-is-used]
- [ ] AC-22: WHEN no session of the recipient ever reads the notification THEN the question is still recorded as handed over or not handed over by the outcome of the hand-off itself and nothing about the cycle's behaviour depends on the notification [REQ: a-bus-notification-addresses-an-identity-that-outlives-a-session, scenario: the-bus-is-never-read]
