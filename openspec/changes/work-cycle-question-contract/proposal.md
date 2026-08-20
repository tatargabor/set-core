## Why

When the work-cycle engine runs a section and the work needs a person, the engine already
knows it: the section returns `NEEDS_INPUT`, the question is written into `tasks.md` as a
`- [?]` task, and every group that depends on it is held back
(`lib/set_workcycle/verdict.py:50`, `lib/set_workcycle/groups.py:124`). What happens next is
nothing. The run stops and waits for somebody to read a file.

That is cheap in the daytime and expensive at night, which is when these cycles are meant to
run: a cycle that meets one question at 01:00 does no further work until a person opens the
repository in the morning. **The night is the thing being lost, not the minute.**

A project on this machine has already solved it, end to end, and the solution has been in
daily use long enough to have measurements rather than opinions. It routes the question to a
human channel with options as buttons, and writes the answer back. Two of its findings are
worth more than its code, because both are counter-intuitive and both were measured:

- **The question must not travel as an ordinary agent message.** Sent that way it became an
  item in a queue in 11 minutes and was still undecided **25.4 hours** later. Carried by the
  purpose-built path it came back answered in **2 minutes 10 seconds**.
- **The answer's primary carrier is a file, and the message bus is only the fast one.** An
  agent bus is live sessions talking to each other; if no session is running, the entry
  settles. An answer arriving at 03:00 for a session that has since exited is exactly the
  night this exists to save.

set-core should not adopt that implementation. It should adopt its **shape**, as a contract
any project can satisfy with an outbound of its own — its own chat channel, its own bot, its
own on-call tool. The framework supplies the envelope and the plumbing that unblocks the
`- [?]`; who carries the question to a human, and how, stays outside.

## What Changes

The shape below is **taken from a working implementation on this machine, read directly**
rather than negotiated — see *The working model, measured* at the end. Where this change
departs from it, it says so and why.

- **A versioned question envelope**, domain-free, produced when a section returns
  `NEEDS_INPUT`. It carries the identity needed to write the answer back, the question text,
  an option list, an audience, and where the answer is expected.
- **The option list is structured, never a joined string.** Measured on the working
  implementation: a display string built by joining options **cannot be split back safely**,
  because the separator can occur inside an option. Machine input and display are two
  fields, not one.
- **`audience` is required and the FRAMEWORK never invents it.** The project may declare a
  fail-closed default — the working implementation defaults apply-side questions to its
  *developer* audience and never to its *client* audience, because a night-time outbound
  would otherwise jump the decision order. What the framework must not do is supply a value
  of its own, and an outbound that receives no audience refuses to carry the question.
- **A declared outbound**, resolved the way the status contract already resolves a project's
  commands. set-core ships **no outbound of its own** — not a chat client, not a bot. The
  existing notification module in this repository speaks in one direction only and is not
  extended here.
- **The outbound is best-effort and can never fail the cycle.** Measured, and stated in the
  working implementation as a rule: *the outbound is a convenience, not the register.* The
  question stands in `tasks.md` whether or not anyone carried it anywhere, and a failed
  hand-off is reported, not raised.
- **A durable answer pickup.** The answer arrives as a file in a framework-owned directory
  inside the asking project's tree; the pickup writes it into the task and clears the
  `- [?]` so the held groups run — reusing `lib/set_workcycle/prompt.py`'s existing
  `answers` route rather than a second one beside it.
- **The key is a field, not a filename**, and files whose key the reader does not recognise
  are **left untouched**. Both measured: the working implementation shares one answer
  directory between two readers, and its own comment names the failure that rule prevents —
  *tidying away what is not ours is exactly the silent data loss the mechanism was built
  against.* Malformed answers are quarantined, not deleted.
- **Answers are scoped to the run that asked.** `lib/set_workcycle/lock.py` already carries
  the measured lesson: an answer meant for one run once woke a different one.

**Not in this change:** any outbound implementation; any surface that displays pending
questions; masking or redaction of the question text, which belongs to whoever carries it
out and is measurable only there.

## Capabilities

### New Capabilities
- `human-question-contract`: the versioned envelope for a question raised by a work cycle
  and for its answer — identity, text, options, audience, answer path — plus the rules that
  make it safe to read: the framework never invents a value, a missing audience is a
  refusal rather than a default, and nothing from the envelope is persisted outside the
  project that owns it.
