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

**The measurement is inside the corpus it measures.** `pgrep -af "<pattern>"` matches the
searching process itself, because the pattern is in its own command line — and so is any
word chosen to filter it, so `| grep -c 'while :'` counts a command containing the string
`'while :'`. Measured four times in one day here: the check reported 3, then 2 watchers
while exactly one ran. The direction is what costs: it **over**-reports, and "two watchers"
invites killing one, which can leave zero. The general form covers a grep over a corpus that
includes the file doing the grepping, a test that asserts about a directory it writes into,
and a count of matches that its own query created. Resolve each hit to an identity and
discriminate on something the impostor cannot fake — here, process age: a real watcher is
hours old, the self-match is always `00:00`.

**A dead test looks exactly like a passing one, from far enough away.** Fifteen tests here
raised `TypeError` on a removed keyword argument *before reaching any assertion* — including
the one test written to guard against a quoted verdict being read as a verdict. Collection
counts and green suites do not distinguish "asserted and held" from "never got there".

**A pattern is blind to negation, and the blindness looks like a match.** Anchoring a
sentinel at the start of a line stops a *quoted* verdict and nothing else. `VERIFY_RESULT:
PASS is NOT what I emit here` still parsed as a pass, and `CRITICAL_COUNT: 0 — but I could
not check the auth module` still parsed as zero — where zero *downgrades an explicit failure
to a pass*, so the clause admitting the gap was the thing that hid it. When a sentinel is
supposed to be a line, match the WHOLE line; anything else is a substring test wearing an
anchor.

**The name is a second place, and it is the copy people actually read.** A limit stated in
a header, a docstring or a design section does not protect anything if the *name* claims
more, because the name is what travels — into a summary, a test report, an `ls`, a status
line, a compact. Found on both sides of an agent channel within minutes of each other on
2026-07-24: a change called `differentiated-change-pipeline` whose 22 tasks built a detector
and no pipeline (`grep -inE "regression|exit gate|per-lane|second pipeline" tasks.md` → zero
hits, while its own design argued the two lanes gate opposite ends), and a test suite named
"the output surface is CLOSED" that was closed in one direction only — a limit its file
header stated loudly and its fourth test specifically asserted.

This is the second-place defect turned inward: **within a single artifact, the name is a
second copy of the content.** It is the shortest and most-read copy, so it drifts first and
costs most. Two consequences: put the limit *in the name* when the thing is one-directional
or partial, and prefer renaming to rescoping — a name that claims more than the tasks
deliver reads later as "that part is done".

**And a third, about how to look for it — because the obvious search is worthless.** The
class is *a claim about what a MECHANISM covers*, not *a completeness word*. Grepping
`every|all|never|always|complete|closed` across a whole test suite finds names describing
asserted **behaviour** — "the quantity never goes negative", "every price × discount
combination" — which are correct and numerous. Measured on the other side of the channel:
**268 hits on the broad corpus, all legitimate; 1 on the correctly narrowed one.** Search
only the names that describe a checker: gate suites, contract suites, manifest and surface
tests. Anywhere else the hit rate is so bad that the next person abandons the search before
reaching the one real instance — which is the same failure as a gate that fires daily on
nothing.

*Worked example of the narrowing, from this repo:* the broad pattern over `tests/unit/*.py`
plus the web unit tests returns 2; the narrow corpus is 56 test names across the gate and
contract suites, of which two make a mechanism-coverage claim
(`test_every_envelope_field...is_named_in_the_living_record` and its `error_class` twin).
Both say **"is named"**, which is exactly what they check — their docstrings explicitly
refuse to claim the field is described *correctly*. So: one instance found and fixed on the
peer's side, none here, and the corpus and pattern are stated so the negative result can be
rechecked rather than believed.

**A marker outranks the body, so a marker that is true of a narrower subject still lies.**
Two shapes, and the second is the harder one. The blunt shape: a strike-through, a `✅` or a
"Built" that simply contradicts the text underneath it — a list item here read as open while
its own last paragraph said the goal it belonged to was met. The subtle shape: the marker is
**true of its own subject** and the reader takes the subject to be wider. Measured on the
other side of the channel the same day — a row marked `✅ DONE` because the *tool* was
finished, while sixteen people who had filed reports still had no answer. Nothing in it was
false; the subject had quietly widened between writer and reader.

