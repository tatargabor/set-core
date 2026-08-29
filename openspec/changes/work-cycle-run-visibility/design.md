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

### D5 — The screen reads the record; it does not shell out to learn state

Rendering runs from `set/runtime/work-cycle/<change>/*.json` is what the engine's own contract
promises ("readable without a running engine or service"). The API reads those files. The only
thing the surface *executes* is the start.

*Alternative considered:* run `set-work-cycle status` per project on every poll. Rejected — a
process per tile per poll, and it makes rendering depend on the very command whose absence D1
exists to handle.

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