- `question-outbound-binding`: how a question reaches a declared outbound and how its answer
  returns — the declaration that names the outbound, the bus notification carrying a
  pointer, the file that is the durable carrier, and the pickup that unblocks the `- [?]`
  task and scopes the answer to the run that asked.

### Modified Capabilities
<!-- None. `work-unit-engine`, `work-cycle-control` and `task-group-resolution` are the
     natural neighbours, but they live in an open change and have not reached
     `openspec/specs/` yet. This change consumes their behaviour and does not alter their
     requirements. -->

## Impact

- `lib/set_workcycle/` — `engine.py` (the `NEEDS_INPUT` path), `groups.py` (clearing a
  `- [?]`), `prompt.py` (the existing `answers` route), `lock.py` (run scoping).
- A new module for the envelope and the binding, with the outbound resolved from
  configuration rather than imported.
- The agent bus is a dependency of the notification path only. The contract must remain
  satisfiable without it, because the file is the carrier that does not need a live session.
- No change to the existing one-way notification module, and no new outbound dependency.

## The working model, measured — 2026-08-20

Read from the two trees that already run this end to end. Every row is code or a comment in
those trees, not a report of them.

| | what it does today |
|---|---|
| question raised | the section returns `NEEDS_INPUT`; the open `- [?]` tasks of the change are collected into a question list |
| identity | `<change>#<task-id>`, deliberately the same shape another cycle in the same project already used, so the outbound needs one reader rather than two |
| audience | fail-closed on the **project** side: apply-side questions are the developer audience and never the client audience |
| options | a structured list for the machine, a joined string for display — never the reverse |
| hand-off | a **direct process call** with the question list on stdin, and an explicit `--seat` |
| failure of the hand-off | ignored: best-effort, the question is already in `tasks.md` |
| answer | a file in the asking project's framework-owned directory, overridable by environment variable, with a fallback into the outbound's own tree **that announces itself** |
| answer key | a field inside the JSON, not the filename |
| foreign answers | another reader's entries share the directory and are left untouched |
| bad answers | quarantined into their own directory with a reason, never deleted |

## Open questions

### 1. The bus — MEASURED 2026-08-20, and the objection was about the wrong thing

The user's instruction is that set-core notifies the outbound **over the agent bus**. The
working model deliberately does not, and the outbound's own stated reason (2026-08-08) is
that if no session of it is running, the entry **settles** — *and that is exactly the night
the chain was built to save.*

That objection was tested here rather than believed or dismissed. Two halves, both measured:

| | how it was measured | result |
|---|---|---|
| does an entry for a **stopped** seat survive? | opened a two-seat room with a seat last seen two days earlier, sent one entry, then looked at the store | the entry is on disk in an append-only per-writer file; the send reports `wakes: []` — **nobody was woken and it was kept anyway**; the recipient has no read cursor in that room, so the entry sits ahead of it |
| does a seat that **arrives later** get what was written before it existed? | a seat created today read a room it had never been in | **8 entries handed over, the oldest 11 days old** — all written before this seat existed |

**So the entry is not lost.** The 2026-08-08 objection describes *loss*, and loss is what
justified rejecting the bus for the question direction. What the measurement leaves standing
is **latency**: delivery happens when a session of that agent next reads the room, and if
none runs until morning, the question waits until morning.

That is a materially smaller claim than the one on record, and it changes the decision:
a bus notification is safe to build against, and the thing that still has to be solved is
**how soon somebody reads**, not whether the question survives. The direct process call
remains the low-latency path; it is not the only one that is safe.

⚠ What is still NOT measured: whether a new session of a given agent **automatically** reads
its rooms. That depends on that project's own session hook and its declared default rooms,
not on the bus. A contract that assumes it would be assuming something about the recipient's
configuration.

### 2. Still to settle with the existing implementation

Asked on the bus on 2026-08-20; the answers change what gets built.

- **Field names.** set-core is public and English; the working implementation's fields are
  mixed-language. Which side carries the mapping?
- **The audience value set.** Does the contract fix the values, or only require the field
  and leave the vocabulary to the project?
- **Identity.** The working key has no project segment, because the answer directory sits
  inside the project. A shared outbound serving several projects needs one. Does the project
  segment belong in the key, or does the outbound derive it from where the question came
  from?
- **Where the answer lands for an arbitrary project**, so a second outbound can satisfy the
  same contract without knowing the first one exists. Today this is an environment variable
  and one hard-coded path.