So: **when an item's name is broader than the thing delivered, the marker must say what it
is a marker OF.** "Built" becomes "built as far as the API; the click is unproven". The
reason is not fairness, it is arithmetic — *the marker is the part that gets counted*, in a
summary, in a status line, in a compact. A body that states the limit while the marker
overclaims has put the correction where nobody is standing, which is the same defect as the
overclaiming name one section up.

**Record the pattern that was WRONG, not only the number that is right.** A corrected figure
sitting alone invites the next reader to re-derive it — and they will reach for the same
obvious query, because it was obvious to you too. Measured across this day: `grep -i` on a
Hungarian keyword returned 12 where the answer was 7, matching a title containing the word
and a note saying the thing was *pending* — the two cases that mean the opposite; an
unanchored severity match, a bare substring search for a field name, and a completeness-word
sweep all failed the same way. In every case the corrected number is the cheap half of the
finding and the refuted pattern is the durable half.

The stronger form, where it fits: **hold the wrong pattern in a test.** `test_a_bare_substring
_check_would_not_have_caught_it` exists so that a later "simplification" back to `key in
document` fails instead of looking identical and quietly checking nothing. A comment asks to
be believed; a test refuses to be reverted.

**A zero with an empty breakdown is a shape error until proven otherwise.** From the same
measurement: a count came back `0` because the reader looked for its list under the wrong
key of an envelope, so `undefined` became an empty array became zero — and that zero would
have *proved* there was nothing to answer. The tell was not the zero, which looked like data,
but that the breakdown beside it was empty too. When a count is zero and its own grouping is
empty, inspect the **shape of the input** before writing down the conclusion.

**A subagent's "done" is not evidence that anything happened.** Measured here: an unflagged
`claude -p` asked to create a file replied `Done.` and exit 0, and the file did not exist —
the tool layer had refused the write and the agent did not know. So a gate that waits on an
action must measure the action's *trace* (a file, a commit, a line in a log), never the
report. The same fact cuts the other way too: **an instruction is not a constraint.** What
an agent cannot do is decided by the tools it holds, not by the sentence telling it not to.

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

**Assert the RESTORE too, not only the mutation.** Mutation testing has two steps that can
silently no-op, and only the first one is ever guarded. Measured here: a mutation was applied
through a helper that asserts its target exists (so that half was honest), and restored with
`git checkout <file> 2>/dev/null || true` — on a file that was **untracked**. `git checkout`
cannot restore a file git does not know about; the `|| true` swallowed the error; the suite
went green because the mutation was reverted only in the *assumption*, and the broken value
sat in the tree ready to be committed as the shipped behaviour. The direction is what makes
it expensive: the failure produces a *reassuring* run and leaves the defect behind. So the
restore is checked the same way the mutation is — re-grep the file for the original value
before believing the green run:

```bash
grep -n 'position="before:end"' lib/set_orch/lane_gate.py   # the restore, verified
```

And prefer a restore that works on the file's actual state: `cp` a copy aside, or write the
original back explicitly. A revert command chosen for the tracked case fails silently in the
untracked one — which is exactly when new code is being mutation-tested.

**Never open a file for writing in the same expression that reads it.** Measured on the
other side of the agent channel, on a 290 KB append-only log: `open(p, "w").write(open(p)
.read().replace(...))` truncated the file to **0 bytes**. Python evaluates `open(p, "w")`
first, which truncates immediately; the read that follows then sees the already-empty file.
No exception, no non-zero exit. The same author had written it safely one round earlier —
read into a variable, then write — and compressed it onto one line because it was shorter.

Two things make it worth a rule rather than a note. **The failure direction is reassuring:**
an empty file is a valid "nothing to write" shape, so every downstream check (size, diff,
commit) stays green on it. And **the backup was refreshed by the destroying command itself** —
a `cp` to a mirror ran after the truncation, so the mirror held the zero. Only the git
history, written before the operation, still had the content. *A backup that the damaging
operation updates is not a backup.*

So: read in a separate statement, or write a temp file and `mv`. And when a check exists to
catch a class of damage, make sure the damaging path cannot be the thing that updates it.

