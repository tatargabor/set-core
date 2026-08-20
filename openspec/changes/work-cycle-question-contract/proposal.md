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

- **A versioned question envelope**, domain-free, produced by the framework when a section
  returns `NEEDS_INPUT`. It carries the identity needed to write the answer back to the
  right task, the question text, an optional option list with a single/multi flag, and the
  path the answer is expected at.
- **A required, framework-uninvented `audience` field.** The question declares who it is
  for. The framework never guesses it, and an outbound that receives a question without one
  **refuses to carry it**. Failing closed is the point: a question with no stated audience is
  a question that could reach the wrong person.
- **A declared outbound**, resolved the way the status contract already resolves a project's
  commands: the project says who carries its questions. set-core ships **no outbound of its
  own** — not a chat client, not a bot. The existing notification module in this repository
  speaks in one direction only and is not extended here.
- **Notification over the agent bus**, addressed to the declared outbound, carrying a
  pointer rather than the question body. The body stays in a file until the outbound's own
  filter has had a chance to mask it.
- **A durable answer pickup** that reads the answer file, records it, and clears the `- [?]`
  so the held groups can run — reusing the answer path the engine already has
  (`lib/set_workcycle/prompt.py`, `answers`), not a second one beside it.
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

## Open questions — being settled with the existing implementation before anything is built

Asked on the agent bus on 2026-08-20; none of the five is a detail, and each changes what
gets built:

1. **Field names.** set-core is public and English; the existing implementation's fields are
   mixed-language. Which side carries the mapping?
2. **The audience value set.** Does the contract fix the values, or only require the field?
3. **Identity.** `<project>/<change>/<task-id>` is enough on its own to write an answer back.
   Does it replace the existing implementation's id/key pair, or sit beside it?
4. **What the bus notification carries** — the whole batch, or a pointer to a file.
5. **Where the answer lands for an arbitrary project**, so a second outbound can satisfy the
   same contract without knowing the first one exists.
