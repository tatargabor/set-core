## Why

This framework has a large corpus of development rules and **no mechanism that enforces any of
them**. There is no pre-push gate layer at all: `scripts/gates/` does not exist, and no git hook
manager is configured. Every rule in `.claude/rules/` is a sentence someone has to remember.

Measured on this repository today, against rules this repository already states:

| what a rule already forbids or requires | measured violations | what enforces it |
|---|---|---|
| "NEVER silently swallow errors (`except: pass`)" — code-quality | **404** handlers whose entire body is `pass`, in **83** files (0 bare `except:`) | nothing |
| new capability or contract change goes through OpenSpec | 118 commits since the rule was restated; 36 touched `openspec/changes/` | nothing |
| a change should validate | **14 of 36** active changes fail `openspec validate --strict` | nothing |
| a rule that cites a file should cite one that exists | **14 of 46** cited paths do not exist | nothing |

The counts are not the finding. The finding is that all four numbers are *invisible from inside the
workflow*: nothing reports them, so they only surface when somebody goes looking, and they have
therefore been free to grow. A rule without a gate is a wish, and this repository is running on 60+
wishes.

**A consumer project has solved exactly this, and its solution is in daily use.** That project runs
a chain of ~50 pre-push gates, and one of them enforces a step this framework does not have at all:
an **adversarial review of a change's plan, against the real code, before implementation starts**.
The evidence for it is theirs and it is specific. A change built from careful research — a code map,
a measured spike, ten delta specs, `openspec validate` green — read as a finished plan. A two-branch
adversarial review then found **four critical and eight serious defects**, every one of them by
reading the code rather than the spec: the plan would have deleted a route that another feature's
editor depended on, would have reproduced the very defect it was written to fix (it replaced a
deduplicating mechanism with one that only serialises), and would have left a document type
permanently unfinishable. None of it was visible from the spec. **Internal consistency, and
`openspec validate` with it, does not measure whether a plan fits reality.**

The framework side of the same gap is measurable here: **24 changes in this repository have started
work — a ticked task — and not one of them has a review artifact.** That number is also why this
change cannot simply switch a gate on.

## What Changes

- **A gate layer exists at all.** A `scripts/gates/` directory, a runner wired into pre-push, a
  documented way to scope which gates run for which push, and a per-gate **baseline file that may
  only shrink** — machine-enforced, because a baseline that can grow is a gate that can be turned
  off one line at a time. Gates fail closed and print what to do next.
- **An adversarial review step before apply, with a named artifact.** Two *independent* branches,
  because one reviewer finds one class of defect: one attacks the plan against the real code, the
  other checks the plan against the project's own mandatory rules. Their output is
  `review-findings.md` in the change directory, with a severity and a status per finding, and a
  mandatory closing section stating **what was checked and found correct** — without it, "no
  findings" and "did not look" are indistinguishable.
- **Two named agents rather than an ad-hoc prompt**, so the two branches stay independent and their
  attack surface is a list rather than a mood. Both are told, explicitly, that inventing a finding
  is worse than an empty list.
- **A gate that enforces the review**: a change with started work must carry a substantive
  `review-findings.md`, and an unresolved critical finding blocks. Freshly archived changes are
  checked too — implement-then-archive must not be a way around it.
- **A gate on the gates.** Every gate ships with a **two-directional self-test**: it fires on the
  case it exists for, and stays silent on a clean one. This is not ceremony. The consumer's own
  adversarial-review gate shipped with a fail-open defect — it matched only one *shape* of finding
  (a status-table row), while 3 of 17 findings files used headings instead, and a change whose own
  header read "apply is BLOCKED, one critical finding open" **passed the gate and was archived**. A
  gate that cannot fail is indistinguishable from one that is not installed.
- **The first gates for rules this repository already has**, chosen by measurement above rather than
  by taste: silent exception swallowing; `openspec validate --strict` on touched changes; a change
  with completed work not left unarchived; and a **truthfulness linter for the rule corpus** — a
  rule citing a path that does not exist is a rule the next reader will follow into nothing.
- **A baseline for every gate at introduction**, seeded from the current violations, so the layer
  lands without blocking work — and shrinks from there. With 404 and 24 measured violations, a gate
  introduced without a baseline blocks the next push and gets skipped permanently within a day.

Deliberately **out of scope**: deploying this gate layer into consumer projects. A consumer that
already runs a gate chain must not receive a second one, and the framework's standing rule is that a
project's proven foundation is extended, never replaced. Making these gates deployable — opt-in, and
only where no chain exists — is a separate change with its own safety argument.

## Capabilities

### New Capabilities

- `adversarial-spec-review`: a change's plan is reviewed before implementation by two independent
  adversarial branches, one against the real code and one against the project's mandatory rules,
  producing a findings artifact whose severities and statuses decide whether implementation may
  begin.
- `repo-gate-layer`: the framework's own repository carries a pre-push gate layer — a runner,
  scoping, per-gate baselines that may only shrink, and a deliberate-skip path that records its
  reason — so a stated rule can be enforced rather than remembered.
- `gate-self-test`: every gate carries a self-test that proves it fires on the violation it exists
  for and stays silent on a clean case, and the absence of such a self-test is itself a gate
  failure.
- `rule-enforcement-gates`: the first concrete gates, each one enforcing a rule this repository
  already states and none of which was enforced before — silent exception swallowing, OpenSpec
  validation and archiving hygiene, and the truthfulness of the rule corpus itself.

### Modified Capabilities

<!-- None. No existing capability changes behaviour: the orchestration merge gates, the profile
     verification rules and the OpenSpec artifact schemas are untouched. This layer runs at push
     time in this repository, which is an axis the framework does not currently occupy at all.

     Note the distinction, because the word "gate" is already taken here: the engine's *integration
     gates* (dep install → build → test → e2e) run inside a merge, on a consumer's project. These
     run on a push, on this repository. Same word, different subject; the naming is settled in
     design.md so the two are not conflated later. -->

## Impact

- `scripts/gates/` — new. The runner, the individual gates, and a shared library for the parts that
  keep being got wrong (fenced-block stripping, so an example inside a code block is not read as
  data; whole-line matching, so a quoted verdict is not read as a verdict).
- Git hook configuration — new. Pre-push. Commits stay unguarded deliberately: the framework's own
  rule already forbids `--no-verify` on pushes for exactly this reason.
- `data/*-baseline.txt` — new, one per gate that needs one, seeded from measured current state.
- `.claude/agents/` — two new agents for the two review branches. Three exist today; none of them is
  adversarial and none reads a change's plan against the code.
- `.claude/rules/` — one new rule stating when the review is mandatory and when it is not.
- `tests/gates/` — new. The two-directional self-test per gate, and a test that fails when a gate
  exists without one.
- **No change to `lib/set_orch/`, `modules/`, or any consumer-facing template.** This change adds a
  development-time layer to this repository; it does not touch the framework's runtime or anything
  that is deployed.

## Status

Ready to apply. The shape is taken from a working implementation rather than designed here, and the
decisions that differ from it — what set-core adopts, what it deliberately leaves behind, and why
the deployment half is a separate change — are recorded in `design.md`.
