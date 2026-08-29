## Why

The work-cycle engine is built, proven on a real tree, and reachable through an API route —
and **nobody can start it or watch it**. Three measurements, taken 2026-08-29, say where the
gap is:

- `grep -rn "fleet/units" web/src` → **0 hits**. `POST /api/fleet/units` exists
  (`lib/set_orch/api/fleet.py:1532`) and no screen calls it. Nothing renders the engine's own
  run state either, though the engine writes it precisely so a reader needs no running service.
- The route builds `argv[0] = "set-work-cycle"`, the owner execs it with its own environment,
  and that environment cannot resolve it: `env -i PATH=<owner PATH> sh -c 'command -v
  set-work-cycle'` is empty — the console script exists only in the repo's venv. **So the
  route cannot start a unit on this machine at all**, and what the caller is told points away
  from the cause: `systemd-run` fails instantly, no scope registers, the owner spins its full
  four-second wait and answers `did not become active`. A true sentence about the symptom,
  naming the wrong thing to fix. Registered as **B-105**.
- A finished run leaves almost nothing behind. `run_agent_session` is called without
  `on_event` (`lib/set_workcycle/cli.py:369`), so the agent session's stream is consumed and
  discarded; and `UnitRecord.to_dict()` (`lib/set_workcycle/engine.py:470`) persists neither
  the session id the runner read off the stream nor the `--started-by` the CLI accepts. While
  the owner's pty is alive the run is watchable and nowhere else — after it, *who started this,
  and what happened inside it* are both unanswerable.

A fourth item is adoption rather than a defect: the unit prompt's reading list is mechanically
every `.md` in the change directory (`lib/set_workcycle/groups.py:524`). A project with its own
knowledge base has no way to name it, which is the one place where a project would otherwise
have to change how it works to be driven — the thing adoption exists to avoid.

## What Changes

- **A start that cannot exec is refused by name, not by symptom.** The engine command is
  resolved against the environment the child will actually run in, before a scope is claimed,
  so the caller is told which command could not be found and where it was looked for —
  instead of waiting four seconds for a true sentence about a scope.
- **A run records who asked for it and which session ran it.** `started_by` and the agent
  session id join the unit record, alongside the pid and seat already there.
- **A run's stream is persisted where the record already lives**, so a finished run is
  readable without the owner, the pty, or any service.
- **The fleet screen gains the work-cycle half it was built for**: start a unit for a change,
  see what the engine recorded, and open the run's terminal in the project's existing dock.
- **A project may declare extra reading paths** in `set/work-cycle.yaml`, carried into the unit
  prompt. Declared only — the engine names no path of its own, exactly as with gates.

No breaking change: every addition is additive, and a project that declares nothing keeps
today's behaviour.

## Capabilities

### New Capabilities

- `work-unit-start-integrity`: what must be true before a start is reported as one — the
  engine command resolves in the child's environment, and a failure to exec is a refusal
  carrying the repair rather than a claimed start.
- `work-unit-run-observability`: what a run leaves behind — origin (`started_by`), the agent
  session id, and the session's stream, all readable after the process and its terminal are
  gone.
- `work-cycle-screen`: the surface — starting a unit, reading the engine's recorded state, and
  reaching a running unit's terminal in the project's dock, including what it must show when a
  start is refused or a run is stale.
- `work-cycle-reading-scope`: what a project may declare about where a unit reads from, and the
  rule that absence is reported rather than guessed.

### Modified Capabilities

None. The work-cycle capabilities from `work-cycle-engine-apply-first` are not archived yet, so
they are not in `openspec/specs/` and cannot take a delta. The requirements here are additive
and sit in their own capabilities; if that change archives first, these remain compatible with
it because none of them restates one of its requirements.

## Impact

- `lib/set_orch/api/fleet.py` — the unit-start route (resolution before the scope, refusal shape)
- `lib/set_orch/fleet/owner.py`, `lib/set_orch/fleet/scopes/` — how the child's environment is
  established, and what a failed exec reports back
- `lib/set_workcycle/engine.py` — `UnitRecord` fields and serialisation
- `lib/set_workcycle/cli.py`, `lib/set_workcycle/runner.py` — the stream sink, and carrying
  origin into the record
- `lib/set_workcycle/adoption.py`, `lib/set_workcycle/groups.py`, `lib/set_workcycle/prompt.py`
  — declared reading paths
- `web/src` — the fleet screen's work-cycle surface and its tests
- **Confidentiality**: the persisted stream is written into the *project's own* runtime
  directory (`set/runtime/work-cycle/`), never into this repository, and no framework-side log,
  cache, or diagnostic dump carries its content.
- **Install**: the resolution fix touches how the framework's own console scripts are found, so
  it is verified on an installed machine and not only in a checkout.
