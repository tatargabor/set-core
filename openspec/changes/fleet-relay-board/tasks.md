## 1. Board

- [x] 1.1 `web/src/lib/fleetRelayBoard.ts`: choices per question (options + an off-list proposal, the proposal and the recommended option marked), one-click rule, readiness of a several-question send, the verdict sentence with its reason
- [x] 1.2 `web/src/components/FleetRelayBoard.tsx`: the table; detail per waiting call on the panel's cadence; option click / free text / several-question send through `…/answer`; teach and to-terminal kept
- [x] 1.3 `FleetRelay.tsx`: the panel opens as the board (fixed, large, own close, Escape, outside click)
- [x] 1.4 Unit tests for 1.1; existing relay tests green; `tsc -b` clean; `pnpm build`
- [x] 1.5 Visual check in the browser on the running dashboard, with real waiting calls (ui-quality rule) — 2026-11-26 20:4x, localhost:7400/fleet: one real waiting continuation (itline-ai-plus); the board opened full-width under the header, the question in full with its line breaks, both suggestions as controls with the proposal marked "proposed", the free-text field, and the decider column reading "Proposed «…», not sure enough to write it (likely 0.60 below 0.80)". Escape closed it. Nothing was clicked: an option click would answer a real agent.

## 2. Teach on the row (owner, 2026-11-26: „teach is a táblázatos formátumban kellene nem külön képernyő")

- [x] 2.1 "teach it too" checkbox + optional condition on a single-question row when the server allows teach; the same option click / Enter posts to `…/teach`; the result (answered, commit sha or why not) is shown on the row
- [x] 2.2 The separate Details / Answer / Teach overlay (`FleetRelayCall.tsx`) is removed; its spec text (`fleet-relay-teach` relay-teach delta, `relay-own-answer`) rewritten for the board
- [x] 2.3 Visual check of the teach controls in the browser — 2026-11-26 ~21:05, localhost:7400/fleet, with NO live call waiting, so the page's `fetch` was stubbed in the tab for three made-up calls (a single question, a two-question call, a permission prompt); every POST to them was answered 409 by the stub, so nothing left the page. Seen: the teach checkbox and the condition field on the single-question row only, the proposal marked on the two-question row's option, "send all 2 answers" disabled until both picks, the permission row with no controls. With teach ticked, an option click posted `…/relay-fake-1/teach {"answer":"Előbb megnézem","explanation":""}` and the row showed the stub's refusal.

## 3. Note beside the option, teach on any question (owner, 2026-11-26: „itt első kérdésre akarnék teach-et és/vagy customot a választás mellé, de csak felülírni tudom")

- [x] 3.1 `composeAnswer`: pick + note → "<pick> — <note>"; picking no longer clears the note
- [x] 3.2 Teach per question on any non-permission call with a decider record; `POST …/answer` takes `teach: [{index, explanation}]`, delivers the answers, then `relay_teach.teach_rules` appends the ticked rules and commits them once; the single-call `/teach` route still refuses several questions
- [x] 3.3 Tests: 4 route tests (one-of-two taught, none taught, a bad index, `/teach` still refuses), 2 vitest; set-web restarted on it
- [x] 3.4 Browser, LIVE calls, every POST stubbed in the tab (409, nothing left the page): on the real three-question MyGLS call, Q1 picked «Nem tudom, kérdezd meg» with a note typed beside it, the pick stayed; "teach it too" on Q1 showed its condition field; Q2/Q3 kept their own teach boxes; "send all 3 answers" disabled until all three. One single-question row's option click reached the stub as `…/answer {"answers":[…],"teach":[]}`
- [ ] 3.5 A real per-question teach committed from the board (the owner's first use)

## Acceptance

- [ ] AC-4 (the click → `…/teach` request seen on a stubbed call, 2.3; a real commit from the board not yet): WHEN "teach it too" is ticked with a condition and an option is clicked THEN the agent is answered and the rule is committed in the project, and the row shows the sha [REQ: an-own-answer-can-also-be-taught, scenario: answer-and-teach]

- [ ] AC-1 (reading half seen live, see 1.5; the one-click SEND not exercised on a live call — it posts to the same `…/answer` route measured live in relay-own-answer M2): WHEN a single-question call waits THEN its question, options and the decider's reason are visible on opening, and one option click answers it [REQ: the-relay-panel-shows-every-waiting-question-in-full-and-answers-it-in-place, scenario: reading-and-answering-without-another-click]
- [ ] AC-2 (unit-tested: `readyToSend`; seen on a stubbed call, 2.3 — not on a live one): WHEN a three-question call waits THEN send is offered only after three choices [REQ: the-relay-panel-shows-every-waiting-question-in-full-and-answers-it-in-place, scenario: a-several-question-call]
- [ ] AC-3 (unit-tested: `answerable`; seen on a stubbed call, 2.3 — not on a live one): WHEN a permission prompt waits THEN its row has no answer control [REQ: the-relay-panel-shows-every-waiting-question-in-full-and-answers-it-in-place, scenario: a-permission-prompt]
