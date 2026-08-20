## Context

The work-cycle engine already recognises that a section needs a person: it returns
`NEEDS_INPUT`, the question is written into `tasks.md` as a `- [?]` task, and every group
that depends on it is held (`lib/set_workcycle/verdict.py:50`,
`lib/set_workcycle/groups.py:124`). Nothing carries that question to anybody, and nothing
brings an answer back, so the cycle stops until a person opens the repository.

Two trees on this machine already close that loop, in daily use. This design takes their
**shape**, read directly from the code, and turns it into a contract that a second
implementation could satisfy without knowing the first exists. What it must not do is
require either of them to change how it works.

The constraint that shapes almost every decision below: **set-core is a framework and the
question text is a project's domain.** The framework may route a question; it may not read
it, interpret it, translate it, or keep it.

## Goals / Non-Goals

**Goals:**

- A question raised by a work cycle can reach a human through an outbound the *project*
  declares, and its answer can come back and release the held groups.
- A second, unrelated outbound — someone's own chat channel — can satisfy the same contract.
- The mechanism cannot lose a question, cannot lose an answer, and cannot silently discard
  somebody else's.
- Nothing about it can fail the cycle it is attached to.

**Non-Goals:**

- **No outbound implementation.** Not a chat client, not a bot, not a poller. The one-way
  notification module already in this repository is not extended.
- **No masking or redaction here.** Deciding what may leave the machine is measurable only
  where the text is turned into a message, which is the outbound's own filter. The framework
  carries the fields the outbound needs to record what it masked; it does not mask.
- **No surface.** Displaying pending questions is a separate change.
- **No new question vocabulary.** `- [?]`, `[input:KEY]` and `[confirm]` already exist and
  already carry the blocking semantics. A second notion of "a question" would be the failure
  this project keeps writing rules about.

## Decisions

### D1 — The register is `tasks.md`; the outbound is a convenience

The question exists the moment it is written into `tasks.md`. Whether anybody carried it
anywhere is a separate, best-effort fact. A hand-off failure is reported and never raised.

*Why:* taken from the working implementation, which states it as a rule in its own code.
The alternative — treating the hand-off as part of the cycle — makes a chat outage stop
development, and makes the outbound a second place where the truth lives. Two registers
drift, and the one that drifts is always the copy.

### D2 — The answer's carrier is a file; the bus is the fast path

The answer arrives as a file in a framework-owned directory inside the asking project's
tree. A bus message may also arrive and may arrive first; it is an accelerator, never the
record.

*Why:* a file waits for a machine that was switched off. This is the working
implementation's decision and the measurement behind it is not ours to re-derive.

*Alternative considered and rejected:* the bus alone. See D3 — it does not lose the entry,
but it delivers on the recipient's schedule, and the record must not depend on that.

### D3 — The bus is safe for the question direction; the objection on record was about loss

The working implementation hands the question over by a **direct process call**, explicitly
not the bus, because (2026-08-08) an entry for an agent with no running session *settles*.

Measured here on 2026-08-20, both halves:

- An entry addressed to a seat last seen two days earlier is written to the store even
  though the send reports `wakes: []`. The recipient has no read cursor in that room, so the
  entry stands ahead of it.
- A seat created **today** read a room it had never been in and was handed **8 entries, the
  oldest 11 days old** — all written before that seat existed.

So the entry is not lost. What remains true is **latency**: delivery happens when a session
of that agent next reads the room. The recorded objection describes loss, and loss is what
justified rejecting the bus; the measurement leaves a materially smaller claim standing.

*Consequence:* the contract may specify a bus notification. It must not specify it as the
only path, and it must not promise when the recipient reads.

⚠ *Not measured:* whether a new session of a given agent automatically reads its rooms. That
is the recipient project's session hook and declared default rooms, not the bus. A contract
that assumed it would be assuming something about somebody else's configuration.

### D4 — The framework never invents `audience`; the project may default it

`audience` is required. The framework does not supply one, and an outbound that receives a
question without one refuses to carry it.

