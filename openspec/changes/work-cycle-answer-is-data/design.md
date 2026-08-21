## Context

`prompt.build_unit_prompt` renders answered questions into the unit prompt as
`- **{task}**: {answer}` under *"They are decided now — act on them rather than asking
again."* The prompt is passed to a full session with the project's hooks and permission mode.
The text is a person's, arriving through a file anyone on the machine may write — and, once
`work-cycle-question-outbound` lands, through whoever can post in a chat channel.

## Goals / Non-Goals

**Goals:** an answer decides its own question and cannot become new work; an answer's size and
validity are bounded at the boundary; no free-text field of the document reaches a log raw.

**Non-Goals:** authenticating who answered — a chat channel's membership is the outbound's
concern, and an authenticated author can still write a bad answer, so the bound must hold
either way. Nothing here changes delivery, matching or application.

## Decisions

### D1 — Delimit and label, rather than sanitise the text

The answer is rendered inside an explicit delimiter, labelled as the decision on a named
question. Stripping or escaping "dangerous" words is the alternative, and it is worse on both
counts: it mangles legitimate answers (a person answering *"run the migration first"* means
it), and it cannot enumerate what is dangerous to a language model. Structure is checkable;
a blocklist is a guess that looks like a defence.

### D2 — The bound refuses rather than truncates

A truncated answer is a text no person wrote, applied as though they had. Refusing leaves the
question awaiting, which is the state the mechanism already knows how to report.

### D3 — Closed choices are enforced where they were offered, and today there are none

If the question offered a closed set, an answer outside it is a mismatch, not a subtlety —
the cheapest possible check against an answer that did not come from the person the question
was put to.

⚠ **It is inert today, and saying so is the point.** Measured: `OpenDecision` carries `task`
and `question` only; the awaiting marker records the question text alone; nothing in this
engine holds an option list. The structured list arrives with
`work-cycle-question-outbound`, which is gated on this change — so the control cannot fire
until then, and a green test for it proves the code path, not a live defence. An earlier
draft claimed the options were "already in the envelope and in the awaiting record", which
was a plan describing itself as if it had shipped.

### D4 — Enumerate the document's free-text fields

`source` reaches a log line verbatim today while being sanitised for the filename: the rule
said "the question and the answer", and `source` is neither. So the rule becomes an
enumeration of the document's fields, and a new field is covered by being enumerated rather
than by omission.

## Risks / Trade-offs

- **A legitimate long answer is refused** → the bound is generous and the refusal names the
  length received, so a person can see what happened and say it shorter.
- **Delimiting is not a security boundary against a determined author** → correct, and it is
  not claimed to be. It is a structural statement of what the text is, which is what makes
  a later check about *what the unit was told to do* possible at all.
- **The option check needs the question's options at answer time, and nothing carries them
  yet** → until `work-cycle-question-outbound` lands, every question is free text and this
  control does nothing. The fallback is honest, but it must be *reported* as inert rather than
  silently taken for a defence — otherwise the change ships three controls and enforces two.

## Open Questions

- What the length bound should be. It should be measured against the longest legitimate
  answer on record rather than chosen, and no such measurement exists yet.
