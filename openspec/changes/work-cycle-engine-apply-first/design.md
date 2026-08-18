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

⚠ **The strategic frame, stated by the user and easy to lose at a context boundary.** The framework's
orchestration engine **is not currently being developed and is out of date** — the intent is to
rewrite it, not to preserve it. The consumer project carries **the current foundation of how
development is actually done**, but has not raised it to orchestration. So this engine is not a
feature bolted onto a healthy orchestrator: it is **the foundation the future orchestration will be
rebuilt on**. Two consequences follow, and neither is optional. The additive path in D8 is a
*transition*, not a permanent shape — the existing loop is kept alive while there is nothing better,
not because it is the destination. And the order of work is fixed: the modern foundation is brought
over first, and orchestration is rebuilt **on top of it** afterwards — never the reverse, which would
mean fitting a proven foundation into a shape that is itself being replaced.

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
- Building the fix lane. It is **scheduled for the next round, not dropped** — and the abstraction is
  deliberately shaped to receive it: the unit kind is an attribute, so the fix lane adds unit kinds
  rather than a second engine. Anything in this design that would have to change to admit it is a
  design error, not a future task.
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

**Measured (task 2.1), and the answer is outcome two: run the resolved steps directly.** The
question was whether `GatePipeline` (`gate_runner.py:216`) can be pointed at one tree and a subset
of gates without inheriting merge semantics. Both halves of the pointing work and needed no change:
the tree reaches it through `change.worktree_path` alone (11 accesses, no other source), and a
subset is just `GateConfig(gates={...})` plus registering what you want. The three behaviours this
paragraph originally suspected — retry caching, baseline-diff scope, new-API-surface detection — are
**inert on a first run**: the first two return early while `verify_retry_index == 0` (`:449`, `:505`)
and the third is reachable only from inside the first. They were the wrong suspects.

What cannot be shed is **state**. `GatePipeline` writes orchestration state from 9 call sites, and
its failure path is unconditional: measured end to end on a scratch repository, one failing gate left
the change at `status: "failed"`, `test_result: "fail"`, `last_gate_commit: <sha>`. So a *section*
gate going red would record the whole *change* as having failed verification. Pointing `state_file`
at a scratch file is refused rather than unavailable — it would be a second store of run state, which
`work-cycle-control` forbids.

So the engine reuses the gate **configuration** chain, `resolve_gate_config(change, profile, …)`,
and the state-free types around the pipeline — `GateResult`, `GateDefinition`, `_resolve_gate_order`,
`_truncate_gate_output`, all verified to write no state — and runs the resolved steps itself. What is
**not** acceptable, and remains so, is a second source of gate configuration.

**⚠ Amended 2026-08-19, by the first live crossing run, and the amendment is the interesting part.**
The paragraph above says the engine's gate steps come from the resolution chain and that a second
source is unacceptable. Shipped behaviour no longer matches it: an adopted project's own
`set/work-cycle.yaml` `gates:` list is read **first**, and the chain is consulted only where that key
is absent. The design was written before adoption had a gate key at all, and it was not revisited
when adoption gained one — so the consuming project declared two gate commands, the engine printed
them in `describe()` and ran something else. A declared guard that does not take effect is the very
defect this change exists to forbid, one layer up, on itself.

The prohibition survives in the form that carries its reason. What D4 was protecting against is two
*framework* sources that must be merged, because a merge is where drift hides. A project's own
declaration is not that: it is **whose** declaration, and it wins outright with no merge —
declared → run exactly those; declared empty → no gate; not declared → the chain. Precedence, not
combination. The engine still contributes no gate command of its own, which was always the real
claim (`test_the_engine_package_names_no_gate_command_of_its_own`).

**Measured (task 2.2) — the event stream.** `chat.py` is the framework's **only** live stream
consumer. `grep -rln "stream-json"` returns 7 files and six of them do not consume a stream: five
redirect stdout to a file (`supervisor.py`, `fixer.py`, `investigator.py` — the last reading only the
first line, for `session_id`) and two parse already-complete content. There was no synchronous
consumer to adopt.

Extractable from it: `_map_event` (`:250`, 41 lines, pure `dict`→`dict`; its only `WebSocket` mention
is in the docstring), the invocation shape `claude -p --output-format stream-json --verbose --model`
with `resolve_model_id`, and — answering this design's third Open Question — the `system`/`init`
event carrying `session_id` (`:181`), which is where a headless run's session-scoped seat comes from:
read off the agent process the engine itself started, never invented. Re-expressed rather than
extracted: the async framing. `_run_claude` is 126 lines of which roughly a hundred are chat's own
(broadcast to a `set[WebSocket]`, generation guard, history, stale-session retry); the reusable
mechanic is a blocking `Popen` line loop with a per-line `json.loads` that logs and continues on a
non-JSON line rather than dying.

The full evidence, with commands, is in this change's `measurements.md`.

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
- ~~**Can `GatePipeline` be pointed at one tree and a gate subset without inheriting merge
  semantics?**~~ **Answered by measurement (task 2.1) — see D4.** It can be pointed at both; it
  cannot shed its orchestration-state writes, so the engine runs the resolved steps itself.
- ~~**Where does a session-scoped seat come from in a headless run?**~~ **Answered by measurement
  (task 2.2) — see D4.** From the `system`/`init` event on the agent process's own stream
  (`chat.py:181`). The engine reads the seat off the session it started; it neither invents one nor
  needs the caller to supply it. The refusal the specs require is unaffected: a seat that names only
  a project is still rejected.