*Why the project, not the framework:* the working implementation defaults apply-side
questions to its developer audience and **never** to its client audience, because a
night-time outbound would otherwise jump the decision order. That is a real safety
mechanism, and an earlier draft of this design would have forbidden it by insisting nobody
may default the field. The rule is about **who** may decide, not about whether a default
exists: a project knows its own audiences, and a framework guessing one is how a question
reaches the wrong person.

### D5 — Options are structured; the display string is derived and never parsed back

The option list is an array. A joined, human-readable string may travel beside it for
display, and is never read back.

*Why:* measured on the working implementation — a joined form cannot be split back safely
because the separator can occur inside an option. This is the same class as a name that is a
second copy of the content: the derived form drifts and is the one that gets read.

### D6 — The key is a field, foreign entries are untouched, malformed ones are quarantined

The answer's key lives inside the answer, not in its filename. A reader that does not
recognise a key **leaves the file alone**. A malformed answer is moved aside with a reason,
never deleted.

*Why:* measured — one directory is shared by two readers today. The working implementation's
own comment names the failure this prevents: tidying away what is not ours is exactly the
silent data loss the mechanism was built against. Deleting a malformed answer destroys the
only copy of something a person typed.

### D7 — The outbound is resolved from declaration, not imported

Who carries a project's questions is read from the project's configuration, the same way its
status-contract commands already are. set-core holds no reference to any particular outbound.

*Why:* this is the whole point of the change. It is also what makes the second
implementation possible, and what keeps a private project's name out of a public framework.

### D8 — An answer is scoped to the run that asked

`lib/set_workcycle/lock.py` already carries the measured lesson: an answer meant for one run
once woke a different one. The pickup honours the same scoping rather than inventing its own.

## Risks / Trade-offs

- **The bus delivers on the recipient's schedule** → the file remains the record (D2), and
  the contract permits a project to keep a direct hand-off as its low-latency path. Nothing
  in the framework requires the bus.
- **`audience` is only as good as the project that sets it** → the framework cannot check a
  vocabulary it does not own; it can only refuse to invent one. The outbound is the place
  that fails closed, and it already does.
- **A shared answer directory is a shared namespace** → D6 makes non-recognition the
  default behaviour rather than an error, so adding a third reader is safe by construction.
- **The framework routes text it must not keep** → the question body travels to the outbound
  and is written to `tasks.md` by the project. set-core persists nothing derived from it:
  no cache, no log line carrying the body, no debug dump. Logging follows the existing rule
  in `project_status.py` — shape, counts and error classes only.
- **A question could be raised for a task that is later edited or removed** → the pickup
  must fail closed: an answer whose task no longer exists is quarantined with a reason, not
  applied to a neighbouring task.

## Migration Plan

Nothing to migrate. The two existing implementations keep working unchanged: they already
satisfy D1, D2, D5 and D6, and D7 only asks that the path they hard-code today be declared
instead. A project that declares no outbound behaves exactly as it does now — the question
stands in `tasks.md` and nobody is told.

## Open Questions

Asked of the existing implementation on 2026-08-20; each changes what gets built, and none
is a detail. The bus question that stood first here has been answered by measurement (D3).

1. **Field names.** set-core is public and English; the working implementation's fields are
   mixed-language. Which side carries the mapping — the contract, or the outbound?
2. **The `audience` vocabulary.** Does the contract fix the values, or require the field and
   leave the vocabulary to the project? D4 decides *who* may set it, not what the values are.
3. **Identity.** The working key has no project segment, because the answer directory sits
   inside the project. An outbound serving several projects needs one. Does the segment
   belong in the key, or does the outbound derive it from where the question arrived from?
4. **Where the answer lands for an arbitrary project.** Today: one environment variable and
   one hard-coded path, with a fallback that announces itself. The framework-owned directory
   in the asking project's tree is the obvious default — but the default has to be stated in
   the contract, not inferred, or the second outbound will infer a different one.
