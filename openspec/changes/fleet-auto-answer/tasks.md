## 0. Measure first — where could the operator's past answers have been found

The study runs BEFORE the decider is built and decides its thresholds. Its raw material is the operator's own answers in local transcripts (measured 2026-11-23: 1201 `AskUserQuestion` calls in 31 projects, 978 with structured answers and their option lists, 102 rejected). That material is consumer data: the extracted set, the replay inputs and every per-question result stay machine-local under `~/.local/share/set-core/auto-answer-study/`; only aggregate counts reach `measurements.md`.

- [x] 0.1 Extract the answer set: per answered call the question, its options (with any "(Recommended)" marker), the chosen answer or free text, the notes, the timestamp, the project tree and the session. Machine-local only. Count: answered, free text ("Other"), multi-question calls. [REQ: the-decision-names-its-tier-and-its-source]
- [x] 0.2 Cheap baselines, no model: how often the chosen answer is the option the agent marked as recommended; how often the exclusion patterns fire on the question/options/answer (the share that could never be automatic). Done 2026-11-23: `measurements.md` S1 — 1544 answered questions, 68 % picked the recommended option, 26 % free text, exclusion pattern fires on ≤ 35 %. [REQ: outward-and-irreversible-steps-are-never-answered-automatically]
- [ ] 0.3 Replay WITHOUT time leakage, on a stratified sample (by project and month, ≥ 100 calls): give the decider prompt only what existed before the question's timestamp — tracked files from the project's git state at that moment (`git show <commit-before-ts>:<path>`), the kb search over that state, untracked sources (handoffs, memory) only if their mtime precedes it, and the operator's EARLIER answers in the same project. Record per call: the tier and choice the decider would have given, whether it matches the real answer, and which source class carried it (rules/CLAUDE.md, handoff, open change, bug register, memory, kb section, earlier answer, none). [REQ: the-lookup-reads-where-decisions-live-and-only-reads]
- [ ] 0.4 Report into `measurements.md` as aggregates only: coverage and accuracy per tier; accuracy of `likely` per confidence band (this sets `likely_min`); share per source class; share excluded by the outward rule; share found nowhere. Name the source classes that carried no correct answer, so they can be dropped from the prompt. [REQ: an-automatic-answer-is-proposed-before-it-is-written-and-a-human-answer-wins]
- [ ] 0.5 Decide from 0.4, in `design.md`: keep or change the default bar and window; whether earlier answers become a lookup source (see design D10); whether the decider is worth building at all if accuracy of the allowed tiers is below 90 %. Record the decision with the numbers. [REQ: the-decision-names-its-tier-and-its-source]

## 1. The relay hands its outbound what it is asking about

- [ ] 1.1 CORE `lib/set_orch/fleet/question_relay.py`: every place that runs the outbound (`AskUserQuestion`, permission, continuation) exports `SET_RELAY_KIND`, `SET_RELAY_SESSION` and `SET_RELAY_CWD` to the outbound process; the envelope is unchanged. Test: a fake outbound records its environment and stdin; the envelope bytes equal the pre-change envelope. [REQ: the-relay-tells-its-outbound-what-it-is-asking-about]

## 2. The decider core

- [ ] 2.1 CORE `lib/set_orch/fleet/auto_answer.py`: config readers (`auto_answer.enabled`, `forward_command`, `window_s` default 60, `likely_min` default 0.8, `model`, `never_patterns`, `extra_paths`) through `local_config`; module logger. [REQ: the-decider-is-the-relay-s-outbound-and-forwards-to-the-operator-s]
- [ ] 2.2 CORE the decision parser: one JSON object → `Decision(choice, tier, confidence, sources[{path, excerpt}], outward)`; refuse a missing tier, a `decided`/`found` without a source, a closed-list choice outside the options, any parse failure. Tests in both directions. [REQ: the-decision-names-its-tier-and-its-source]
- [ ] 2.3 CORE the exclusion check: kind `permission` → excluded; deterministic patterns over question, options and choice (English and Hungarian forms of publish/push, deploy, production, send message/email, delete, pay, credential) plus `never_patterns`; the model's `outward` flag; either excludes. Tests: each pattern family fires; prose that merely contains a substring of a pattern word does not (whole-word); the model flag alone excludes; the pattern alone excludes. [REQ: outward-and-irreversible-steps-are-never-answered-automatically]
- [ ] 2.4 CORE the allow rule: `decided`/`found` allowed; `likely` allowed at or above `likely_min`; anything excluded is never allowed. Table test. [REQ: an-automatic-answer-is-proposed-before-it-is-written-and-a-human-answer-wins]
- [ ] 2.5a CORE the knowledge-base step: run `set-kb search --json --limit <n>` in the session's cwd with the question and options; hand path, heading and excerpt of each hit to the prompt as candidates; a failing or non-searchable kb → continue without it and log `kb: not used (<reason>)`. Tests with a fake `set-kb`: hits reach the prompt; a failure does not stop the decision. [REQ: the-lookup-reads-where-decisions-live-and-only-reads]
- [ ] 2.5 CORE the lookup call: a headless `claude -p` in the session's cwd with read-only tools, hooks disabled, no persistence, the relay guard variable, a time bound (default 90 s); the prompt names the decision locations and `extra_paths`, carries the question, options and kind, and asks for the JSON object. Reuse `wait_detect.run_headless`'s shape rather than a second subprocess helper; extend it with a cwd and allowed tools if needed. Test with a fake `claude` on PATH: timeout and non-zero exit → no decision. [REQ: the-lookup-reads-where-decisions-live-and-only-reads]

