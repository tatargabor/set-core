## Why

The owner, 2026-11-26, from a screenshot of the relay panel with four waiting calls each shown
as one truncated line (`auto: no decision — the sources do not settle it`) and a `details`
link: *„vszeg egyből kellene mutatni egy nagy ablakban táblázatban hogy ne kelljen kattintani
tudjak dönteni és jól olvasható legyen"*. Deciding a call today takes three steps per row —
open details, read, go back, open answer — and the reason the decider gave is hidden behind
a tooltip.

## What Changes

- Opening the relay panel shows a large floating board: one table row per waiting question,
  with the agent, the question in full, its options as buttons, and the decider's verdict
  with its reason and proposed answer — all visible without another click.
- One click on an option of a single-question call answers it as the operator's own answer
  (the existing own-answer route). A several-question call is answered when each question
  has a pick. A free-text field per question answers in the operator's own words.
- The decider's proposal is marked on its option (or shown as an extra choice when it is not
  one of the options, as a continuation's free text can be).
- `teach` and `to terminal ↩` stay on each row; a permission prompt shows no answer controls.
- A call the decider has no record of says its text is only on the channel or terminal.

## Capabilities

### Modified Capabilities

- `relay-own-answer`: the panel shows every waiting question in full and answers it in place.

## Impact

`web/src/components/FleetRelay.tsx`, new `web/src/components/FleetRelayBoard.tsx` and
`web/src/lib/fleetRelayBoard.ts`; no server change (reads `…/detail`, posts `…/answer`).
