## Context

set-core already differentiates changes twice, and both mechanisms answer the same kind of
question — *what does this change touch* — with an answer produced **before** the work:

- `gate_profiles.py:145` maps a self-declared `change_type` onto a gate profile. Measured
  on `HEAD`: `infrastructure` sets `build`/`test`/`e2e`/`test_files` to `skip` and
  `spec_verify` to `soft`; `cleanup-after` also skips `review` and `rules`.
- `category_resolver.py` unions six deterministic layers plus an LLM to produce categories
  used for gate and rule selection.

Neither is checked afterwards. A `grep` for a retrospective comparison
(`mismatch|contradict|actual|declared` near `change_type` in `lib/set_orch/*.py`) returns
one unrelated function signature. In an autonomous run the declaration is written by an
agent, and the cheaper declaration is the one that costs the agent less work.

The failure this produces has been measured in a consumer project's history: a commit
delivering a new module implementing two specified capabilities on a financial path, with
no specification updated, **and every gate green** — because it had been classified as
trivial and nothing measured the classification afterwards. That project's response was
not a better classifier. It was three retrospective checks.

The 2026-07-19 factory verdict constrains the shape: build a differentiated pipeline
first, alone; the router comes only once two provably different pipelines exist to choose
between, because *"a taxonomy with near-zero behavioural delta is a false gate, and this
repo already has three."*

## Goals / Non-Goals

**Goals:**

- Measure, after the work, whether the declared lane contradicts what was delivered.
- Keep every signal on the project's side; Layer 1 holds the mechanism and no pattern.
- Produce a real behavioural delta between two lanes — opposite ends of the process gated —
  so that a future taxonomy would have something to sort between.
- Survive introduction into a repository that already has violations, which is the step
  most such gates die at.

**Non-Goals:**

- The router. Not built, not designed, not stubbed.
- Any change to `change_type`, `gate-profiles`, `gate-registry` or
  `change-category-resolver`. They answer a different question and stay untouched.
- Proving a change's lane is *correct*. This gate can only prove a contradiction.
- A new field on the change definition, or a new prompt anywhere.

## Decisions

**D1 — Retrospective measurement, not an entrance classifier.** The alternative is a better
classifier: more layers, a stronger prompt, a required field. It was rejected because the
existing failure is not that the classification is imprecise — it is that *nothing
disagrees with it*. Adding a seventh input to a classifier nobody checks improves the
number that is already unverified. A retrospective check is also cheap to be wrong about:
a false fire costs a warning line, whereas a false classification silently removes review
and tests from a change that needed them.

**D2 — The signal is a shape, never a volume.** Rejected: thresholds on lines or files
changed. A large generated update is routine; a small change to a decision predicate on a
critical path is not. A size threshold therefore fires hardest on the safest population,
which is worse than not firing at all because it trains everyone to ignore it. A *new
module where none existed* is close to the definition of a new capability, and it is
mechanically decidable.

**D3 — The two lanes gate opposite ends of the process.** A *changing* lane gates the
entrance: specification, review, delta. A *restoring* lane gates the exit: a regression
test citing the defect's stable identifier. This is the design, not a consequence of it —
it is what makes the two pipelines *provably different*, which is the precondition the
verdict sets before any router may exist. Rejected alternative: the same chain with
different strictness levels, which produces a taxonomy with near-zero behavioural delta —
the verdict's named failure.

**D4 — Refuse an incomplete declaration; never default one.** Each of scope, baseline and
promotion condition has a defaulting failure that is invisible: a defaulted scope judges
work its author never meant it to, a defaulted baseline forgives the existing backlog
silently, and a defaulted promotion condition turns a warning into a blocker with nobody
deciding. Refusal is loud and cheap; a default is quiet and wrong.

**D5 — The baseline may only shrink, and a change that would grow it fails.** Rejected: an
"acknowledged violations" list that can be appended to. That is the same mechanism with the
brake removed, and it converts the debt register into a suppression list within weeks. The
gate reporting outstanding debt even when nothing new fires is what keeps the number
visible; a quiet zero is how the backlog stops being anyone's problem.

**D6 — WARN by default, promotion only on a declared measurement.** A gate that blocks on
day one is switched off by the end of the week, and switching it off removes the warning
too. The promotion condition is declared by the project because only the project knows what
a real signal looks like in its own tree — the framework cannot supply a threshold that
means anything.

