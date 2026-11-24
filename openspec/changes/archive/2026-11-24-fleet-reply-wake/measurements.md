# fleet-reply-wake — measurements

## M1 — the first round after deploy (2026-11-24 14:43:19, set-web on `5418e7a2`)

The store held 28 answered engagements and none had a wake outcome. One round recorded 26
`too-old` (older than the then 2 h), the 34-minute-old one `gone` (its asking session no longer
live), and one scratch record `operator-present` (M2). Nothing was typed into a real agent.

## M2 — live wake on a scratch fleet agent (task 2.1)

A scratch fleet agent (`scratch-wake`, haiku, hooks off) said READY and went idle. A fabricated
engagement (asker `set-core#<its session prefix>`, room `scratch-reply-wake-test`, answered
"now") was written into the real store, and the real takeover loop decided it:

- 14:43:19 — `operator-present`: the agent's start prompt counts as human input and was 70 s
  old (< 120 s). The guard is right, and the case is the test's own: a fleet-started agent's
  first two minutes count as "someone is at it".
- A second record, 2.5 min after start — 14:45:22 `fleet reply wake: … woke scratch-wake`,
  `asker wake: woken`. The transcript: the typed `[fleet] Your request in bus room
  scratch-reply-wake-test at … was answered (reply at …). Read the reply on the bus and continue
  your thread.` → `assistant: WOKEN`. The next rounds typed nothing more.

The two scratch records stay in the store as `answered` (pruned after 30 days). After the
owner's remark the window became 20 min (*„too-old igen ezek régiek 34 percesek"*).
