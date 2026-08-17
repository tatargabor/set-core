## Why

The framework's apply is **change-granular**. The loop emits `apply:<change>` and hands the *whole*
`tasks.md` to one agent (`lib/set_orch/loop_prompt.py:242`); nothing inside a change is ordered,
sliced, or stopped. Measured: `grep -rn "depends" lib/set_orch/*.py` returns only *change-to-change*
`depends_on` (planner, merger, category_resolver) — between task groups there is nothing.

A consumer project has been running the missing half in production for a month, and it is the half
that decides whether a large change can be implemented at all: sectioning it, so each group runs in
a **fresh context** with only its own slice, a gate and a commit per group, and a stop point a human
can answer. The framework orders changes *relative to one another*; that engine orders the *inside*
of a change. These are two levels, not refinements of each other.

Two things make this urgent rather than tidy.

**The framework cannot see, install or version what it does not own.** Today the mechanism lives in
one project's tree: the framework can neither ship it to a second project, nor say which version a
project is running, nor report where a run has got to. The agent working in that project drives it
perfectly well — what is missing is everything *around* that: distribution, versioning, and a state
the framework can read.

**And a second implementation is a schedule, not a risk.** The consumer's engine took 18 commits in
30 days. A parallel port would fall behind on the day it is born, so the decision taken with them is
one engine, in the framework, with their copy retired against evidence — not a permanent bridge.

## What Changes

- **A work-unit engine in Layer 1.** A *work unit* is a piece of work run in a fresh agent context
  and closed by a **verdict**, a **gate**, a **commit**, and — when it cannot finish — a named
  **stop condition**. The unit is deliberately not "a task group": measured with the consumer,
  their two engines differ in *what the unit is*, and their prompt builders count **1 vs 4** (one
  builder over N slices; four builders — triage/investigate/fix/chain — over one item). A third
  shape exists already: their investigation takes a `{lens}` and is called from three sites, i.e.
  the same phase from several viewpoints, compared. The abstraction is designed for all three;
  **this change ships the slice lane only** — hence the name.
- **Task-group resolution inside a change.** Numbered group headings, `<!-- depends: -->` edges, and
  a **fail-closed serial default**: an unannotated group waits for its predecessor. Absent
  annotation, "independent" and "we forgot to write it down" are indistinguishable from outside,
  and parallelising is the more expensive mistake.
- **Slice handover, not file handover.** The agent receives its group's block plus carry-over notes
  from the previous run — both from *the same group* (a resumed `PARTIAL`) and from *the previous
  group*, because a fresh context forgets discoveries as readily as noise.
- **A schema-constrained verdict, and a reality check against it.** `GROUP_DONE` / `PARTIAL` /
  `NEEDS_INPUT` / `BLOCKED`, with **open decisions as a separate field** — a note is not a stopper,
  and a decision left in prose gets read by the next section and answered on the human's behalf.
  What the agent claims is then diffed against the checkmarks actually in `tasks.md`, in both
  directions.
- **A deferred-work connector, not an answer flow.** A directory that accepts `<change>#<task>`-keyed
  answer JSON. Who fills it — a chat bridge, the dashboard, a person — is the caller's business and
  never the engine's. **Intake runs at the engine's entry point on every path**, not as a side effect
  of a loop.
- **One entry point, not two.** The engine is entered by a command run in the project's tree — that
  is how an agent working there starts a slice today, and it needs no running service. The
  framework's surface starts a unit by invoking *the same command*, so there is exactly one way into
  the engine and one place where run state comes from. The surface's own job is to read that state.
- **NOT in this change:** loop chaining, reconcile, run history, the phase lane, the lens lane. The
  abstraction must not *exclude* them; it does not ship them.

## Capabilities

### New Capabilities
- `work-unit-engine`: what a work unit is, how it is run in a fresh context, how it is locked to one
  seat, and how it is closed — verdict, gate, commit, or a named stop condition.
- `task-group-resolution`: reading groups and dependency edges out of a change's `tasks.md`,
  fail-closed ordering, and cutting the slice plus carry-over that one run receives.
- `deferred-work-connector`: setting a unit aside with a nameable resume condition, and the
  filesystem connector through which answers arrive — including partial writes, several answers for
  one key, and making consumption visible.
- `work-cycle-control`: one entry point into the engine — a command run from the project's own tree,
  by the agent working there, with no framework service required. Every other caller, including the
  framework's surface, goes through that same command; run state is written where the framework can
  read it without executing anything.
- `work-cycle-adoption`: what it takes for *any* registered project to be driven this way — a
  declaration rather than framework code, an un-adopted project distinguishable from a finished one,
  several projects driven from one place with their state kept apart, and adoption that does not
  require a project to change how it already works.

### Modified Capabilities
<!-- None. The existing change-granular loop keeps its behaviour for the whole parallel period; the
     new engine is a second, additive path. Measured: no existing spec states any behaviour for `[?]`
     tasks (0 hits across 436 spec files, of which 376 contain SHALL) — so nothing is contradicted. -->

## Impact

**Code.** A **separate top-level package**, `lib/set_workcycle/` — not a module inside the
orchestration package. The engine is a distinct capability that happens to reuse orchestration
machinery; putting it inside `set_orch` would make it read as part of orchestration, and a dependency
that reads that way soon becomes one. The package split fixes the **direction** of the dependency:
`set_workcycle` imports from `set_orch`, never the reverse, so orchestration keeps working with the
engine deleted. Packaging cost is one entry in `pyproject.toml`'s package list; `lib/` already
carries several top-level packages. Reused rather than rewritten:
`GatePipeline` + the profile-driven `gate_registry` for gates, `chat.py` for stream-json consumption,
`loop_tasks.py` for checkbox parsing, plus `events.py`, `paths.py`, `process.py`. Project-specific
steps — type-check and test commands, source-tree sweeps — reach the engine **through the profile**,
never through Layer 1.

**Entry point.** A command shipped with the framework and invoked from a project's tree. No new HTTP
mechanism for starting work: the surface invokes the same command, so a second start path — which
would mean a second source of run state — cannot come into existence. No existing endpoint changes
shape.

**A consumer's migration, and what it obliges here.** Their engine keeps running until the framework
version has run *the same change on their tree*, proven by a real run — a non-trivial change with
group dependencies and at least one human stop. New capability goes only into the framework version
from now on; their copy is frozen to bug fixes. That freeze is only honest if this work does not
drag, which is why the slice lane ships first.

**Two defects deliberately not inherited**, both measured on their side today: a seat identifier
scoped to the *project* matches every live session in it (seven, on the day it was measured) — the
seat is always session-scoped; and correct stop handling that lives in the rarely-called command
variant is, in practice, absent — stop handling is a property of the engine.