**D7 — Three outcomes per signal, and no overall verdict.** Fired, did not fire, could not
be evaluated. Collapsing the third into the second is a false absence in the one place it
would be believed. And no summary field asserting the lane is correct, for the same reason
the consumer's release-readiness answer carries no `ready` field: the gate cannot prove the
absence of a contradiction it has no signal for, so a verdict would assert what nobody
measured.

**D8 — A signal never evaluates its own definition.** A pattern-based signal matches the
sentence describing the pattern. Left alone, the gate reports its own rule and spec as
violations, and the cheapest way to silence it is to delete the explanation — removing the
reason before the defect. Measured on this repository the same day: a credential-literal
scan produced six survivors, **two of which were the rule that defines the scan and the
spec describing the violation.**

## Risks / Trade-offs

- **The gate proves contradiction, never correctness.** A change whose lane is wrong in a
  way no declared signal covers passes silently → the spec forbids an overall verdict field
  and requires the unevaluated count to be reported, so the gap is visible rather than
  papered over. Stated in the proposal as well, because a partial check reported as a
  complete one is worse than no check.
- **Signals are the project's, so a project with weak signals gets weak protection** → this
  is accepted, and is the same trade the status contract makes. The alternative — framework
  signals — mismeasures every project it was not written against while looking
  authoritative.
- **A refused declaration could hide a real signal** → refusal is reported alongside the
  other signals' results, never in place of them, and one refusal does not disable the rest.
- **Introduction noise** → shrink-only baseline plus WARN-first. Both are requirements, not
  guidance, because both are the steps a hurried adopter skips.
- **A second mechanism that looks like the existing ones** → the risk is a future reader
  merging this with `change_type` or the category resolver. The proposal and this document
  both state the axis difference explicitly: those say what a change touches, this says
  whether the declaration survived contact with the work.

## Migration Plan

1. Ship the reader and evaluator with **no** signals declared anywhere. Behaviour is
   unchanged by construction: no declaration, no evaluation, no all-clear.
2. Declare signals in a project — not in `modules/`, and not in this repository's own
   templates — and observe at WARN.
3. Promote only when that project's declared measurement is satisfied and recorded.

Rollback is removing the declaration; the framework half is inert without one.

**D9 — The declaration lives in the tree, and the rationale lives with the gate.** This
closed the structural question that was left open above; it was settled by measured
experience from a project that has run the pattern for months, not by preference here.

*Where.* Not the status contract. Their gates run in a pre-push hook with no database and
no server — the same constraint that made the status contract itself "file plus CLI, no
HTTP" — and lane signals are evaluated during verification of a **worktree**, which is the
same environment: there is no live project to ask. A declaration reachable only through a
running system is unreadable exactly when it is needed, and it fails in the direction that
looks like "nothing to check".

*How many places.* The cost of each split was measured across four homes — the call (the
hook configuration), the execution (the gate script), the norm (the rule prose), and the
debt (the baseline). The finding is asymmetric and it is the useful part: **the
configuration↔implementation split cost zero measured incidents, while prose as a third
home cost three** — a third of the rule corpus referencing files that no longer existed
(43 lines of debt still outstanding), four parallel process descriptions with different
phase numbering that did not contradict each other but did not know about each other, and a
count in prose that said 7 where the reality was 17, erring *downward* so it understated the
risk. So: separate the call from the execution freely; do not move the norm out of reach.

*Which direction the link must be strong.* Measured on their tree: 14 of 19 gates name a
rule, 11 of 76 rules name a gate. The asymmetry is correct, and the reason generalises —
**the gate's message is what someone reads at the moment it fires**, and that is the only
moment its rationale is worth anything. If the reason lives one indirection away, the
fastest available response is to suppress the gate. Hence two requirements: a *triggering
case* is a mandatory declaration field, and it must appear in the firing message along with
the way to suppress that one signal — because a reader who cannot find the narrow bypass
will find the blanket one.

## Open Questions

- **Whether a lane needs a name at all.** The two lanes are currently distinguished only by
  which end they gate. Naming them invites the taxonomy the verdict defers. Leaning toward
  leaving them unnamed until a second pipeline exists.
