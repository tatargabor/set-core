## Context

The work-cycle engine (`lib/set_workcycle/`, from `work-cycle-engine-apply-first`) is complete
and has driven a real change end to end on a real tree. Everything downstream of *starting* it
works. What does not exist is the half a person touches: nothing on the screen starts a unit,
nothing renders what the engine recorded, and a finished run leaves almost no trace.

Four measurements taken on 2026-08-29 fix the starting point, and they are the reason this
change is scoped the way it is rather than as "build a work-cycle screen":

| # | measured | file:line |
|---|---|---|
| 1 | `grep -rn "fleet/units" web/src` → 0 hits | — |
| 2 | `set-work-cycle` does not resolve on the owner's PATH; it exists only in the repo venv | `fleet.py:1509`, `owner.py:162` |
| 3 | the agent stream is consumed and dropped — `run_agent_session` is called with no `on_event` | `cli.py:369` |
| 4 | the unit record persists neither the session id nor `--started-by` | `engine.py:470` |

**Measured after the first draft, and it moved work out of this change.** Half of "read the
run state" is already built, and specifying it again would have produced a second reader of one
state — the thing the engine's own contract forbids:

- `lib/set_orch/fleet/purpose.py` `read_purposes()` already walks every unit record for a
  project, computes `finished | running | stale` **with pid verification** (`pid_unverified`
  marks a pid held by something that is not an agent, because pids are recycled), carries the
  verdict verbatim, and joins the task file's progress. It crosses the D10 seam by reading the
  JSON rather than importing, with `RUN_STATE_REL` kept as a deliberate second copy.
- `lib/set_orch/fleet/awaiting.py` already parses the engine's awaiting marker, with a second
  copy of the regex and `tests/unit/test_fleet_awaiting.py` failing when the copies diverge.

So the surface work is **extension**, not construction: `Purpose` lacks gate, commit,
set-aside, origin and session, and nothing exposes the runs of a project as a list.

Two constraints from the repository's own rules bind the design rather than decorate it. The
engine may not be imported by `set_orch` (engine design D10), so the surface reaches it by
running its command — which is exactly why measurement 2 is a blocker rather than a nuisance.
And a run's stream is full of the project's domain, so where it is written is a confidentiality
decision, not a storage one.

**One measurement was wrong first, and the correction is part of the design.** This change was
opened believing the unit-start route answers `200` for a command that cannot exec. Probed
directly: `systemd-run` fails immediately (`Failed to find executable`, exit 1), no scope
registers (`LoadState=not-found`), `await_unit` spins its full 40 × 0.1 s, `adopt` raises
`ScopeError`, and the route answers **409 — "did not become active"**. The defect is real and
narrower: a four-second wait ending in a true sentence about the symptom that points away from
the repair. Designing for the imagined false-`200` would have produced a guard in the wrong
place.

**A parallel track is in the same files.** Another session is adding provider/model selection to
the fleet start path, and its measured seam is `owner.py`'s `env=` parameter (the child env has
every `CLAUDE`-prefixed key deleted at line 167, and `env=` is applied at 170). This design must
not fight it — see D1.

## Goals / Non-Goals

**Goals:**

- A start that cannot become the engine is refused by naming the missing command, before
  anything is claimed.
- A run is fully readable after its process, its terminal, and the owner are gone.
- The fleet screen can start a unit, show what the engine recorded, and open a running unit's
  terminal in the project's dock.
- A project may declare where its units read from, without changing how the project works.

**Non-Goals:**

- Chaining units into a loop, reconciling, or any autonomous scheduling. A unit is started
  deliberately; that is the engine's own scope decision and this change does not reopen it.
- A second start path. Everything goes through the engine's single entry point.
- Aggregating, indexing, or searching run streams.
- Changing packaging or how the framework installs its console scripts. D2 explains why the
  fix is resolution rather than installation.

## Decisions

### D1 — Resolve the engine command against the child's env, in the owner, not in the route

The route knows the command name; only the owner knows the environment the child will run in,
and that environment is *computed* (`dict(os.environ)`, `CLAUDE*` keys removed, `env=` applied).
So resolution belongs in the owner, immediately after the child env is final and before
`pty.fork()`.

*Alternatives considered.* **Resolve in the route** — rejected: the route would resolve against
the web service's environment, which is a different one, and the check would pass while the
child still failed. That is the "measure a proxy instead of the thing" class. **Install the
console script onto the owner's PATH and call it fixed** — rejected as the *only* fix: it
repairs this machine and leaves the failure mode intact for every other machine, and the
misattributed error survives. Do both, but the behaviour is the guard.

