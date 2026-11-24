## 1. Finding and carrying open questions (core, `lib/set_orch/fleet/relay_backfill.py`)

- [x] 1.1 `open_questions(...)`: fleet-held sessions (owner `list_agents` → session record → transcript) with an open `AskUserQuestion` (`tool_use` without `tool_result`, sidechains skipped) and no relay waiting record; plus the open ones in sessions the fleet does not hold, as `not-fleet-held`. Unit tests on real-shaped transcripts. [REQ: turning-a-switch-on-pulls-in-the-questions-already-open]
- [x] 1.2 `hand_over(question)`: the hook's envelope (`build_envelope` on the call's own input, `call_id(session_id, tool_use_id)`), the relay outbound with kind `ask`, then the waiting record with `backfill`, `tool_use_id`, `label` and the carrier's pid. A failed outbound hands nothing over and says why. [REQ: turning-a-switch-on-pulls-in-the-questions-already-open]
- [x] 1.3 `carry(record)`: poll for every answer; stop with no typing on release marker, switch off, timeout, record replaced, label gone, or the call resolved in the transcript; re-check after the answers arrive; remove the record, then Esc / line / Enter through the owner daemon. The line names each question by header (or first 60 chars) and its answer. Logs carry the short session id and the reason only. [REQ: a-pulled-in-answer-reaches-the-agent-through-its-terminal]
- [x] 1.4 `pull_in(trigger)`: one carrier per question (D2: `systemd-run --user --collect` when available, else a detached process), at most one per session; returns `{pulled, not_fleet_held, skipped}` with project + short id per entry. Does nothing while the relay is off. [REQ: what-cannot-be-pulled-in-is-named-not-hidden]
- [x] 1.5 `bin/set-relay-backfill`: by hand it prints the report; `--carry` is the carrier entry. [REQ: the-pull-in-can-be-run-by-hand]

- [x] 1.6 The hook parks every question it lets go to the terminal (`question_relay.park`; the bin's own off path too), mode 600, removed when pulled in, when the session's next question is relayed, when the session ended or the call has a result, and after 24 h. `open_questions` reads parked records first, the transcript second; `call_is_open` reads results only (M3). Tests; three mutations caught. [REQ: a-question-left-to-the-terminal-is-parked-for-the-next-switch-on]

## 2. The decider's decide-only mode (core, `auto_answer_worker.py`)

- [x] 2.1 `SET_RELAY_NO_FORWARD=1`: no forward, no release when nothing is allowed, a window write and the log as usual. Tests: an allowed answer is written after the window with no forward call; an excluded one is neither forwarded nor released. [REQ: a-question-already-on-the-channel-can-be-decided-without-a-second-post]
- [x] 2.2 `undecided_waiting()` in `relay_backfill.py`: relay waiting records of kind `ask` with no pending decider record, the envelope rebuilt from the transcript call whose `call_id` matches; one decide-only worker each. [REQ: a-question-already-on-the-channel-can-be-decided-without-a-second-post]

## 3. The switches (`lib/set_orch/api/fleet.py`)

- [x] 3.1 Relay toggle → on: `pull_in("relay-on")`, the report in the response under `backfill`. Auto-answer toggle → on with the relay on: the terminal pull-in plus the decide-only workers; the report in the response. A pull-in failure is logged and reported and never fails the toggle. [REQ: turning-a-switch-on-pulls-in-the-questions-already-open]

## 4. Live

- [x] 4.1 Measure Esc on an open question dialog in a scratch fleet agent: after Esc + line + Enter, the transcript shows the call closed and the next user turn carrying the line. Record it in `measurements.md`. [REQ: a-pulled-in-answer-reaches-the-agent-through-its-terminal]
- [ ] 4.2 The real case: with the relay off, a scratch fleet agent asks; turn the relay on from the fleet; the question appears in the waiting list; answer it on the panel; the agent continues with the answer. Record it. [REQ: turning-a-switch-on-pulls-in-the-questions-already-open]
- [x] 4.3 Capability guide line: switching the relay on pulls in open questions; `set-relay-backfill` by hand. [REQ: the-pull-in-can-be-run-by-hand]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN an agent asked while the relay was off and the switch is turned on THEN the question is handed over, appears in the waiting list, and reaches the decider when automatic answers are on [REQ: turning-a-switch-on-pulls-in-the-questions-already-open, scenario: a-question-was-asked-while-the-relay-was-off]
- [x] AC-2: WHEN nothing is open THEN nothing is handed over and the response reports zero [REQ: turning-a-switch-on-pulls-in-the-questions-already-open, scenario: nothing-is-open]
- [x] AC-3: WHEN the relay already holds the question THEN it is not handed over twice [REQ: turning-a-switch-on-pulls-in-the-questions-already-open, scenario: the-relay-already-holds-the-question]
- [x] AC-13: WHEN an agent asks while the relay is off THEN the hook parks it and a later switch-on pulls it in although the transcript does not hold the call [REQ: a-question-left-to-the-terminal-is-parked-for-the-next-switch-on, scenario: asked-while-the-relay-is-off]
- [x] AC-14: WHEN a parked question's session has ended THEN it is not pulled in and its record is removed [REQ: a-question-left-to-the-terminal-is-parked-for-the-next-switch-on, scenario: the-session-has-ended]
- [x] AC-4: WHEN the operator answers on the channel THEN the terminal receives Esc, one line, Enter, and the record is gone [REQ: a-pulled-in-answer-reaches-the-agent-through-its-terminal, scenario: the-operator-answers-on-the-channel]
- [ ] AC-5: WHEN the decider writes an allowed answer THEN the agent receives it the same way and the log says written [REQ: a-pulled-in-answer-reaches-the-agent-through-its-terminal, scenario: the-decider-answers]
- [x] AC-6: WHEN the question is answered in the terminal first THEN nothing is typed and the record is removed [REQ: a-pulled-in-answer-reaches-the-agent-through-its-terminal, scenario: answered-in-the-terminal-first]
- [x] AC-7: WHEN "to terminal" is pressed on a pulled-in question THEN the carrier ends and nothing is typed [REQ: a-pulled-in-question-ends-like-a-relayed-one, scenario: handed-back-to-the-terminal]
- [x] AC-8: WHEN the relay switch goes off again THEN the carrier ends and nothing is typed [REQ: a-pulled-in-question-ends-like-a-relayed-one, scenario: the-switch-goes-off-again]
- [x] AC-9: WHEN a session outside the fleet has an open question THEN it is listed as not fleet-held and not handed over [REQ: what-cannot-be-pulled-in-is-named-not-hidden, scenario: a-question-in-a-plain-terminal]
- [x] AC-10: WHEN `set-relay-backfill` runs with the relay off THEN it hands nothing over and says so [REQ: the-pull-in-can-be-run-by-hand, scenario: run-while-the-relay-is-off]
- [x] AC-11: WHEN automatic answers are turned on over a waiting question THEN it is decided, nothing is re-posted, and an allowed answer is written after the window [REQ: a-question-already-on-the-channel-can-be-decided-without-a-second-post, scenario: automatic-answers-turned-on-over-a-waiting-question]
- [x] AC-12: WHEN such a question cannot be answered THEN it keeps waiting and is not released [REQ: a-question-already-on-the-channel-can-be-decided-without-a-second-post, scenario: the-decider-cannot-answer-it]
