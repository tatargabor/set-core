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
