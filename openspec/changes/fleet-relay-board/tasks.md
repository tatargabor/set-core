## 1. Board

- [x] 1.1 `web/src/lib/fleetRelayBoard.ts`: choices per question (options + an off-list proposal, the proposal and the recommended option marked), one-click rule, readiness of a several-question send, the verdict sentence with its reason
- [x] 1.2 `web/src/components/FleetRelayBoard.tsx`: the table; detail per waiting call on the panel's cadence; option click / free text / several-question send through `…/answer`; teach and to-terminal kept
- [x] 1.3 `FleetRelay.tsx`: the panel opens as the board (fixed, large, own close, Escape, outside click)
- [x] 1.4 Unit tests for 1.1; existing relay tests green; `tsc -b` clean; `pnpm build`
- [x] 1.5 Visual check in the browser on the running dashboard, with real waiting calls (ui-quality rule) — 2026-11-26 20:4x, localhost:7400/fleet: one real waiting continuation (itline-ai-plus); the board opened full-width under the header, the question in full with its line breaks, both suggestions as controls with the proposal marked "proposed", the free-text field, and the decider column reading "Proposed «…», not sure enough to write it (likely 0.60 below 0.80)". Escape closed it. Nothing was clicked: an option click would answer a real agent.

## Acceptance

- [ ] AC-1 (reading half seen live, see 1.5; the one-click SEND not exercised on a live call — it posts to the same `…/answer` route measured live in relay-own-answer M2): WHEN a single-question call waits THEN its question, options and the decider's reason are visible on opening, and one option click answers it [REQ: the-relay-panel-shows-every-waiting-question-in-full-and-answers-it-in-place, scenario: reading-and-answering-without-another-click]
- [ ] AC-2 (unit-tested: `readyToSend`; no several-question call was waiting to look at): WHEN a three-question call waits THEN send is offered only after three choices [REQ: the-relay-panel-shows-every-waiting-question-in-full-and-answers-it-in-place, scenario: a-several-question-call]
- [ ] AC-3 (unit-tested: `answerable`; no permission prompt was waiting): WHEN a permission prompt waits THEN its row has no answer control [REQ: the-relay-panel-shows-every-waiting-question-in-full-and-answers-it-in-place, scenario: a-permission-prompt]