*Interaction with the parallel provider track:* placing it after `env=` is applied means the
other session's env changes flow into it for free. The seam is one function taking the final
env; whichever track lands first, the other fits without moving it.

### D2 — Refuse before claiming, and release what was claimed

`ScopeError` today arrives after a four-second liveness wait, and its message names the scope.
Resolution failure is knowable before the fork, so it is refused there with the command name and
the PATH it was looked for in. Failures that are *not* knowable in advance (the child dies for
another reason) keep the existing path but report the child's exit status rather than a scope
that did not become active.

*Alternative considered:* keep one error path and improve its wording. Rejected — the wait is
the other half of the cost, and a message cannot remove it.

### D3 — The stream is written by the engine, next to the record, in the project's tree

`run_agent_session` already takes `on_event`. The sink is a JSONL file beside the unit record
under `set/runtime/work-cycle/<change>/`, written incrementally as events arrive.

Three reasons this location and not another. **Confidentiality:** the stream carries the
project's domain, and the framework may persist nothing derived from a consumer's data — the
project's own runtime area is the only place it may live. **Availability:** the engine writes
it, so it exists for a run started from a terminal exactly as for one started from the screen —
a sink owned by the surface would only cover the surface's own runs. **Incrementality:** a
killed run keeps everything up to the kill, which is precisely the run a reader most wants.

*Alternative considered:* have the owner record the pty bytes. Rejected twice over — the owner
is specified to persist nothing (its docstring makes thinness a survival property), and pty
bytes are a rendering, not a record: no session id, no event structure, and terminal escapes.

### D4 — Origin and session id are recorded as facts, with absence stated

`started_by` is accepted by the CLI today and reaches only the response payload; the session id
is read off the stream and used only for a log line. Both join the unit record. Where either is
absent, the record says *not declared* / *unknown* rather than carrying a default. This is the
repository's own "a gap is not a zero" rule: a run whose origin is unknown must not read as a
run nobody started.

Note what this does **not** claim: `started_by` is a caller's assertion the framework does not
verify. The record keeps it as a declaration, and the surface must render it as one — the same
distinction the fleet screen already draws between a `recorded` and an `ancestry` parent.

⚠ **And the origin must be the requester, not the surface.** Measured: the route passes
`--started-by fleet-surface` as a **literal** (`fleet.py:1562`), the same string for every run
the screen starts, while the requesting agent travels separately to the owner as
`requested_by` — which lives only as long as the owner does. So persisting `started_by` alone
would satisfy every test in this change and still leave *which agent started this* unanswerable
the moment the owner restarts, which is the question the change exists for. The route passes
the requester through into the engine's own flag; the constant becomes a fallback used only
when no requester was given.

### D5 — Records are READ; the plan is asked for and cached

Two different questions, and the first draft of this design answered them with one rule and got
the second one wrong.

**What a run did** comes from `set/runtime/work-cycle/<change>/*.json`, read directly. That is
what the engine's contract promises ("readable without a running engine or service"), it needs
no import, and `fleet/purpose.py` already does it — so this half is extending an existing reader
with the fields it does not yet carry.

**What is runnable, and why not** cannot be read that way. It requires the engine's plan —
parsing the task file, resolving `<!-- depends: -->`, and selecting the next group — and all of
that lives in `set_workcycle`, which `set_orch` may not import (D10). So the surface **runs
`set-work-cycle status --json`** and caches the answer, refreshing it on a start, on a finish,
and on a task-file change rather than per poll.

*Alternatives considered.* **A third copy of the group resolver in `set_orch`** — rejected. The
second-copy pattern is established here (`RUN_STATE_REL`, the awaiting regex) and it works
because those copies are a constant and a regex, each guarded by a test that fails on
divergence. A dependency resolver with a fail-closed default and cycle detection is not that
kind of copy; two of them would disagree in exactly the case that matters. **Shelling out on
every poll** — rejected for the reason the framework already wrote down at `fleet.py:1631`: a
process per tile per poll. **Making the whole screen depend on the command** — rejected: the
run list must render when the engine is not installed, which is also what makes D1's failure
mode survivable.

### D6 — A work unit is a first-class inhabitant of the project's dock, not a second terminal system

