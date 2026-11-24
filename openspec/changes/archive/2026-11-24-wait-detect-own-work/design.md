## Context

`wait_detect.decide` blocks a stop only on WAITING; `continuation.py` acts only on a DONE verdict
record. The two-word prompt forced a background wait into one of the two, and haiku split it
between them run to run.

## Decisions

**D1 — a third word instead of a sharper sentence.** First tried: one more sentence in the
DONE paragraph ("a message whose next step waits only for the agent's own background work is
DONE"). Measured on the same 8 messages: no better. The real message flipped to WAITING, and
two background waits stayed WAITING. A category the model can name was measured 24/24 with 3
samples each, so the model gets a word for the case rather than an exception to remember.

**D2 — SELF is its own verdict, not mapped to DONE.** A DONE record makes the continuation
carrier ask the decider "what next?" and possibly post it. A turn that waits on its own work
will be woken by that work, so a continuation would be a second, competing next step. Keeping
SELF distinct makes both consumers do nothing for it without touching the carrier.

**D3 — mixed messages are WAITING.** If the turn waits on its own work and also needs an
answer from the user, the user question is what would be lost; the rule says so in the prompt.

## Risks

- A model still mislabels: the fail direction stays toward today (a missed wait ends the turn
  as before; a spurious WAITING costs one needless question).
