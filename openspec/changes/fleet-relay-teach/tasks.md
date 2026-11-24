## 1. The taught-rules file and its commit (core, `lib/set_orch/fleet/relay_teach.py`)

- [x] 1.1 `main_checkout(cwd)`: the first `worktree` of `git worktree list --porcelain` for the repository holding `cwd`, or a reason when `cwd` is not in a git repository. Unit test with a real repo and a linked worktree. [REQ: taught-rules-live-in-the-project-and-are-committed-there]
- [x] 1.2 `append_rule(root, question, answer, explanation, today)`: create `.claude/rules/auto-answer-taught.md` with its header when missing; append one entry (heading from the question's first line, question, answer, explanation when given, date) and never rewrite earlier entries; no session id, path or name in it. [REQ: taught-rules-live-in-the-project-and-are-committed-there]
- [x] 1.3 `commit_rule(root, path)`: `git add -- <file>` + `git commit -m "auto-answer: taught rule <date>" -- <file>`, hooks running, a short retry on `index.lock`, refusal on a detached HEAD. Return the short sha and branch, or the reason. Tests: another staged file stays staged and out of the commit; a refusing pre-commit hook leaves the file written and returns the hook's message. [REQ: taught-rules-live-in-the-project-and-are-committed-there]
- [x] 1.4 `teach(call_id, answer, explanation)`: refuse a permission prompt or a multi-question call. Otherwise deliver the answer first (`question_relay.deliver_answer`), then append and commit. Report each step's result independently. Logs carry the project, file and sha, never the rule text. [REQ: a-waiting-question-can-be-answered-once-and-taught-for-next-time]

## 2. The decider reads the rules (core, `auto_answer.py`, `auto_answer_worker.py`)

- [x] 2.1 `taught_rules(cwd)`: the taught file of the main checkout and of the call's own tree (deduplicated), capped at 20 KB keeping the newest entries, with a WARNING when cut. In the prompt verbatim, labelled, with the condition instruction. The main checkout's file is also a decision location, so its quotes check as `decided`. [REQ: a-standing-delegation-is-decided-on-not-waited-for]
- [x] 2.2 `exclusion(..., taught=False)`: with `taught=True` only a permission prompt excludes. The worker sets it when a CHECKED decision reference's path is a taught-rules file, and logs `taught: true` on the decision record. Tests: a rule-backed "yes" to a production question is allowed; an unchecked quote is not enough; a permission prompt stays excluded. [REQ: outward-and-irreversible-steps-are-never-answered-automatically]
- [x] 2.3 Mutation round on 2.2 (the pass direction): drop the `checked` condition, drop the path condition, drop the permission guard. Each mutant must be caught. [REQ: outward-and-irreversible-steps-are-never-answered-automatically]

## 3. The API (`lib/set_orch/api/fleet.py`)

- [x] 3.1 `GET /api/fleet/question-relay/{call_id}/detail`: the pending record's questions (text, options, choice, tier, outcome, reason, checked references) plus the waiting record's kind, age, count and release flag. With no pending record, say so. 404 when the call is not waiting. [REQ: each-waiting-question-can-be-opened-in-full]
- [x] 3.2 `POST /api/fleet/question-relay/{call_id}/teach` `{answer, explanation}` → the step results of 1.4. 409 when the call cannot be taught, with the reason. [REQ: a-waiting-question-can-be-answered-once-and-taught-for-next-time]

## 4. The panel (`web/src/components/FleetRelay.tsx`, `web/src/lib/fleetRelay.ts`)

- [x] 4.1 "details" on every row: an overlay above the panel with its own close control. It shows the questions in full with their options, the decider's verdict per question, and what the call waits for. [REQ: each-waiting-question-can-be-opened-in-full]
- [x] 4.2 "teach" on single-question, non-permission rows: an answer field (pre-filled with the proposal, else the recommended option), the options as one-click fills, an explanation field, and save. The result shows "answered"/why not and the sha + branch/why not. A failure stays open; success closes after 10 s. Permission and multi-question rows get no "teach", and their details say why. [REQ: a-waiting-question-can-be-answered-once-and-taught-for-next-time]
- [x] 4.3 Unit tests for the pure helpers (prefill choice, teachable, result line); `tsc -b`, the web test suite, `pnpm build`. [REQ: a-waiting-question-can-be-answered-once-and-taught-for-next-time]
- [x] 4.4 Visual check in the browser on the running dashboard: open the panel with a real waiting call, open details, open teach. Say what is seen. Nothing under an overlay may move. Do not save on a real consumer's question during the check; a save is exercised on a scratch session (5.1). [REQ: each-waiting-question-can-be-opened-in-full]

## 5. Live

- [x] 5.1 In a scratch git project with a relay-wired scratch session: ask a question, teach it from the panel with an explanation. The agent receives the answer, the file holds the entry, and `git log -1 --stat` shows only that file. Then ask the same question again in a new session: the decider answers `decided` quoting the rule (or the agent no longer asks). Record it in `measurements.md`. [REQ: a-waiting-question-can-be-answered-once-and-taught-for-next-time]
- [x] 5.2 Capability guide row (`.claude/rules/capability-guide.md`): teach a project rule from the relay panel. [REQ: taught-rules-live-in-the-project-and-are-committed-there]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the operator opens Details on a waiting question the decider abstained on THEN the overlay shows the question text, its options, outcome `no-decision` and the reason, and nothing under it moves [REQ: each-waiting-question-can-be-opened-in-full, scenario: a-question-the-decider-abstained-on]
- [x] AC-2: WHEN Details opens on a call with no decider record THEN it says so and shows what the relay knows [REQ: each-waiting-question-can-be-opened-in-full, scenario: a-call-the-decider-never-saw]
- [x] AC-3: WHEN the operator teaches an answer with an explanation THEN the agent receives it at once, the file gains one verbatim entry, and the overlay shows the sha [REQ: a-waiting-question-can-be-answered-once-and-taught-for-next-time, scenario: teaching-an-answer-with-a-condition]
- [x] AC-4: WHEN a rule is saved after the call ended THEN it is still written and committed, and the overlay says nothing was answered [REQ: a-waiting-question-can-be-answered-once-and-taught-for-next-time, scenario: the-question-ended-before-the-save]
- [x] AC-5: WHEN a permission prompt waits THEN its row has no Teach and its Details say why [REQ: a-waiting-question-can-be-answered-once-and-taught-for-next-time, scenario: a-permission-prompt]
- [x] AC-6: WHEN the call comes from a linked worktree THEN the rule is committed in the main worktree and the linked one is untouched [REQ: taught-rules-live-in-the-project-and-are-committed-there, scenario: a-call-from-a-linked-worktree]
- [x] AC-7: WHEN other files are staged in the main checkout THEN the commit holds only the rules file and the others stay staged [REQ: taught-rules-live-in-the-project-and-are-committed-there, scenario: another-session-has-staged-work-in-the-checkout]
- [x] AC-8: WHEN the pre-commit hook refuses THEN the rule stays uncommitted, the call is answered, and the refusal is shown [REQ: taught-rules-live-in-the-project-and-are-committed-there, scenario: a-commit-hook-refuses]
- [x] AC-9: WHEN a taught rule covers a commit question THEN the decider proposes the rule's answer `decided`, quoting it [REQ: a-standing-delegation-is-decided-on-not-waited-for, scenario: a-taught-rule-covers-the-question]
- [x] AC-10: WHEN a checked taught rule backs "yes" to a go-live question THEN the answer is allowed despite the outward words [REQ: outward-and-irreversible-steps-are-never-answered-automatically, scenario: a-taught-rule-approves-an-outward-step]
- [x] AC-11: WHEN a permission prompt waits and a rule seems to cover it THEN it is still excluded [REQ: outward-and-irreversible-steps-are-never-answered-automatically, scenario: a-rule-does-not-open-a-permission-prompt]
