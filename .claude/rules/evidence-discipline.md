# Evidence Discipline — what counts as knowing something

Written down on 2026-07-24 after a day in which the *same shape of defect* was found six
times, in six unrelated places, by two agents working independently. It is here because
that shape is not memorable on its own — each instance looked like a small local bug — and
because everything below was learned by measuring, then lost once already to a paraphrase.

**The rule underneath all of it: a claim and its evidence travel together, or the claim is
an assumption wearing a claim's clothes.** A word like *measured*, *verified*, *works*
obliges showing the command, the output, a `file:line`, a PID, a task id. Without one, the
honest word is "assumption" — and nothing built on it may be written into a rule book.

## The defect classes — the NAMES, so you can recognise one

Each line is a class this repo has actually paid for. **The measurement behind each one, the
direction it failed in, and the check that catches it are in the `evidence-discipline`
skill** — load it when a measurement surprises you, when a green result feels too
reassuring, or when you are about to write a test meant to prove something.

- **False value** — a field the system no longer stands behind is still emitted, next to its replacement.
- **False absence** — the system announces something is hidden or suppressed that was never there.
- **Prose read as fact** — a parser reads an example, a quote, or a fenced block as a verdict.
- **A proxy measured instead of the thing** — `ps -p <pid>` for "is my process alive"; `cd` into a worktree for "I ran its code".
- **The measurement is inside the corpus it measures** — `pgrep -af` matches itself; a grep matches the file doing the grepping. It OVER-reports.
- **The instrument hits the wall it was built to measure and reports a zero** — an exhausted resource and an efficient one look identical from inside the test.
- **Two agents generalise from the runtime each can see** — a conclusion that crosses to the other side's environment must be measured THERE.
- **A filter downstream of a source undoes it** — and looks exactly like a source that returned nothing.
- **A reproducer is a measurement with a timestamp** — a symptom that stops appearing is not a repair; assert the CAUSE.
- **The harness's own cleanup answers before the code under test does** — assert at the moment the code finishes, not after teardown.
- **A dead test looks exactly like a passing one** — a test that raises before its first assertion still counts as collected.
- **A pattern is blind to negation** — anchor the WHOLE line; a substring test wearing an anchor is still a substring test.
- **The name is a second place, and it is the copy people actually read** — a name claiming more than the tasks deliver reads later as "that part is done".
- **A marker outranks the body** — and a marker true of a NARROWER subject still lies, because the marker is what gets counted.
- **Record the pattern that was WRONG, not only the number that is right** — better still, hold the wrong pattern in a test.
- **A zero with an empty breakdown is a shape error** until the input's shape has been inspected.
- **A subagent's "done" is not evidence** — measure the trace (a file, a commit, a log line). And an instruction is not a constraint: tools decide what an agent can do.
- **The check verifies the MECHANISM and is silent about the RESULT** — ask: if this passes, what exactly do I now know?
- **A test that drives the thing with an API the user does not have** measures a different system.
- **Two defects on opposite sides of a seam hide each other** — the first measurement after a fix is the SECOND defect's debut.
- **Extending a configurable protection can WEAKEN it** — ask which branch the extension takes OVER, not which one it adds to.

## Fail direction outranks bug count

When a guard is wrong, ask which way it is wrong before asking how often. A gate guarding
merges into `main` had six of seven behaviours wrong — and all six in the **`pass`**
direction. The count made it look like sloppiness; the direction made it a hole that
silently merged failing work. State the direction in the commit message; a reader months
later can re-derive the count and cannot re-derive the direction.

## How to prove a fix is a fix

**Stash it and rerun.** A test written alongside a fix that also passes without it proves
nothing, and looks like proof forever. Three of six tests written here passed either way.

```bash
git stash && pytest tests/unit/<new-test>.py; git stash pop
```

Four traps sit inside that one line, and each has cost a wrong conclusion here: the RESTORE
can silently no-op, a `.pyc` can stop a mutation reaching the interpreter, a non-unique
mutation pattern mutates something else and blames your test, and `git stash` inside a
killable command can take the whole session's work with it. All four, with their
measurements, are in the **`evidence-discipline`** skill.

Where the result is a screen, structural counts prove it *renders* and nothing more — see
[ui-quality](ui-quality.md). Look at it.

## Why this file exists rather than a memory

These findings crossed an agent channel and a context compact on the same day. Each hop is
lossy in one direction only: precision goes, confidence stays. A finding that arrives as
"we hardened the parsers" has lost the thing that made it useful — *which* shape broke it,
and which way it failed. **Write the shape into the repository while you still have it.**
