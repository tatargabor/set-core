## Context

The fleet's attention axis (`agent-input-attention`) tells a finished turn (`input`) from a session
stopped in front of a person (`prompt`). `prompt` came from two sources only: the runtime record's
`waiting` status (a permission prompt) and a log-measured open question tool (`asking`). An agent
that ends its turn with the family's `NEED INPUT:` hand-over line is stopped in front of a person
just the same, but both sources read it as `input`.

## Decisions

**Adopt the family's marker, not a heuristic.** The pattern is the one the consumer family's
keep-going hook already uses (`^[\s>*_`-]*(NEED INPUT|ALL DONE)\s*:`, case-insensitive, multiline),
extended only to accept `**NEED INPUT**:` (emphasis closed before the colon). A question mark at
the end of a turn, or words like "should I", were rejected: they fire on rhetorical questions and
on reports, which is the prose-read-as-fact class. The marker is a declaration the agent was told
to make, so reading it is reading a declaration, not guessing.

**Only the closing stretch of a finished turn.** The text after the last tool traffic, possibly
several text entries, and only when nothing is outstanding. A person's text after the marker
clears it. A marker before the last tool call belonged to an earlier stretch.

**Raise the class, keep the state.** `state` stays `quiet` (the log measurement); `attention`
becomes `prompt`, and only from `input` or `background` — a `busy` record means the loop moved past
the marker. Every consumer of `prompt` (tab warning, escalation) follows without change. The web's
question count (`askingNow`) and the jump-to-asker list read a new helper, `isAskingYou`, that
treats `asking` and `need_input` as the same fact.

**`all_done` is carried, not rendered.** A finished turn is already green; the field costs nothing
and lets a later surface separate "finished and said so" from "finished".

## Risks

- An agent that writes `NEED INPUT:` and then keeps working: the record turns `busy` and the class
  is not raised; the next finished turn re-reads its own closing text.
- The tail is bounded (256 KB). A closing message longer than the tail is not read — the class
  falls back to `input`, the pre-change behaviour, never to something louder.
