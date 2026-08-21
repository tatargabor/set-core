## Context

The engine already closes the loop on this side of the machine: a unit reports an open
decision, `cli.py` marks the task awaiting with `connector.mark_awaiting`, the awaiting task
holds the groups that **declare a dependency** on it (`groups.py` — an awaiting group is
*skipped*, not blocked behind, so unrelated later groups stay runnable), an answer dropped
into the tree is taken in on every entry path and released into the next run's prompt.

Only the middle step is missing: nobody is told. This design is about that step and nothing
else.

⚠ **This document was rewritten on 2026-08-21.** Its first version was reviewed
adversarially by three independent passes and much of it was refuted — the corrections are
listed in `proposal.md`. Two of them changed the shape of the design rather than a detail:
**set-core's notification module speaks in both directions** — `lib/set_orch/discord/`
turns three hard-coded emoji into run-completion actions — and **the answer pickup already
exists** in `lib/set_workcycle/connector.py`, specified by `deferred-work-connector` in
`work-cycle-engine-apply-first`.

⚠ A second review corrected the first correction, and the distinction decides a design
question rather than a detail: that Discord path **carries no identity**. Its payload has no
run id, no change, no task, no message id; the handler filters on the emoji alone; and
`completion_message_id` is written at `events.py:346` under a comment saying it is kept "for
the reaction handler" and is **read nowhere**. So there is no question, no option list and no
correlation in it to generalise. Reusing it is not cheaper than writing an outbound; it is a
different job, and it is not assumed here.

The constraint that shapes the rest: **set-core is a framework and the question text is a
project's domain.** The framework may route a question; it may not read it, interpret it,
translate it, or keep it anywhere but the project's own register.

## Goals / Non-Goals

**Goals:**

- A question raised by a work cycle reaches a human through an outbound the *project*
  declares and the *operator* has enabled.
- A second, unrelated outbound can satisfy the same contract without knowing the first exists.
- A question cannot be lost, cannot be silently duplicated, and cannot be silently unheard.
- Nothing about it can fail the cycle it is attached to.

**Non-Goals:**

- **No outbound implementation.** Whether the existing reaction-driven path in
  `lib/set_orch/discord/` becomes the first conforming outbound is a later decision.
- **No answer pickup** — `deferred-work-connector` (in `work-cycle-engine-apply-first`).
- **No masking.** What may leave the machine is decided where the text becomes a message.
- **No new question vocabulary.** `- [?]` already exists in this engine and already carries
  the blocking semantics. ⚠ `[input:KEY]` and `[confirm]` do **not** — they belong to a
  different subsystem (`lib/set_orch/loop_tasks.py`), which the work cycle neither reads nor
  writes. An earlier draft named all three as if they were already integrated.

## Decisions

### D1 — The register is the awaiting task; the outbound is a convenience

The question exists the moment it is marked awaiting. Whether anybody carried it anywhere is
a separate fact. A hand-off failure is reported and never raised.

*Why:* a chat outage must not stop development, and the outbound must not become a second
place where the truth lives. Two registers drift, and the copy is the one that drifts.

### D2 — But "convenience" must not become "silence"

D1's first version combined *best-effort* with *handed over once* and produced a trap the
review found: a hand-off that fails at 01:00 is reported into a log nobody reads, and every
later run reports the question as "outstanding" — true, and read as *a person has it*.
Nobody has it.

So the state is three-valued, not two: **not yet handed over**, **handed over**, **handed
over and failed every attempt**. Only the second suppresses a re-send; the third is retried
and is reported as an *unheard* question, distinct from one awaiting a person.

### D3 — An outbound requires an operator opt-in, not only a project declaration

`lib/set_orch/project_status.py:936-951` sets the bar for what a project may declare as a
write command, and says why the bar has to be restated rather than trusted:

> The first write was acceptable because it appends to a file in the project's own
> repository, and is therefore *structurally* incapable of reaching a live system: no
> network, no database, no deployment. That is the bar. […] it survives only as long as
> someone restates it at the moment a second kind of write is proposed.

**This change is that moment, and the first version of this design did not restate it.** A
question outbound reaches something outside this machine, so a project declaration alone is
not sufficient authority. The declaration lives in the project's tree, which is writable by
the very work unit that just ran; the opt-in therefore lives with the operator, outside that
tree. Without it, a unit that edits its own configuration selects the command the framework
will spawn next, with the framework's environment.

### D4 — The framework never invents `audience`; the project may default it

`audience` is required and the framework supplies no value of its own. A project may declare
a fail-closed default: the working implementation defaults apply-side questions to its
developer audience and **never** to its client audience, because a night-time outbound would
otherwise jump the decision order. That is a safety mechanism, and an earlier draft of this
design would have forbidden it by insisting nobody may default the field. The rule is about
**who** may decide, not about whether a default exists.

