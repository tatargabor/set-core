## 1. Relay core (Layer 1, `lib/set_orch/fleet/question_relay.py`)

- [x] 1.1 `readiness()` — reads `question_relay.*` from local config, returns enabled, target, missing keys; one function for the hook and the API [REQ: an-incomplete-configuration-is-reported-never-completed-by-guess]
- [x] 1.2 `build_envelope(tool_input, session, project, label, answer_dir)` — one entry per question, structured options, configured audience [REQ: a-two-way-outbound-receives-an-envelope-and-the-answer-comes-back]
- [x] 1.3 Waiting records: write/remove/list/release-marker under the state dir, no question text [REQ: a-waiting-question-is-recorded-where-the-fleet-can-read-it]
- [x] 1.4 `collect_answers(id, keys, answer_dir)` and `answer_output(tool_input, answers)` [REQ: a-two-way-outbound-receives-an-envelope-and-the-answer-comes-back]
- [x] 1.5 `webhook_message(...)` minimal / full, and the post [REQ: a-webhook-outbound-notifies-and-releases]
- [x] 1.6 `relay(hook_input, ...)` — the whole decision loop with injectable clock/sleep/runner; every failure releases; logging without question text [REQ: every-failure-releases-the-question-to-the-terminal]

## 2. Hook and deploy

- [x] 2.1 `bin/set-hook-question-relay` — reads stdin, calls `relay`, prints the answer JSON or nothing; never exits non-zero [REQ: the-relay-is-off-by-default-and-off-changes-nothing]
- [x] 2.2 `bin/set-deploy-hooks`: PreToolUse matcher `AskUserQuestion`, timeout 3600, idempotent; `install.sh` links the hook if bin tools are listed there [REQ: the-hook-reaches-every-project]

## 3. API and fleet screen

- [x] 3.1 `GET /api/fleet/question-relay` (readiness + waiting), `POST /api/fleet/question-relay` (enable/disable, refused when not ready), `POST /api/fleet/question-relay/release/{session_id}` [REQ: the-fleet-header-carries-the-switch-and-what-is-waiting]
- [x] 3.2 `web/src/lib/fleetRelay.ts` + `web/src/components/FleetRelay.tsx`: switch, not-ready state naming missing keys, waiting count on the closed chip, floating list with "answer here instead" [REQ: the-fleet-header-carries-the-switch-and-what-is-waiting]
- [x] 3.3 Mount in `web/src/pages/Fleet.tsx` [REQ: the-fleet-header-carries-the-switch-and-what-is-waiting]

## 4. Tests

- [x] 4.1 `tests/unit/test_question_relay.py`: off, missing audience, envelope shape, answered, partial, outbound failure, switch off mid-wait, release marker, timeout, late answer ignored, waiting record without text, webhook minimal/full; mutation round [REQ: every-failure-releases-the-question-to-the-terminal]
- [x] 4.2 Deploy test: twice → one entry [REQ: the-hook-reaches-every-project]
- [x] 4.3 `web/tests/unit/fleetRelay.test.ts` [REQ: the-fleet-header-carries-the-switch-and-what-is-waiting]

## 5. Live verification

- [x] 5.1 Real interactive session in a scratch project with the hook deployed, the relay on, target `command` pointed at the real bridge in its dry-run mode replaced by a fake answer writer: answered end to end; then switch-off release and fleet release [REQ: a-two-way-outbound-receives-an-envelope-and-the-answer-comes-back]
- [x] 5.2 LOOK at the fleet header in Chrome: switch, not-ready title, waiting count, list, release [REQ: the-fleet-header-carries-the-switch-and-what-is-waiting]
- [x] 5.3 One real round trip through the real channel, with the user answering — only with the user's go-ahead [REQ: a-two-way-outbound-receives-an-envelope-and-the-answer-comes-back]

## Acceptance Criteria (from spec scenarios)

### The relay is off by default, and off changes nothing
- [x] AC-1: WHEN the switch is unset or false THEN the hook exits 0 with no output [REQ: the-relay-is-off-by-default-and-off-changes-nothing, scenario: switch-off]

### An incomplete configuration is reported, never completed by guess
- [x] AC-2: WHEN target command lacks an audience THEN the question is released and readiness names the key [REQ: an-incomplete-configuration-is-reported-never-completed-by-guess, scenario: audience-missing]

### A two-way outbound receives an envelope and the answer comes back
- [x] AC-3: WHEN every answer file arrives THEN the hook returns the answers [REQ: a-two-way-outbound-receives-an-envelope-and-the-answer-comes-back, scenario: answered-on-the-channel]
- [x] AC-4: WHEN only one of two answers arrived THEN the hook keeps waiting [REQ: a-two-way-outbound-receives-an-envelope-and-the-answer-comes-back, scenario: several-questions-in-one-call]

### Every failure releases the question to the terminal
- [x] AC-5: WHEN the outbound exits non-zero THEN the hook releases at once [REQ: every-failure-releases-the-question-to-the-terminal, scenario: outbound-fails]
- [x] AC-6: WHEN the switch is turned off while waiting THEN the hook releases [REQ: every-failure-releases-the-question-to-the-terminal, scenario: switch-turned-off-while-waiting]
- [x] AC-7: WHEN the fleet releases a waiting question THEN the hook releases [REQ: every-failure-releases-the-question-to-the-terminal, scenario: released-from-the-fleet]

### A waiting question is recorded where the fleet can read it
- [x] AC-8: WHEN a question is handed over THEN a waiting record without question text exists until answer or release [REQ: a-waiting-question-is-recorded-where-the-fleet-can-read-it, scenario: waiting-record-lifecycle]

