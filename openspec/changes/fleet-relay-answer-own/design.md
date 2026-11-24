## Context

The relay's answer store (`answers/<call id>__Q<n>.json`, `{"valasz": …}`) is the one
contract every answerer uses: the chat bridge, the fleet's single-question `deliver_answer`,
the send button, teach, and the decider's exclusive create. A carrier (the hook, a
continuation, a pulled-in question) waits for every key, then answers. So an own answer is a
write into that store; nothing downstream changes.

## Decisions

**D1 — A new route beside teach, not a teach mode.** `POST …/{call_id}/answer {answers: [..]}`.
Teach writes a rule and is refused for multi-question calls; an own answer must work for
any count and must not commit anything unless asked. "Also teach it" calls the existing teach
route instead, so the rule path stays one path.

**D2 — `deliver_answers` generalises `deliver_answer`.** It writes Q1..Qn after the same
checks (waiting, not released, count matches). `deliver_answer` becomes the one-text case of
it, so the send button and teach keep their behaviour.

**D3 — Nothing pre-filled.** The control exists for answering differently. Pre-filling the
proposal would make the easiest action the one the operator opened the control to avoid. The
options are one click away.

**D4 — Not for permission prompts.** A permission prompt has two fixed answers, already on
the channel and in the terminal. Free text there invites an answer the runtime cannot read.

## Risks / Trade-offs

- [A call the decider never saw has no text in the overlay] → the overlay says so and shows
  the count. The question is on the channel and in the terminal. The relay's waiting record
  holds no text by design.
- [The operator sends while the decider's countdown runs] → the answer file exists first, and
  the decider's exclusive create then fails, so it logs the call as overtaken, as it does for
  the chat bridge.
