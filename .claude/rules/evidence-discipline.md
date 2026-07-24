# Evidence Discipline — what counts as knowing something

Written down on 2026-07-24 after a day in which the *same shape of defect* was found six
times, in six unrelated places, by two agents working independently. It is here because
that shape is not memorable on its own — each instance looked like a small local bug — and
because everything below was learned by measuring, then lost once already to a paraphrase.

**The rule underneath all of it: a claim and its evidence travel together, or the claim is
an assumption wearing a claim's clothes.** A word like *measured*, *verified*, *works*
obliges showing the command, the output, a `file:line`, a PID, a task id. Without one, the
honest word is "assumption" — and nothing built on it may be written into a rule book.

## The defect classes, because naming them is what makes them findable

**False value.** A field the system no longer stands behind is still emitted, and lands on
screen *next to* its replacement, contradicting it. Nobody notices, because both numbers
look like data. The fix belongs at the source — the producer declares what it has
deprecated — never at the display, and never as a hard-coded field name in a layer that is
supposed to be domain-free.

**False absence.** The mirror image, and the more dangerous one: the system announces that
something is hidden, missing, or suppressed — when it was never there. "1 deprecated field
hidden" about a field the producer stopped sending. A declaration is not data. **Count from
the data; use the declaration only to know what to look for.**

**Prose read as fact.** Any parser reading human or model prose will eventually read an
*example* as an instruction: a fenced code block parsed as a directive, a rule quoted before
a verdict read as the verdict, a `##` inside a fence ending a section. Anchor such parsers —
line start, not quoted, last occurrence wins, near the end of the output — and test them on
the shape that actually broke, not on the happy path.

**A proxy measured instead of the thing.** `ps -p <pid>` answers whether *a* process holds
that number, not whether *your* process is alive. Ask by identity, not by a number you
remember: `pgrep -af "<the thing it watches>"`. When a check is cheap and its subject is
specific, matching the subject is never harder than remembering the handle.

**A dead test looks exactly like a passing one, from far enough away.** Fifteen tests here
raised `TypeError` on a removed keyword argument *before reaching any assertion* — including
the one test written to guard against a quoted verdict being read as a verdict. Collection
counts and green suites do not distinguish "asserted and held" from "never got there".

## Fail direction outranks bug count

When a guard is wrong, ask which way it is wrong before asking how often. A gate that
guarded merges into `main` had six of seven behaviours wrong — and all six in the
**`pass`** direction. The count made it look like sloppiness; the direction made it a hole
that silently merged failing work. State the direction in the commit message; a reader
months later can re-derive the count and cannot re-derive the direction.

## How to prove a fix is a fix

**Stash it and rerun.** A test written alongside a fix that also passes without it proves
nothing, and looks like proof forever.

```bash
git stash && pytest tests/unit/<new-test>.py; git stash pop
```

Three of six tests written here passed either way. One of them passed only because the
fixture used an invalid enum value, so the bad input *was* parsed and a downstream validator
stopped it — the test was measuring the validator, not the parser. Without the stash, all
six would have been reported as proof.

The same discipline applies to a screen: structural counts (sections rendered, rows present,
zero JS errors) prove it *renders*. They say nothing about whether two fields contradict
each other — see [ui-quality](ui-quality.md). Look at it.

## Why this file exists rather than a memory

These findings crossed an agent channel and a context compact on the same day. Each hop is
lossy in one direction only: precision goes, confidence stays. A finding that arrives as
"we hardened the parsers" has lost the thing that made it useful — *which* shape broke it,
and which way it failed. **Write the shape into the repository while you still have it.**
