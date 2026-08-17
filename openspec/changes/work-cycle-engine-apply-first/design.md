## Context

The framework already runs agents against changes. What it cannot do is run *part* of a change: the
loop hands the whole `tasks.md` to one agent (`lib/set_orch/loop_prompt.py:242`) and lets it work
until it stops. For a large change that is the difference between an implementation that finishes and
one that dilutes — the fortieth message decides the same questions the fifth did, with less of the
file in view.

A consumer project has run the missing half in production for a month. The design below adopts its
shape rather than inventing a parallel one, because that shape is proven and this framework's rule
is to extend a working foundation, not replace it. What the framework contributes is the abstraction:
the consumer's engine knows about one lane; the framework has to carry at least three.

Three measurements bound the design, and each one closed a question that would otherwise be argued:

- **The lanes differ in their work unit, not in their plumbing.** Prompt builders: **1** in the apply
  engine (one shape, N task groups) against **4** in the bugfix engine (triage / investigate / fix /
  chain, one item). A third shape already exists there — investigation takes a `{lens}` and is called
  from three sites, i.e. the same phase from several viewpoints, compared.
- **Shared function names are not shared code.** The two engines have 15 identically-named functions;
  only three share an implementation (100%, 94%, 71%), the rest sit between 3% and 39%, and
  `extractJson` is 13 lines on one side against 332 on the other. So the common engine cannot be
  extracted by merging two files. It has to be designed from requirements — which is what the specs
  in this change are.
- **The gate is already an abstraction here.** `resolve_gate_config(change, profile, …)` returns a
  `GateConfig` of gate names and modes, resolved through a six-layer chain ending at the profile. The
  engine does not need gate logic; it needs to *call* this one.

## Goals / Non-Goals

**Goals:**
- A work-unit abstraction in Layer 1 that admits slice, phase and lens units without knowing what any
  of them mean in a domain.
- The slice lane shipped whole: group resolution, fail-closed ordering, slice handover, carry-over,
  schema-constrained verdict, verdict-vs-tree diff, and the answer connector.
- One entry point — a command run in the project's tree — used by the agent working there and by
  the framework's surface alike, so run state has exactly one producer.
- A migration path that ends with **one** implementation, evidenced by a real run.

**Non-Goals:**
- Chaining units automatically. The caller decides when the next unit runs.
- Reconciling an interrupted run into a commit, and run history — both later.
- Shipping the phase or lens lane. The abstraction must not *exclude* them; this change does not
  build them.
- Replacing the existing change-granular loop. It keeps working, unchanged, for the whole parallel
  period.

## Decisions

### D1 — A work unit is the abstraction; the lane decides what one unit is

A **work unit** is: a slice of work, run in a fresh agent context, closed by a verdict, then a gate,
then a commit — or set aside with a named condition. The engine owns that lifecycle and nothing else.
What constitutes one unit is the lane's business: a task group (slice lane), one phase of an item
(phase lane), one viewpoint on a phase (lens lane).

*Alternative considered:* model the cycle directly — "iterate the groups of a change". Rejected on
the 1:4 measurement: the bugfix lane's four prompt builders are not four groups, they are four
*kinds* of unit over one item. A group-shaped abstraction would have forced the second lane into a
shape that does not fit, which is how a framework starts requiring projects to change how they work.

### D2 — A lens is an attribute of a unit, not a fan-out construct

Running the same phase through three viewpoints is three units that share an input and differ by one
attribute. Comparing their results is itself a unit, with the three verdicts as its input.

*Alternative considered:* a first-class fan-out — one unit that spawns N and joins them. Rejected for
now because it adds a second control-flow shape to an engine whose only shape is "run one unit", and
because the join is not free of judgment: someone has to decide what the three viewpoints together
mean, which is work, not plumbing. **This is the design's least-settled decision** — it is stated so
it can be refuted, and it has been put to the consumer whose engine already runs lenses. If the join
turns out to need engine support, it is additive: a unit that takes several verdicts as input.

### D3 — The engine is tree-agnostic; the caller supplies the tree

The engine takes the working tree as an input and locks *that tree*. The framework's own
orchestration hands it a worktree; a consumer running it on a trunk-based repository hands it the
repository root. Neither is privileged.

*Why it matters:* the framework's existing machinery assumes a worktree per change, and the proven
engine assumes one tree with a lock. Encoding either assumption into the engine would exclude the
other. The lock, not the tree layout, is what prevents two units from colliding.

### D4 — Gate configuration is resolved through the existing chain; the runner is chosen by measurement

Gate steps come from `resolve_gate_config(change, profile, …)` — the same six-layer chain the merge
path uses, ending at the profile. The engine contributes no gate definitions and no commands.

Whether the existing `GatePipeline` also *runs* them is deliberately left to the first task, because
that pipeline is built for merge verification: it carries retry policy, baseline-diff scope checks
and new-API-surface detection, none of which a section gate needs. Two outcomes are acceptable —
reuse it with a restricted gate set, or run the resolved steps directly — and the deciding question
is whether the pipeline can be pointed at one tree and a subset of gates without inheriting merge
semantics. What is **not** acceptable is a second source of gate configuration.

### D5 — Stop points are conditions, not a "waiting for human" flag

A unit set aside records a *named resume condition*. A human decision is one kind; the availability
of an external system is another. This came from the third prospective consumer of the engine, whose
stop is not a person at all — had the abstraction said "awaiting human", that consumer would have
been excluded by a word.

### D6 — The answer path is a connector, and its failure modes are designed in