The owner already holds the unit's pty and labels it `unit-<change>-<seat>`. The dock renders
owner-held terminals. So the unit appears there by construction; what is added is the label's
meaning on screen and the route from a run to its terminal. A finished run opens its persisted
stream in the same place, explicitly marked as a recording — because a recording rendered like
a live terminal is a false value in the shape this repository keeps paying for.

### D7 — Declared reading paths are named to the unit, never read by the engine

The engine passes paths into the prompt; it does not open, summarise, or index them. That keeps
the framework domain-free (it never holds the project's knowledge) and keeps the cost flat. A
declared path that does not exist is reported — a silently dropped path and a project that
declared nothing look identical otherwise, which is the "a filter downstream of a source undoes
it" class.

### D8 — Project rules reach the unit with no declaration at all

Worth stating because it is the question people ask: *how does the unit learn the project's
rules?* It does not need to. A unit runs as a full agent session in the project's tree, so the
project's `CLAUDE.md`, its rules and its hooks load the way they do for any session. The
declaration in D7 exists only for material that is **not** picked up that way.

### D9 — New record fields cross the D10 seam as a guarded second copy

Every field added to the unit record has to be read on the other side of a boundary that forbids
importing. The established answer here is a second copy plus a test that fails when the copies
diverge, and this change follows it rather than inventing a third mechanism: the reader gains
the fields, and the divergence test gains them too.

*Alternative considered:* a shared schema module both sides import. Rejected for this change —
it would be a new package sitting under both, and the dependency-direction test that guards D10
exists precisely to keep that surface from growing quietly. Worth revisiting if the field list
keeps growing; not worth it for five fields.

## Risks / Trade-offs

- **Two sessions in `owner.py` at once (measured, live).** → One narrow function taking the
  final child env, appended after the existing env assembly; coordinate on the channel before
  either lands. The alternative — waiting — costs more than the merge does.
- **Resolution passes and the exec still fails** (the script exists but its interpreter is
  gone). → D2's second half: the post-fork path keeps reporting, and it reports the child's
  exit status. The guard narrows the window; it does not close it, and nothing here should
  claim it does.
- **The stream file grows without bound on a long run.** → It is per unit, in the project's
  runtime area, and units are bounded by a group. If this becomes real, the fix is a cap that
  *states* it truncated — never a silent one.
- **Confidentiality by location is a convention a future contributor can break.** → A test
  asserts the sink resolves under the tree passed to the engine, and that a framework-side log
  of a run carries no stream text.
- **The screen grows a fourth thing to show and pushes the failures behind a tab.** → The
  spec's marker requirement, which is the project's own UI rule: anything hidden that is wrong
  is marked where the reader is standing.
- **A cached plan goes stale and the screen offers a start that the engine then refuses.** →
  The refusal is already specified to surface where the person acted, so the failure is visible
  rather than silent; the cache is an optimisation over a correct refusal, never a substitute
  for one.
- **A green suite proves nothing about the screen.** → The spec carries the browser check as a
  requirement, and an unreachable browser leaves it open rather than substituting a count.

## Migration Plan

Additive throughout; no behaviour changes for a project that declares nothing.

1. Resolution and refusal in the owner (D1, D2) — independently valuable: it turns today's
   unusable route into one that says what is wrong.
2. Install `set-work-cycle` where the owner can see it, and verify with the owner's own PATH.
   Not a substitute for step 1.
3. Record fields and the stream sink (D3, D4) — the engine keeps working unchanged for anyone
   already using it; new runs simply record more.
4. The surface (D5, D6), which depends on 3 for anything worth showing.
5. Declared reading paths (D7), independent of all of the above.

Rollback: each step is separable, and none changes a stored shape that an older reader would
choke on — a record without the new fields reads as *unknown*, which is what the spec requires
anyway.

## Open Questions

- **Where the console script should live** so the owner resolves it on any machine: the
  installed-tools directory alongside the other `set-*` commands, or an absolute path derived
  from the running framework's own interpreter. The first is conventional; the second survives
  a machine where the tools directory is not on the service's PATH. Decide during step 2, with
  the measurement in hand.
- **Whether the stream sink should record the framework's own view too** (gate step output,
  commit result) or only the agent session's stream. Today the record holds the outcomes; the
  question is whether a reader wants the gate's *output* in the same file. Deliberately left
  open — it is additive either way.
- **How far back the screen should list runs.** The engine keeps every unit record; a project
  driven for a week has many. Not answered here because nobody has yet been annoyed by it, and
  guessing a retention rule before that is how a wrong default gets frozen.