### A webhook outbound notifies and releases
- [x] AC-9: WHEN target is webhook at default detail THEN the post carries project, agent and headers only and the question is released [REQ: a-webhook-outbound-notifies-and-releases, scenario: minimal-notice]

### The fleet header carries the switch and what is waiting
- [x] AC-10: WHEN the configuration is complete and the switch is turned on THEN enabled becomes true [REQ: the-fleet-header-carries-the-switch-and-what-is-waiting, scenario: turning-the-relay-on]
- [x] AC-11: WHEN a key is missing THEN the switch cannot be turned on and names it [REQ: the-fleet-header-carries-the-switch-and-what-is-waiting, scenario: not-ready]
- [x] AC-12: WHEN two questions wait THEN the closed header shows 2 [REQ: the-fleet-header-carries-the-switch-and-what-is-waiting, scenario: waiting-count]

### The hook reaches every project
- [x] AC-13: WHEN hooks are deployed twice THEN exactly one relay entry exists [REQ: the-hook-reaches-every-project, scenario: deploy-twice]

## Verification record (2026-10-11)

- `pytest tests/unit/test_question_relay.py` — 24 passed. Mutation round on the core: 12 mutants (any answer instead of all, switch-off ignored, release marker ignored, deadline ignored, a failing outbound treated as success, readiness never missing a key, options joined into a string, question text in the webhook notice, question text in the waiting record, timeout not capped, the off switch ignored, the waiting record never cleared) — all 12 caught, after one test was tightened: the timeout test asserted "released eventually" and let a deadline ×1000 pass; it now asserts "released on time".
- `vitest run tests/unit/fleetRelay.test.ts` — 10 passed; `tsc -b` clean.
- Deploy: two runs on a tree with its own PreToolUse hook → one relay entry (timeout 3600), the project's hook kept.
- **Live, in a real interactive session** in a scratch project with the hook deployed, the relay turned on by a real click on the fleet header, and a stand-in bridge that answers after 10 s:
  - answered on the channel — the agent received "Large (from the channel)" and continued with no picker;
  - **the first live run found a defect no unit test had**: the hook read the bridge's stderr through a pipe, and the bridge's background child held it, so the hand-off blocked until the child finished — "handed over" and "answered" logged in the same millisecond and the fleet never saw a waiting question. Fixed (no pipe held), with a regression test shown failing on the old code. Rerun: handed over :56, answered 12 s later, the header showed `⏳ 1` meanwhile;
  - "answer here instead" clicked in the fleet → the hook released, the picker appeared in the terminal;
  - switch turned off by a click while a question waited → released within one poll, picker appeared;
  - switch off → the picker appeared at once and the hook wrote nothing.
  - The relay log holds no question or answer text (grep: 0). The envelope the hook produced matches what the real bridge accepts in its dry-run mode (measured before the build).
- **A second defect, found by the existing suite:** the Fleet page's render tests mock `fetch` for the whole page; the new control rendered an answer without `waiting` and crashed the screen (187 failures). Both header widgets now parse their payload and degrade to "unreadable". The remaining 7 failures are in the flaky set that also fails on a clean HEAD (B-130, B-136).
- Looked at in Chrome: not-configured detail names the missing key and the `set-config` line; on/off states; waiting count; list; release.
- The machine's config was restored to exactly its previous keys after the live test; the relay is off and unconfigured on this machine.

**Open:** 5.3 — one real round trip through the real channel, with the user answering. And existing projects get the hook on their next `set-project init`; no tree other than the scratch one has it yet.

### 5.3 attempt, 2026-10-11 — the real channel, first round trip NOT yet completed

- Configured on this machine: target `command` → the bridge with `--csatorna-id` of a new text
  channel created for relay questions (the development channel the user picked is a FORUM,
  type 15, which cannot take plain posts); audience `FEJLESZTŐ`.
- Rolled the hook out with `set-deploy-hooks` (not a full `set-project init` — only the hooks
  changed): 53 trees committed (one pathspec commit each, `.claude/settings.json` only, the
  only change being the relay entry — checked per tree), 3 deployed and left uncommitted (2
  untracked settings files, 1 carrying another session's edit), subagent worktrees and `/tmp`
  trees skipped. Nothing pushed. Machine-local log outside set-core.
- Live: the hook handed the question over (exit 0), but the bridge's post had FAILED —
  "Missing Access": the new channel inherited a private category's permissions and the bot
  cannot see it (it cannot grant itself access either, 403). The bridge still exited 0, so
  the hook waited; released from the fleet after 35 s, picker appeared. Relay turned OFF.
- Waiting on: the user adding the bot to the channel; the bridge exiting non-zero when
  nothing was posted (requested from its owner on the bus). Then the round trip is retried.


### 5.3 done, 2026-10-11 — the round trip through the real channel

- After the user added the bot to the channel: the hook handed the question over, the bridge
  posted it (`1 kiment`), the user tapped the first option, the bridge's poller wrote the
  answer, and the agent continued with "Yes, it arrived" — no picker.
- **The hook held for 24 min 59 s and still delivered** — the measured hold time goes from
  700 s to ~1500 s; the 3600 s entry timeout is still unmeasured at its top.
- **Running sessions picked the hook up without a restart.** During the same window two real
  agents asked questions and got Discord answers: one session started 2026-10-09, the other
  started ~2 h before the rollout commit. Adding the hook to `.claude/settings.json` reached
  sessions that were already running.
- Still open on the bridge side (reported on the bus, not a set-core task): exit non-zero when
  nothing was posted. Until it does, a Discord outage holds a question until it is released
  from the fleet or times out.