**A baseline that shares the working tree's code is not a baseline.** Measured here on the
very check this repo prescribes for regressions. `git worktree add --detach /tmp/base HEAD`
then `cd /tmp/base && pytest` looks like running the old version — and does not. An editable
install resolves the package from a finder that hard-codes the development path, so the
baseline's TESTS ran against the working tree's LIBRARY. Two versions were never compared.

The direction is the expensive part, and it is the reassuring one twice over. Additive
changes — the common case — leave old tests passing against new code, so the two failure sets
come out identical and the check reports "no regression" having compared one version with
itself. And it is *most* convincing exactly when it is least earned. It surfaced only because
two baseline tests failed that could not fail at `HEAD`, which was luck, not method.

The general shape: **`cd` into a directory is a proxy for running the code in it.** Point
`PYTHONPATH` (or the equivalent) at the baseline's own source, and *assert where the import
came from* before believing the run:

```bash
PYTHONPATH=/tmp/base/lib python -c \
  "import set_orch;assert set_orch.__file__.startswith('/tmp/base/'),set_orch.__file__"
```

**And the first repair was itself a narrowing.** It set `PYTHONPATH` to one root and asserted
one package by name. This repo has three first-party roots, and a raw `.pth` entry hard-codes
one of them to the development tree — so a package imported by 10+ unit test files still came
from the working tree, and the "corrected" baseline was still partly hybrid. A hand-named list
is a second copy; this one drifted at the moment it was written. The replacement asserts the
THING — at session end, no loaded module may resolve to any set-core checkout other than this
one — which is a check nobody has to maintain a list for.

**And the detector was proven to fire before its zero was believed.** A check that reports
clean is indistinguishable from one that cannot report anything, so the leak checker was run
against a deliberately un-isolated baseline: **128 leaks** on the full suite, **0** with the
import roots set. Only then does the zero mean something.

Two of this repo's own measurement bugs surfaced doing it, both worth more than the result:

- **`$?` after a pipeline is the LAST command's status.** `pytest … | tail -3; echo $?`
  reports on `tail`, which always succeeds. It read `exit=0` for a run whose status was never
  examined, twice, in the same breath as concluding the check worked.
- **A poll condition must exclude the state the file starts in.** The checker writes
  `NOT REACHED` at configure time so an unrun hook reports itself — and a wait loop on
  "file is non-empty" then fired on that placeholder and read the answer before it existed.
  A guard against silence became the thing that produced a premature reading.

The finding underneath both: **a single-file run said `LEAKS 0` while the full suite said
128.** 140 of 217 unit files insert the source root themselves and 77 do not, so whichever
module imports first decides for the entire session. *Isolation that depends on collection
order is not isolation* — and it fails toward clean on exactly the small, fast run someone
reaches for when checking quickly.

**A generated artefact escapes even a correct source path**, because it is a product rather
than a source. Measured on the other side of the channel: a generated database client resolved
from the main tree while the worktree held modified schema source, so the tests ran worktree
code against main-tree schema — the same hybrid one layer up, and additive schema changes keep
it green. The check therefore has two questions, not one: *where did the module come from*, and
*when was what it loads generated*.

Three lessons outrank the fix, and all are already in this file under other names. A guard is
only as good as the thing it actually measured. *The check that verifies other work is itself
work nobody checks*, because a green comparison is where reading stops. And a repair for a
narrowing is a candidate narrowing until its own traversal has been measured.

**Never put `git stash` in a command that can be killed.** Same defect one level up, and it
nearly cost this session's uncommitted work: `git stash -u && <full suite> && git stash pop`
run in the foreground hit a two-minute tool timeout **after the stash and before the pop**,
leaving a clean tree and every change of the session in `stash@{0}`. It is recoverable —
`git stash list` then `git stash pop stash@{0}`, and check the list first because an
unrelated older stash may sit below it — but only if you notice, and a clean `git status`
after a timeout looks exactly like a command that never started. For a before/after
comparison use a **`git worktree add --detach <dir> HEAD`** instead: the baseline gets its
own directory, the working tree is never touched, and both suites can run at once.

## Why this file exists rather than a memory

These findings crossed an agent channel and a context compact on the same day. Each hop is
lossy in one direction only: precision goes, confidence stays. A finding that arrives as
"we hardened the parsers" has lost the thing that made it useful — *which* shape broke it,
and which way it failed. **Write the shape into the repository while you still have it.**
