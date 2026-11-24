## Why

The relay panel lets the operator send the decider's proposal with one click, teach it, or
hand the question back to the terminal. It has no way to answer something DIFFERENT from
the proposal without being at the agent's terminal. The owner asked for it on 2026-11-24,
from a screenshot of a row reading `auto: not written — outward step: send; it proposed
«Igen, draftold (Recommended)»` with only `details` and `to terminal ↩` on it: *„kell egy
mégis eltérek a választól gomb … lehet inkább azt mondom nem kell … email, vegyük ki hogy
minden beszélgetés után küldjön, de azt be kell tudnom írni valahova"*.

## What Changes

- Each waiting question or continuation row gets an **answer…** control. It opens an
  overlay with one field per question, free text, the question's options as one-click fills,
  and nothing pre-filled: this is for answering differently from the proposal.
- Sending it answers the call at once as the operator's answer, through the relay's answer
  store, for a call with any number of questions.
- When the call has one question and teach is allowed, an optional "also teach it" adds the
  answer as a project rule, using the existing teach path.
- A permission prompt gets no answer… control.

## Capabilities

### New Capabilities
- `relay-own-answer`: the operator's own free-text answer to a waiting relay call, from the
  fleet panel.

### Modified Capabilities
(none)

## Impact

- `lib/set_orch/fleet/question_relay.py`: `deliver_answers(session_id, texts)` for any
  question count (`deliver_answer` stays the single-question form).
- `lib/set_orch/api/fleet_relay_teach.py`: `POST /api/fleet/question-relay/{call_id}/answer`.
- `web/src/components/FleetRelay.tsx`, `FleetRelayCall.tsx`, `web/src/lib/fleetRelayTeach.ts`.