### D5 — Options are structured; the display string is derived and never parsed back

Measured on the working implementation: a joined form cannot be split back safely, because
the separator can occur inside an option. Same class as a name that is a second copy of the
content — the derived form drifts and is the one that gets read.

### D6 — The envelope carries no local path

The envelope is handed to something that posts where people can read it. An absolute path
publishes the account name, the machine layout and the project's directory name — the
name-leak the confidentiality rule forbids, running in the one direction a commit scan cannot
see. So the answer's destination is expressed in a form the framework resolves locally, and
the envelope carries no filesystem path.

### D7 — The outbound is resolved from declaration, not imported

Who carries a project's questions is read from configuration, the same way its status-contract
commands already are. set-core holds no reference to any particular outbound — which is also
what keeps a private project's name out of a public framework.

*What this inherits and what it does not:* `project_status.py` surrounds its command
resolution with guards this design must restate rather than assume — a separate write-command
allowlist, refusal of values that look like flags, and logging that records the length of
stderr and never its content. ⚠ **The output cap is NOT among them on the write path**: 
`MAX_OUTPUT_BYTES` is enforced on the read path only, and the write path parses the child's
output with nothing between. A guard cited as inherited that does not exist on the path being
generalised is worse than no guard, because it stops anyone looking. It passes the full
environment to the child; that is a decision to be made here, not inherited by silence.

⚠ **And the opt-in is a restatement, not a new decision.** The passage quoted above already
ends *"must not be declared here without the operator deciding so explicitly"*. This design
does not invent the requirement; it is the first change that had to honour it.

### D8 — The bus is an accelerator, and its delivery is once per agent

A bus notification may be sent. Nothing may depend on it.

Measured 2026-08-20: an entry addressed to a stopped seat is kept on disk although nothing is
woken, and a seat created that day was handed 8 entries, the oldest 11 days old. So an entry
is **not lost**. Measured 2026-08-21, and it narrows that result: `store.mjs:1325-1361` seeds
a newly born seat's cursor from the furthest read across that agent's past seats, floored at
one hour for a sibling writer. **Delivery is therefore once per agent, not once per session:**
an entry read by a session that dies without acting is gone for that agent.

*Consequence:* the bus may carry a nudge; the record of whether a question was handed over is
the hand-off's own outcome, never the notification.

⚠ *Corrected from the first version:* it claimed `lock.py` "already carries" run scoping for
answers. It does not — `lock.py` is a per-tree mutex keyed on a session seat, with no run
identity. Answer scoping is by awaiting-key set, and it belongs to `deferred-work-connector` (in `work-cycle-engine-apply-first`).

## Risks / Trade-offs

- **The opt-in is friction** → it is friction exactly once per machine, and it is the only
  thing standing between a project-writable config file and an automatic network call.
- **`audience` is only as good as the project that sets it** → the framework cannot check a
  vocabulary it does not own; it can only refuse to invent one and refuse to send without one.
- **Retry can become spam** → the retry is bounded and its state is per question; the
  three-valued state in D2 is what makes "already handed over" a real suppression rather than
  a guess.
- **The framework routes text it must not keep** → the question body goes to the outbound and
  into the project's own task file, and nowhere else. Every free-text field is enumerated for
  the logging rule, because naming only "the question" and "the answer" already missed one.

## Migration Plan

Nothing to migrate. A project that declares no outbound, or an operator who has not opted in,
behaves exactly as today: the question is marked awaiting and nobody is told. The existing
implementations keep working; D7 only asks that the path they hard-code be declared, and the
opt-in is a new setting rather than a change to either of them.

## Open Questions

Asked of the existing implementation on 2026-08-20 and still open. The bus question that
stood first here has been answered by measurement (D8).

1. **Field names.** set-core is public and English; the working implementation's fields are
   mixed-language. Which side carries the mapping?
2. **The `audience` vocabulary.** Does the contract fix the values, or require the field and
   leave the vocabulary to the project?
3. **Identity.** The working key has no project segment, because the answer directory sits
   inside the project. An outbound serving several projects needs one.
4. **How the answer's destination is expressed** without a path (D6), in a form a second
   outbound can satisfy.
5. **From the review:** does the existing reaction-driven path in `lib/set_orch/discord/`
   become the first conforming outbound, or stay as it is? ⚠ Answer it on the measurement,
   not on the first impression: it has three fixed emoji, no question, no option list and no
   correlation between the reaction and what it is answering. Making it conform is closer to
   writing an outbound than to generalising one.
