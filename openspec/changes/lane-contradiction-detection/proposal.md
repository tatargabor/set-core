## Why

set-core selects a change's entire gate chain from a **self-declared** `change_type`, and
**nothing ever checks whether that declaration matched what the change actually did.**
Measured on `HEAD` (2026-07-24):

- `lib/set_orch/gate_profiles.py:145` reads `change_type` off the change and resolves the
  gate profile from it. `infrastructure` sets `build`, `test`, `e2e` and `test_files` to
  `skip` and `spec_verify` to `soft`; `cleanup-after` additionally sets `review` and
  `rules` to `skip`.
- `lib/set_orch/state.py:715` reads it from the change definition with a default of
  `"feature"`. It is written by the planning step — in an autonomous run, by an agent.
- `grep -rniE "change_type" lib/set_orch/*.py | grep -iE "mismatch|contradict|actual|declared"`
  returns **one** hit, and it is an unrelated function signature. There is no retrospective
  check anywhere.

So a change declared `infrastructure` runs no build, no tests and no review, and the only
thing standing between that declaration and reality is the judgement of the process that
benefits from the cheaper answer.

This is not hypothetical. The pattern was measured in a consumer project's history: a
commit delivering **a new module, two specified capabilities, on a financial path, with
zero spec updates — and every gate green**, because the work had been classified as
trivial and nothing measured the classification afterwards. They built a retrospective
gate in response, and it is that mechanism, generalised, that this change adopts.

**Why now, and why this shape rather than a router.** The 2026-07-19 factory verdict
identified the missing piece as a router between differentiated pipelines, and forbade
building it first: the taxonomy comes *"only once two provably different pipelines exist
to choose between"*, because otherwise *"the router gets built and has nothing distinct to
route to… a taxonomy with near-zero behavioural delta is a false gate, and this repo
already has three."*

**What this change is, stated precisely, because its first name overclaimed.** It was
called `differentiated-change-pipeline`, and it does not build a pipeline: every task here
builds the *instrument* that measures whether a declared lane contradicts delivered work.
That instrument is a genuine precondition — "two **provably** different pipelines" cannot be
demonstrated by a mechanism that measures nothing, so the detector has to exist before the
second pipeline is worth building — but a change whose name claims more than its tasks
deliver is the same defect this repository keeps finding elsewhere, and it would have been
read later as "the pipeline is done". Renamed rather than rescoped. **The differentiated
pipeline itself is the next change, not this one; the router remains after that, and only
if the delta turns out to be real.**

## What Changes

- **A project may declare *lane signals*** — narrow, mechanically-decidable conditions
  evaluated against the delivered work — and set-core evaluates them. The signal
  definitions are project data, exactly as contract commands are; Layer 1 holds no
  signal of its own.
- **Lane integrity is measured retrospectively, never classified at the entrance.** No new
  classifier, no new prompt, no new field an agent must get right before work starts. A
  lane signal fires only when the delivered artefacts contradict the declared lane.
- **Per-lane gate chains are asymmetric by design.** The two lanes gate opposite ends of
  the process: a *changing* lane gates the entrance (is this the right thing to build —
  spec, review), a *restoring* lane gates the exit (can it come back — a regression test
  citing the defect's stable identifier). This is the behavioural delta the verdict
  requires before any taxonomy is justified.
- **Every lane signal ships with a shrink-only baseline.** Existing violations are recorded
  as debt, not forgiven; the baseline may lose entries and never gain them.
- **Every lane signal starts as WARN and is promoted only on a measured condition**
  declared alongside it. A signal with no promotion condition stays WARN forever.
- **Every lane signal declares its scope.** A signal with no stated scope is refused rather
  than evaluated everywhere — an unscoped signal evaluates the same work twice and inflates
  its own baseline.
- **A lane signal never evaluates the corpus that defines it.** A signal whose pattern
  appears in the rule, spec or test that documents it would otherwise report itself, and
  the cheapest way to silence it is to delete the explanation.
- **NOT built:** the router. No change to `change_type`, to `gate_profiles`, or to
  `change-category-resolver`. Those answer *what a change touches*; this answers *whether
  the declared lane survived contact with the delivered work*. They are different axes and
  merging them would erase the discrepancy that is worth seeing.

## Capabilities

### New Capabilities

- `lane-signal-declaration`: how a project declares lane signals — the signal, its lane,
  its scope, its baseline, and its promotion condition — and the rules Layer 1 obeys when
  reading them (domain-free, no built-in signals, absent means absent).
- `lane-contradiction-gate`: how a declared signal is evaluated after the work, how WARN
  and ENFORCE differ, how the baseline is applied and maintained, and what the gate must
  never do (report itself, count an unevaluated signal as a pass, or grow a baseline).

### Modified Capabilities

None. `gate-profiles`, `gate-registry` and `change-category-resolver` keep every existing
requirement; this capability sits beside them and reads their output without altering it.

## Impact

- **Layer 1** (`lib/set_orch/`): a new module holding the declaration reader and the
  evaluator; a `ProjectType` extension point for supplying signal definitions. No
  domain-specific pattern enters this layer.
- **Layer 2** (`modules/`): nothing required. A module may supply signals, but the
  reference implementation of a signal set belongs to a project, not to a project type.
- **Gate pipeline**: one new gate registered through the existing `gate-registry`
  mechanism, so it inherits observability and per-change configuration for free.
- **Consumers**: none forced. A project declaring no signals gets today's behaviour
  exactly — no evaluation, no warning, and specifically **no** empty-set "all clear",
  which would be a false absence in the one place it would be believed.
- **Risk that must not be understated**: this gate can only prove *contradiction*, never
  *correctness*. A change whose declared lane is wrong in a way no declared signal covers
  passes silently. The gate's own documentation must say so, because a partial check
  reported as a complete one is worse than no check.
