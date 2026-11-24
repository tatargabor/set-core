## 1. Core and route

- [x] 1.1 `question_relay.deliver_answers(session_id, texts)`: refuse when not waiting, released, a permission prompt, or a count mismatch; write Q1..Qn; `deliver_answer` delegates to it. Tests. [REQ: an-own-answer-is-the-operator-s-answer-delivered-at-once]
- [x] 1.2 `POST /api/fleet/question-relay/{call_id}/answer {answers}` in `api/fleet_relay_teach.py`: 404 when not waiting, 409 with the reason otherwise; logs carry the id and the count. Route tests. [REQ: an-own-answer-is-the-operator-s-answer-delivered-at-once]

## 2. The panel

- [x] 2.1 `answer…` on every non-permission row with an id; `FleetRelayCall` mode `answer`: one empty field per question (count from the waiting record), question text and options from the decider's record when present, options fill their field, send disabled while any field is empty. [REQ: the-operator-can-answer-a-waiting-call-in-their-own-words]
- [x] 2.2 "also teach it for next time" (single question, teach allowed) with the condition field; sending then calls the teach route. [REQ: an-own-answer-can-also-be-taught]
- [x] 2.3 Pure helpers in `fleetRelayTeach.ts` (field count, can-send, request body) with unit tests; `tsc -b`, the web suite, `pnpm build`. [REQ: the-operator-can-answer-a-waiting-call-in-their-own-words]
- [x] 2.4 Visual check in the browser on the running dashboard: open answer… on a waiting row, fill a field from an option, type a field, check nothing under the overlay moves. Send only on a scratch call. Say what is seen. [REQ: the-operator-can-answer-a-waiting-call-in-their-own-words]

## 3. Live

- [x] 3.1 A scratch agent's question (isolated relay world as in fleet-relay-backfill M5, or a scratch relay record): answered through the route with free text; the agent receives that text. Record it in `measurements.md`. [REQ: an-own-answer-is-the-operator-s-answer-delivered-at-once]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the operator answers differently from the proposal THEN the agent receives that text and the log records it as the operator's answer [REQ: the-operator-can-answer-a-waiting-call-in-their-own-words, scenario: answering-differently-from-the-proposal]
- [x] AC-2: WHEN a two-question call gets both fields THEN both answers arrive in order and the call stops waiting [REQ: the-operator-can-answer-a-waiting-call-in-their-own-words, scenario: a-call-with-two-questions]
- [x] AC-3: WHEN a field is empty THEN send is unavailable and nothing is written [REQ: the-operator-can-answer-a-waiting-call-in-their-own-words, scenario: a-field-left-empty]
- [x] AC-4: WHEN the call ended before send THEN nothing is written and the overlay says so [REQ: an-own-answer-is-the-operator-s-answer-delivered-at-once, scenario: the-call-ended-before-send]
- [x] AC-5: WHEN the call is a permission prompt THEN no answer… control and the route refuses [REQ: an-own-answer-is-the-operator-s-answer-delivered-at-once, scenario: a-permission-prompt]
- [ ] AC-6: WHEN the operator answers, ticks also-teach and adds a condition THEN the agent gets the answer and the rules file gains the entry [REQ: an-own-answer-can-also-be-taught, scenario: answer-and-teach] — OPEN: the UI branch posts to the teach route, whose answer+rule path is tested (fleet-relay-teach M2, AC-3), but this overlay's "also teach it" was not exercised live
