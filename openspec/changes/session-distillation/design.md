## Context

The framework used to ship a memory subsystem that wrote itself. It was removed after a
measurement, not after a disagreement about taste: over 21 days and 4958 transcripts, 187 memory
lines reached a session and **168 of them (89.8 %) were `User frustrated` records**, produced by
a detector that fired on exclamation marks. Exactly one line in 187 was a reusable fact. The
same write path also persisted meeting-transcript content, which is the confidentiality carrier
the framework's own rules name.

Seven capabilities went with it. The user has asked for **one** back — the automatic session-end
extraction — and asked for it in a different shape: **distillation**, not capture.

What exists now, and what this design must not disturb:

- The memory layer is the runtime's own per-repository directory, indexed by `MEMORY.md`. The
  framework ships no store and must not introduce one.
- Only the first **200 lines / 25 KB** of that index is injected at session start, and nothing
  warns past the cut. Measured 2026-08-22 across the indexes on one development machine: the
  largest is **123 lines / 20 550 bytes** — already 82 % of the byte budget.
- A private-slug list exists and is resolved **at run time** from the project registry, with an
  allowlist for deliberate exceptions. A pattern file committed to a public repository would
  itself be the leak.
- The runtime exposes a `SessionEnd` hook event alongside `Stop`, `SubagentStop`,
  `SessionStart`, `PreCompact` and the tool events. Measured against the official hook
  reference on 2026-08-22; the development machine's own settings register only `Stop` today.

## Goals / Non-Goals

**Goals:**

- Restore one capability — a pass that reads a **finished** session and records what was learned.
- Make every way the old system failed a **refusal** in this one: a state claim, a harness
  artifact, a repo-derivable fact, a confidential name, an over-budget index.
- Keep the output in the native layer: one file per fact, one index line, no second store.
- Make a run's completion measurable from outside it.

**Non-Goals:**

- The six capabilities deliberately not replaced (semantic search, tag filtering, temporal
  queries, full-text search, cross-device sync, version history). Each is its own change,
  measured against the native layer rather than against a vacuum.
- Distilling anything live. A session still running is not a source.
- Any judgement about the user's state, at any confidence, under any name.

## Decisions

**D1 — The trigger is `SessionEnd`, and the alternative is not merely worse, it is the measured
cause.** `Stop` fires at the end of every assistant turn, so a hook hanging off it observes the
prompt in flight; that is how a task notification became "the user is frustrated". `SessionEnd`
fires once, when the transcript is complete. *Alternatives considered:* `Stop` with a filter —
rejected, because the filter is exactly the component that was wrong last time, and its failure
direction is to write something rather than nothing. A manual command only — rejected as the sole
carrier, because the user asked for the automatic pass; it remains available for a re-run.

**D2 — The hook enqueues; it does not distil.** The `SessionEnd` hook writes one small entry
(transcript path, project slug, timestamp) and exits. Reading a transcript or calling a model
inside an exit hook puts unbounded work in a time-bounded place, and its output reaches nobody.
*Alternative:* distil in-process at session end — rejected: a long session would either block the
exit or be truncated, and a truncated distillation is indistinguishable from a clean one.

**D3 — Refusal over redaction, everywhere.** Each gate drops a candidate whole rather than
editing it into acceptability. Redaction is where extension weakens protection: a chain that
returns as soon as one rule matches stops the built-in rule from running on what is left, and the
resulting document can *gain* the name it was meant to lose. A candidate that trips any gate is
simply not written, and the trace says which rule decided.

**D4 — The confidentiality list is borrowed, never copied.** The gate calls the existing
runtime-resolution path (registry + allowlist) as a library. A second list is a second copy, and
a second copy drifts at the moment it is written — the failure this repository has already paid
for with a hand-named import-root list. The matched value is never echoed into a log or a
refusal message; log the shape, not the content.

**D5 — Both budgets are refusals with measured numbers, not warnings.** Append stops at 150
lines / 20 KB, below the 200 / 25 KB cut, and the refusal reports the measured size. A warning
here is worthless: the failure it warns about is silent by construction, so nobody is watching
when it fires.

**D6 — A run is retired against its trace, never against its report.** The distiller writes a
machine-readable trace naming the transcript, each candidate's disposition with the deciding
rule, and every path written. The queue retires an entry only when that trace exists and names
it. This is not defensive paranoia: an unflagged subprocess asked to create a file has been
measured replying `Done.` with exit 0 while the tool layer refused the write and the agent never
knew.

**D7 — Deduplicate against the existing index before writing.** An admitted fact that an existing
memory already covers updates that file; the index does not grow. Otherwise the budget in D5 is
consumed by restatements, which is how an index reaches its cut without ever learning anything.

## Risks / Trade-offs

- **The distiller is itself a model call, so it can hallucinate a "fact".** → Every write is
  attributable in the trace, and admission requires the candidate to name where in the session it
  came from. A candidate that cannot point at its source is refused.
- **Queue entries accumulate if the distiller never runs.** → Entries are small and idempotent;
  repeated failure moves an entry aside with its reasons preserved rather than retrying forever
  or deleting it. A deleted entry and one that never existed are indistinguishable.
- **Two sessions in the same project can finish at once and race on `MEMORY.md`.** → The append
  is the only shared write; take a POSIX-atomic lock around it, and re-measure the budget inside
  the lock rather than before it.
- **A refusal rate near 100 % looks like a broken distiller.** → It is the expected shape: the
  system this replaces admitted one useful line in 187. The trace makes the difference visible,
  because a distiller refusing candidates and one producing none look identical from outside.
- **The confidentiality gate can only refuse what it can recognise.** → It covers the registry's
  slugs and the allowlist; a partner name that appears nowhere in the registry is not detectable
  by it. This is a stated limit, not a covered case: the admissibility gates (D3) are what keep
  consumer-derived *content* out, and the slug list is the backstop, not the guarantee.

## Migration Plan

1. Ship the queue and the hook first; with no distiller registered, the only effect is a growing
   queue that nothing consumes — safe, and it proves the trigger fires where it should.
2. Run the distiller by hand over queued entries and read what it proposes, before anything is
   automatic. The pass condition is not "it wrote memories" but "every line it wrote is one a
   person would have written".
3. Only then wire the automatic run.
4. **Rollback** is deletion of the hook registration; the native memory layer is unaffected,
   because nothing else in the framework depends on this queue.

## Open Questions

- **Who executes the distillation pass** — a scheduled framework process, or the next session in
  that project picking up its own queue. The second needs no new daemon and is the current
  preference, but it means a project that is never opened again is never distilled.
- **Whether the framework deploys this to consumer projects by default** or only on an explicit
  opt-in. The confidentiality gate makes it defensible; the fact that it writes into a
  developer's own memory index argues for opt-in.