Answers arrive as documents in a directory, keyed *inside* the document on change and task. The
engine never knows who wrote them: a chat bridge, the framework's surface, or a person with an
editor. Three properties are not optional, because all three were measured breaking in production:

- **Deferral before quarantine.** A document that will not parse is treated as an in-flight write and
  retried; only after a bounded number of attempts is it quarantined. Quarantining on first failure
  buries a human decision over a timing accident — six documents sat quarantined that way.
- **Names carry source and time.** The key lives inside the document, so the filename is free — and
  therefore two uploaders can silently overwrite each other. Named by source and timestamp, they
  cannot. The engine tolerates several documents for one key: newest wins, the rest are retained.
- **Consumption is stamped, not inferred.** Directory state lied in both directions where this was
  measured: consumed answers still present, unconsumed answers taken for processed. Eighteen answers
  sat unconsumed, three of them answered the same day.

### D7 — Intake at the entry point, and stop handling in the engine

Pending answers are taken in at the engine's entry point on every path — running a unit, asking what
is runnable, reporting state. Not in one command variant.

*Why so specific:* in the proven engine the correct behaviour existed but lived in the rarely-called
command, so in practice questions went unanswered while the code that answered them was right there.
A behaviour that only some entry points have is, statistically, a behaviour the system does not have.

### D8 — Additive path, existing loop untouched

The new engine is a second entry point. The change-granular loop keeps its behaviour, including its
current treatment of human-marked tasks, for the whole parallel period. Nothing in this change edits
its specs: measured, no existing spec states any behaviour for human-marked tasks at all — 0 hits
across 436 spec files, of which 376 contain SHALL — so there is nothing to contradict, and the two
paths can coexist without a spec conflict.

### D9 — The seat is session-scoped and validated, not trusted

The lock records a seat identifying one agent session. A seat that names only the project is refused
at the point it is recorded, rather than being accepted and misinterpreted later. This is a direct
inheritance of a defect measured in the proven engine, where a project-scoped seat matched seven live
sessions and the answer woke the wrong one.

### D10 — Separate package, own entry point, and the dependency points one way

The engine lives in its own top-level package (`lib/set_workcycle/`) and ships its own command entry
point. It is not a module inside the orchestration package, and it adds no operation to the
orchestration change-control routes.

*Why, stated as a requirement rather than a preference:* **`set_workcycle` may import from
`set_orch`; `set_orch` may not import from `set_workcycle`.** That direction is the whole point — it
means orchestration continues to work with the engine deleted, and it can be asserted by a test
rather than promised in a comment. Co-locating the code would make the reverse import trivially
available, and a dependency that is easy to add gets added.

*What this does not claim:* the two are unrelated. The engine reuses gate configuration, event
plumbing, path resolution and task-file parsing from orchestration, and the surface will show both on
one screen. Sharing machinery and sharing a namespace are different decisions, and only the second
one is being refused.

*Alternative considered:* `lib/set_orch/work_cycle/` as a sub-package. Rejected because a sub-package
inherits the parent's name in every import, log line and traceback, so the separation would hold in
the directory listing and nowhere a reader actually looks.

## Risks / Trade-offs

- **The common abstraction has to be right first time, across two lanes with no shared code.** →
  Mitigated by shipping only the slice lane while the *unit* concept carries all three; the phase
  lane rides a proven core rather than a theoretical one. The residual risk is real and is the
  explicit consequence of a scope decision taken with the risk stated.
- **A freeze on the other implementation makes delay expensive.** Their engine takes bug fixes only
  from now on, so every week this drags costs them capability. → The slice lane ships first for
  exactly this reason, and an escape hatch exists: a capability that cannot wait is authorised
  individually and booked into this engine's scope so it is not silently forgotten.
- **`GatePipeline` may not be reusable at section granularity.** → Decided by measurement in the
  first task, with both outcomes acceptable; only the gate *configuration* source is fixed in
  advance.
- **A section gate is weaker than a merge gate, and could look like the same assurance.** → The
  engine records which gate ran and reports "no gate" as a distinct state from "gate passed". A
  project declaring no gate steps runs with none, rather than with a guessed default.
- **The engine writes to a project's task file** (marking tasks as awaiting a human). → Marking is
  the only mutation permitted; reformatting or rewriting the file is out of scope, and the verdict
  diff exists precisely to catch a run whose claims and the file disagree.

## Migration Plan

1. Ship the slice lane behind its own entry point. The existing loop is untouched, so nothing that
   works today changes.
2. Run it on this repository first — a change of this framework's own, with group dependencies.
3. Then the crossing: run **the same change on the consumer's tree** with the framework engine, and
   compare against what their engine did. The evidence is a real run — a non-trivial change with
   group dependencies and at least one human stop — not a green test suite. A test proves the
   mechanism; only the run proves the result.
4. Their engine retires when that evidence exists, not on a date.

**Rollback:** the engine is an additive entry point with its own lock and its own state. Not calling
it restores the previous behaviour exactly; there is no migration of existing state to undo.

## Open Questions

- **Is a lens an attribute or a fan-out?** D2 decides "attribute" and states why; it is with the
  consumer whose engine runs lenses today. If the join needs engine support, the change is additive.
- **Can `GatePipeline` be pointed at one tree and a gate subset without inheriting merge semantics?**
  First task, by measurement.
- **Where does a session-scoped seat come from in a headless run?** An interactive session has a
  native record; a run started by the framework's surface has to be given one. Whatever invokes the
  command must therefore supply a seat rather than let the engine invent it — noted here because the
  specs require the refusal, not the origin.
