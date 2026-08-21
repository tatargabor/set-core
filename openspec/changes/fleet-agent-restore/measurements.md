# Measurements taken while implementing

Recorded at the moment of the measurement, not summarised afterwards. Each entry
names the command so it can be re-run rather than believed.

## M1 — the reboot drill, on this machine's REAL agents (2026-08-21)

The user asked for proof that this works after a reboot. A reboot cannot be
arranged on demand, so the boot was **simulated by removing what a boot
removes** — in a user+mount namespace, `/proc` was replaced with an empty tmpfs
and `~/.claude/sessions` was bind-mounted over with an empty directory.

**Step 1 — record the live fleet.** `discovery.discover_agents()` → **25 agents,
25 interactive**; `roster.record()` → 25 added, 0 skipped, **11 projects**.

**Step 2 — read it back inside the simulated boot.**

```
proc entries visible: 0
session records visible: 0
TOTAL 25 entries, 25 resumable
```

Every project came back with its full entry count, and every entry was resumable
— because the transcript under `~/.claude/projects/<slug>/<sessionId>.jsonl` is
what a boot leaves behind.

**Step 3 — the control, which is the half that makes step 2 mean anything.** The
same simulated boot, asking today's code the same question:

```
discover_agents() after the simulated boot:  0 agents
discover_agents() without it:               25 agents
```

So the simulation is not vacuous: it destroys exactly what a boot destroys, the
current screen goes to zero inside it, and the roster still holds all 25.

Reproduce:

```bash
unshare -rm bash -c '
  mount -t tmpfs none /proc
  mkdir -p /tmp/empty-sessions && mount --bind /tmp/empty-sessions $HOME/.claude/sessions
  python3 read_back.py <roster.json>'
```

**What this does NOT prove.** That a real reboot leaves the transcripts where
this expects them, and that the roster file survives an unclean shutdown with
its last write intact. Both are properties of the machine, not of this code, and
only an actual reboot answers them — hence task 8.8.

## M2 — a cwd that is not a project (found by M1)

One of the 25 recorded entries landed under the project name **`/home/tg`**: the
agent's `cwd` is the home directory, `project_name` was empty, and the roster
falls back to the cwd as the key. Correct as recorded — the agent was real and
omitting it would understate the fleet — but it raises a question for the restore
route, recorded here rather than decided silently:

`POST /api/fleet/agents` refuses a cwd outside `_known_roots()`. Restore reads
its cwd from the roster, so either it applies the same guard (and this entry
becomes a skip with a reason) or it does not (and restore can start an agent
somewhere the start route would refuse). **Decision: apply the same guard.** A
second route that admits what the first refuses is the guard being deleted, one
caller at a time.

## M3 — mutation rounds (5 + 2 mutants, all caught)

`roster.py`, against `tests/unit/test_fleet_roster.py`:

| mutant | result |
|---|---|
| filter out unresumable entries | CAUGHT (7 failed) |
| key on the pid instead of the session id | CAUGHT (7 failed) |
| copy the stored dict through instead of rebuilding it | CAUGHT (1 failed) |
| record oneshot subprocesses too | CAUGHT (1 failed) |
| store resumability instead of measuring it | CAUGHT (2 failed) |

`api/fleet.py`, against `tests/unit/test_fleet_roster_wiring.py`:

| mutant | result |
|---|---|
| do not swallow the write failure | CAUGHT (1 failed) |
| do not record at all | CAUGHT (3 failed) |

Run with `PYTHONDONTWRITEBYTECODE=1` and `__pycache__` cleared per round (mtime
+ size is all CPython compares, and two mutants of one file can be
byte-identical in size). The pattern count was asserted `== 1` per mutation
rather than using `replace(..., 1)`, and the restore was re-checked by grepping
the original string back — `git checkout` cannot restore an untracked file, and
`|| true` would have hidden that.