## 3. The outbound and its worker

- [ ] 3.1 CLI `bin/set-auto-answer` (added to `install.sh`'s list): reads the envelope, and when the switch is off pipes it byte-for-byte to `forward_command` and exits with its code; when on, spawns a detached worker with the envelope and the three relay variables and exits 0 at once. Tests: switch off → forward gets identical bytes; switch on → exit within 2 s with a slow fake model. [REQ: the-decider-is-the-relay-s-outbound-and-forwards-to-the-operator-s]
- [ ] 3.2 CORE the worker: decide (bounded) → if allowed, write the pending record and forward the envelope with the proposal appended to the question text (option, tier, source, write time); if not allowed, forward with the recommendation (or unchanged when there is none); after `window_s`, re-read the pending record and write the answer with an exclusive create unless an answer exists or the record was cancelled. Tests: nobody answers → written; a human answer during the window → nothing written and the human file untouched; cancelled → nothing written. [REQ: an-automatic-answer-is-proposed-before-it-is-written-and-a-human-answer-wins]
- [ ] 3.3 CORE no forward command and no automatic answer → `request_release` for the session. Test. [REQ: without-a-forward-command-an-unanswerable-question-goes-back-to-the-terminal]
- [ ] 3.4 CORE the log: one line per decision with the call id, kind, tier, outcome (written / excluded / below-bar / cancelled / overtaken / no-decision) and source paths; a test asserts the question and answer text never appear in the log. Pending records pruned with the answer store (7 days). [REQ: every-automatic-answer-is-visible-and-cancellable-on-the-fleet]
- [ ] 3.5 Mutation round on 2.3, 2.4 and 3.2's exclusive write: each mutant caught, or the survivor closed with a stronger test. Record the counts in the commit. [REQ: outward-and-irreversible-steps-are-never-answered-automatically]

## 4. The fleet

- [ ] 4.1 API `lib/set_orch/api/fleet.py`: the switch route (`GET`/`POST /api/fleet/auto-answer`), the cancel route (`POST /api/fleet/auto-answer/{call_id}/cancel`), and the waiting listing carries a pending automatic answer (option, tier, seconds left). Route tests. [REQ: every-automatic-answer-is-visible-and-cancellable-on-the-fleet]
- [ ] 4.2 WEB `web/src`: the header switch next to the question-relay switch; on the waiting agent, the pending answer with its tier and countdown and a cancel control. Floating, nothing pushes the layout (ui-quality). Unit tests for the rendering; rebuild `web/`. [REQ: every-automatic-answer-is-visible-and-cancellable-on-the-fleet]
- [ ] 4.3 WEB Visual check in the browser against the running dashboard: the switch, and a pending automatic answer on a real waiting agent with its countdown and cancel. Say what is seen. If the browser cannot be reached this task stays OPEN. [REQ: every-automatic-answer-is-visible-and-cancellable-on-the-fleet]

## 5. Live on this machine

- [ ] 5.1 Configure per design "Migration Plan" with the switch OFF; one relayed question in a scratch session reaches the operator's outbound unchanged. [REQ: the-decider-is-the-relay-s-outbound-and-forwards-to-the-operator-s]
- [ ] 5.2 Switch ON; in a scratch session ask a question whose answer is a decision recorded in that tree's rules → proposed with tier `decided` and its source, written after the window, the session continues. A second question whose answer sits only in an indexed doc section → tier `found`, the source is that section. Then a push question → forwarded with a recommendation, not written. Record both in this task with timestamps and the log lines. [REQ: outward-and-irreversible-steps-are-never-answered-automatically]
- [ ] 5.3 Capability guide row for `set-auto-answer` in `.claude/rules/capability-guide.md`. [REQ: the-decider-is-the-relay-s-outbound-and-forwards-to-the-operator-s]

## Acceptance Criteria (from spec scenarios)

### the-decider-is-the-relay-s-outbound-and-forwards-to-the-operator-s
- [ ] AC-1: WHEN `auto_answer.enabled` is false and a relayed question arrives THEN the forward command receives the envelope byte-for-byte and no answer file is written by the decider [REQ: the-decider-is-the-relay-s-outbound-and-forwards-to-the-operator-s, scenario: switch-off]
- [ ] AC-2: WHEN the relay runs the decider THEN the decider exits within a few seconds, before the decision is made [REQ: the-decider-is-the-relay-s-outbound-and-forwards-to-the-operator-s, scenario: the-relay-is-not-held]

### the-relay-tells-its-outbound-what-it-is-asking-about
- [ ] AC-3: WHEN the continuation carrier hands a question to the outbound THEN the outbound's environment names the kind `continuation`, the session id and the working directory, and the envelope carries no new field [REQ: the-relay-tells-its-outbound-what-it-is-asking-about, scenario: a-continuation-is-relayed]

### the-decision-names-its-tier-and-its-source
- [ ] AC-4: WHEN the project's rules state the operator's decision that answers the question THEN the choice is that option, the tier is `decided`, and the source names the file and quotes the decision [REQ: the-decision-names-its-tier-and-its-source, scenario: a-decision-already-on-record]
- [ ] AC-5: WHEN the model returns a choice that is not one of the options THEN no automatic answer is made and the question is forwarded unchanged [REQ: the-decision-names-its-tier-and-its-source, scenario: an-answer-outside-the-options]

### the-lookup-reads-where-decisions-live-and-only-reads
- [ ] AC-6a: WHEN the answer is written in a documentation section outside the fixed locations THEN that section is among the model's candidates and a `found` choice names it [REQ: the-lookup-reads-where-decisions-live-and-only-reads, scenario: the-knowledge-base-finds-the-answer]
- [ ] AC-6b: WHEN `set-kb` reports search does not work in the project THEN the decision uses the fixed locations alone and the log says the kb was not used [REQ: the-lookup-reads-where-decisions-live-and-only-reads, scenario: the-knowledge-base-cannot-search]
- [ ] AC-6: WHEN the headless call does not answer within its bound THEN the question is forwarded unchanged and no answer is written [REQ: the-lookup-reads-where-decisions-live-and-only-reads, scenario: the-model-call-times-out]

### outward-and-irreversible-steps-are-never-answered-automatically
- [ ] AC-7: WHEN an agent asks whether to push and the record shows earlier push approvals THEN no automatic answer is written and the operator receives the question with the recommendation and its source [REQ: outward-and-irreversible-steps-are-never-answered-automatically, scenario: the-agent-asks-whether-to-push]
- [ ] AC-8: WHEN the permission carrier relays a tool permission THEN no automatic answer is written, whatever the tier [REQ: outward-and-irreversible-steps-are-never-answered-automatically, scenario: a-permission-prompt]
- [ ] AC-9: WHEN the model marks the step as not outward but the question mentions deploying THEN no automatic answer is written [REQ: outward-and-irreversible-steps-are-never-answered-automatically, scenario: only-the-pattern-fires]

### an-automatic-answer-is-proposed-before-it-is-written-and-a-human-answer-wins
- [ ] AC-10: WHEN an allowed choice is proposed and no human answer arrives within the window THEN the decider writes the answer and the agent continues with it [REQ: an-automatic-answer-is-proposed-before-it-is-written-and-a-human-answer-wins, scenario: nobody-answers-within-the-window]
- [ ] AC-11: WHEN the operator answers during the window THEN the decider writes nothing and the agent receives the operator's answer [REQ: an-automatic-answer-is-proposed-before-it-is-written-and-a-human-answer-wins, scenario: the-operator-answers-first]
- [ ] AC-12: WHEN the tier is `likely` and the confidence is below `likely_min` THEN the question is forwarded with the recommendation and nothing is written [REQ: an-automatic-answer-is-proposed-before-it-is-written-and-a-human-answer-wins, scenario: a-likely-choice-below-the-bar]

### without-a-forward-command-an-unanswerable-question-goes-back-to-the-terminal
- [ ] AC-13: WHEN `auto_answer.forward_command` is empty and the question is excluded THEN the session's question is released to its terminal [REQ: without-a-forward-command-an-unanswerable-question-goes-back-to-the-terminal, scenario: no-outbound-and-no-decision]

### every-automatic-answer-is-visible-and-cancellable-on-the-fleet
- [ ] AC-14: WHEN the operator cancels a pending automatic answer on an agent THEN the decider does not write it and the agent's question still waits [REQ: every-automatic-answer-is-visible-and-cancellable-on-the-fleet, scenario: cancel-from-the-fleet]
- [ ] AC-15: WHEN an automatic answer is written THEN the log line names the call id, the tier and the source paths, and contains neither the question nor the answer [REQ: every-automatic-answer-is-visible-and-cancellable-on-the-fleet, scenario: the-log-carries-no-text]
