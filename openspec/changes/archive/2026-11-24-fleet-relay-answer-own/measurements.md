# fleet-relay-answer-own — measurements

## M1 — the overlay in the browser, on the running dashboard (task 2.4)

Claude in Chrome against `localhost:7400/fleet`, 2026-11-24 14:2x, after `pnpm build`.

- Every waiting non-permission row shows `details · answer… · teach · to terminal ↩` (teach
  only where the call has one question); `answer…` is amber, beside the others, and the row
  height did not change.
- On a real two-question call (opened, never sent): "Your answer" overlay with each
  question's text, the decider's proposal per question ("proposed «…» — write what you want
  instead"), the options as fills and an EMPTY field per question. `send my answer` stayed
  disabled with both fields empty, and still disabled after an option click filled field 1
  only (the option highlighted, the field held its label). The overlay floated over the
  panel; nothing under it moved. Closed with its own ×, nothing sent.
- First send on the scratch call returned `Not sent: Method Not Allowed`: the service still
  ran the code from before the route (a running service holds the code it started with).
  The failure line stayed open, as the rule requires. After `systemctl --user restart set-web`
  the send succeeded.

## M2 — a free-text answer reaches a real agent (task 3.1)

A scratch fleet agent (haiku, only the question hook wired, its relay config OFF so the hook
parked it) asked one `AskUserQuestion`; the fleet-relay-backfill path pulled it into the live
relay with no outbound (nothing posted to the channel). On the panel the row read
"set-core · scratch-ownanswer question"; `answer…` showed "The decider has no record of this
call, so its text is not shown here — read it on the channel." and one field.

Typed "Not yet: ship it only after the colour review", pressed `send my answer`. 14:30:42
relay log: "answered on the channel; typed into scratch-ownanswer". The agent's transcript:
`tool_result is_error` → `[Request interrupted…]` → the typed line with `Q1 “Scratch”: Not yet:
ship it only after the colour review` → `assistant: GOT: Not yet: ship it only after the colour
review — continue with this answer.`

One more measurement on the way: the first pull-in's waiting record was removed within a
second by an auto-answer worker started at 13:46 on the code from before the backfill carrier
existed ("has no live hook"). It is the B-192 shape. In production the carrier's job path
lies under the relay's state dir (`…/question-relay/backfill/…`), which the old marks
accept. The test was re-run from a path carrying that mark.

## M3 — an own answer that is also taught, live (AC-6)

Built the same way as fleet-relay-teach M2. A scratch git repository was created in a scratchpad.
A waiting call and a decider record for it were placed in the live relay state, with a stand-in
`set-hook-…` process holding the call live. The proposal on record was «Igen, küldd
(Recommended)», excluded as `outward step: send`.

Steps, in Chrome on `localhost:7400/fleet` at 14:54:
- Opened `answer…` on that row.
- Typed the own answer "Nem, csak pénteken küldd".
- Ticked "also teach it for next time (a project rule, committed there)". This opened a
  "When / why (optional)" field, and the button changed from `send my answer` to
  `send + teach`.
- Typed the condition and pressed `send + teach`.

Results:
- Overlay: "Answered — the agent has it. Rule committed in teachown-proj (main) as 7f9658f —
  .claude/rules/auto-answer-taught.md. Not pushed."
- `git show --stat HEAD`: one file, `.claude/rules/auto-answer-taught.md`, +14, message
  `auto-answer: taught rule 2026-11-24`. The entry is verbatim: the question, the OWN answer
  (not the proposal), the `When / why` line and the date.
- The relay's answer file held `{"valasz": "Nem, csak pénteken küldd"}`.
- set-web journal: `1 answer(s) handed over from the fleet`, then `relay teach … answered=True
  written=True commit=7f9658f`, with no rule text.

The fake records were removed afterwards and the stand-in process was stopped.
