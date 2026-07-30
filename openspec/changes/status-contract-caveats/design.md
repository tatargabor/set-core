## Context

The status envelope already separates three kinds of "do not trust this at face value", and each
one was added because the alternative had been measured to fail:

| signal | granularity | what it says |
|---|---|---|
| `gaps` | per command | the answer is missing |
| `errorClass` | per failure | the answer did not arrive, and why |
| `deprecated` | per field name | the field is present but nobody stands behind it |

All three describe something **absent or wrong**. The case this change covers is none of them:
the command succeeds, the field is present, and **the value is right** — the reading is simply
wider than the fact. A count of "not tracked" describes the producer's own register, not the
world; a "tracked" count is a lower bound because one of its inputs is written by hand.

The shape was negotiated with a consumer over four rounds. Both sides had reasons that only the
other side could supply, so the decisions below record the *arguments*, not just the outcomes —
a decision whose reason is lost gets re-opened by the next reader on worse evidence.

## Goals / Non-Goals

**Goals:**

- A producer can attach a caveat to a value **and to a whole command**, in one sentence each.
- The framework carries it and never interprets it.
- The caveat is impossible to read *without* the number it qualifies.
- A forgotten or mistyped caveat costs the narrow half, never the general one.

**Non-Goals:**

- **Any framework-side key name.** The framework must work identically for a producer whose keys
  are `TRACKED`/`SUSPECT` and one whose keys are anything else.
- **Any judgement about a caveat's text.** Whether a sentence explains anything is not
  mechanically decidable — two proxies for that were tried elsewhere in this repo and both
  misclassified, in opposite directions.
- **A gate.** See D4.
- **A replacement semantics.** See D2.

## Decisions

**D1 — The producer writes the caveat; the framework holds none.** Identical to `deprecated`, and
for the identical reason: the caveat is domain. "This number describes our register, not the
world" is a sentence only the producer can write, and a framework-supplied one would be right for
whoever it was written against and quietly wrong for everyone else while looking authoritative to
both.

**D2 — Per-field keys ADD to `"*"`; they never override it.** The consumer's first proposal had
them overriding, and their own example did not survive it: `"*"` said *every number here describes
our register*, and the per-field sentence said *known lower bound*. Under overriding, a reader of
that field loses the register caveat — **the more general and more important of the two**.

The deciding argument is direction, not elegance. Forget a per-field entry under additive and the
general caveat still stands (safe); override, and the narrower sentence silently swallows the
broader one (quiet loss). The consumer withdrew the overriding rule in one line, reaching for the
same direction-argument they use elsewhere — an absent `type` means the more serious value, a NULL
channel means *never send*.

**No explicit-replacement marker either.** If replacement is ever genuinely needed it gets its own
named field. Making it the default's semantics is how a mechanism acquires a second meaning that
nobody can see at the call site.

**D3 — The count comes from the data; the declaration only says what to look for.** Inherited
verbatim from `presentDeprecations`, which exists because the opposite produced *"1 deprecated
field hidden"* about a field that was never sent. A declaration is a claim about the data, and a
claim can be wrong.

**D4 — A declared key that is absent from the answer is DIAGNOSTICS, not a gate.** The framework
cannot tell a typo from a legitimate absence, and it must not pretend to: a producer's per-status
breakdown may legitimately list only the statuses currently present, so a caveat keyed on a status
that is currently zero is *correct* and absent. A gate firing daily on that is dead within a week
and takes the real warning with it.

What the framework CAN do is list which declared keys are missing from this answer, where the
producer recognises a legitimate absence at a glance and a typo just as fast. The decision stays
with the producer; the framework only makes it visible.

**D5 — A mistyped key fails in the direction this feature exists to prevent, and the additive
choice already absorbs most of it.** Measured on this side: the renderer counts only names it
found, and nothing logs a declared-but-absent name. For `deprecated` that silence is deliberate —
counting from the declaration is the false absence D3 forbids. For `caveats` the direction
inverts: a mistyped `deprecated` key leaves a stale field *visible* (unpleasant, visible), while a
mistyped `caveats` key leaves the caveat *invisible* and the number visible — exactly the outcome
the feature exists to stop.

Additive (D2) absorbs most of it without anyone having designed that: with a mistyped per-field
key the `"*"` still renders, so the number carries the general caveat and only the narrow half is
lost. **The direction argument paid twice** — once for a forgotten entry, once for a typo. D4's
listing covers the rest.

**D6 — Placement is part of the contract, not a UI preference.** The caveat renders **beside the
number**, and the `"*"` once in the section header. Never a tooltip, never another tab.

This is the whole point of the mechanism rather than a nicety: the defect being fixed is that *the
number travels and the caveat does not*. A caveat one interaction away has not been carried — it
has been filed. It is also the repo's own layout rule: anything hidden that changes how a value
should be read must be marked where the reader is standing.

**D7 — A caveat is not an alarm, and the framework must not infer that it is.** One visual weight
per meaning: if red means broken, a caveat is not red. A caveat says *this correct number means
something narrower*, which is neither a failure nor a warning — and a producer's field whose name
sounds alarming ("expired", "suspect") is still not an alarm unless the producer says so. The
framework never derives severity from a name; it has no names.

## Risks / Trade-offs

- **Two caveats beside one number is visual clutter** → accepted, and it is the cheaper failure.
  The alternative is dropping one, and D2 shows which one gets dropped in practice: the general
  one, which is the one more likely to matter.
- **A producer could write a caveat on every field** → their call, and self-limiting: a caveat
  next to every number reads as noise and the producer sees that on their own screen. The
  framework does not ration sentences it cannot read.
- **A per-field caveat on a field the producer stopped sending** → handled by D3: nothing is
  printed, because the count comes from the data. D4's list is where the producer notices.
- **The diagnostics list could itself become noise** → it is a list, on request, not a banner. If
  it ever acquires a badge or a count on the main surface it has become the gate D4 refuses.
