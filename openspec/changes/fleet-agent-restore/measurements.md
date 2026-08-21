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

## M4 — the owner's label behaviour, measured rather than assumed (task 5.4)

`OwnerClient().health()` and `list` against the running owner, 2026-08-21:

```
health: {'ok': True, 'pid': 4084305, 'uptime_seconds': 219559.8, 'held': 24}
list:   24 agents, every one 'population': 'started-here', 'resumed_session': None
```

Two things settle the open question in design D5. The owner refuses a label it
already holds (`owner.py:150`, `"{label} is already owned here"`) **and** a unit
whose scope is still running. And `list` returns the labels it holds — so the
collision is avoided **proactively**, by asking, rather than by matching the text
of an error message. Restore therefore derives `<label>-r2`, `-r3` (bounded at 3)
and reports `renamed: true` with the label actually used. A rename is visible;
the alternative — skipping the entry — loses a conversation to protect a name.

Also worth recording: `resumed_session: None` on all 24, so nothing on this
machine has ever been resumed through this path. The first real restore will be
the first exercise of `owner.recover()` outside tests.

## M5 — an existing guard test misread the new routes (2026-08-21)

`test_every_fleet_route_is_registered_before_the_project_wildcards` failed the
moment `/api/fleet/roster/{project}` existed. It classified wildcards with
`"{project" in p`, and the new route matches that substring while being a fleet
route, not a member of the `/api/{project}/...` family the test guards against.

Direction: it reported a collision where there was none — which invites moving a
route to fix nothing. Narrowed to `"{project" in p and not
p.startswith("/api/fleet")`, and the refuted pattern is now held in
`test_a_bare_substring_check_would_have_misread_a_fleet_route_as_a_wildcard`, so
a later simplification back to it fails instead of quietly guarding the wrong
thing.

## M6 — mutation round on restore.py (7 mutants, all caught)

| mutant | result |
|---|---|
| treat indeterminate liveness as "nothing running" | CAUGHT (1 failed) |
| resume a live session anyway | CAUGHT (3 failed) |
| abandon the rest after a failure | CAUGHT (2 failed) |
| call it complete whenever anything started | CAUGHT (3 failed) |
| drop the known-roots guard | CAUGHT (1 failed) |
| report an unresumable entry as failed instead of skipped | CAUGHT (2 failed) |
| ignore held labels — let the owner collide | CAUGHT (1 failed) |

The two that matter most are the first two: both are the silent fork, and both
are caught by a test that asserts the owner was **never asked** about a live
session — not that it refused. A test that let the call through and checked the
error would pass on code that forks the conversation and reports it tidily.

## M7 — `set-fleet-roster verify`, run both ways (task 8.8)

The same command, on the same file, outside and inside the simulated boot:

```
outside:  25 entries, 25 resumable now, 25 already running
inside:   25 entries, 25 resumable now,  0 already running
```

That second line is what a real reboot will print, and it is the line to check
after one. The `running` column is what makes it readable at a glance: restore
skips a session that is already live, so `running` is the count restore will
*leave alone* and `resumable - running` is the count it will bring back.

`running` prints `?` and a NOTE when liveness could not be determined, never a
zero — a gap is not a zero, and zero is the number a reader would act on.

## M8 — the defect the browser found, and no test could have (task 8.5)

**The control read `Restore 7 agents` for a project whose seven sessions were all
alive.** Restore skips a live session — that is the guard the whole module is
built around — so the button promised an act that would have skipped every one
of them. 772 web tests and the full Python suite were green.

Nothing in the mechanism was wrong. `resumable` is about the TRANSCRIPT, and all
seven had one. What the button needed is a different question: *is there a
transcript AND is nobody on it*. The two coincide on a rebooted machine, which is
the only state the tests simulated, and diverge on every other.

Fixed at the source. `roster.read()` still consults nothing a reboot destroys —
that property is the point of the module — so `running` is added in the ROUTE,
which may ask. `null` when liveness could not be determined, never `false`,
because that count is SUBTRACTED from what the button offers and an unmeasured
zero would overstate the act.

The screen now says, verbatim from the running dashboard:

```
All 7 already running                                    (text, no button)
Restore 4 of 7 — 2 already running, 1 cannot be resumed  (button, active)
```

## M9 — a LIVE restore against 7 running sessions (2026-08-21)

Clicked for real, on the running dashboard, against the real owner. Seven live
sessions — including this conversation's own,
`0b7772e4-1db9-4065-a951-0b21eeece85b`:

```
None of the 7 started — see the reason on each.
set-core-34 — skipped — session 039178b5-… is bound to a live process; left
              alone — a resume against a live session forks its conversation silently
… (7 of these)
```

Server log: `fleet restore: set-core — 0 started, 7 skipped, 0 failed of 7 attempted`.
After the click: **26 claude processes, owner holding 25, uptime 61.4 h unchanged.**
Nothing was started, nothing was stopped, no conversation was forked.

The result marker in the DOM is `partial`, not `complete`, and the unfinished
count is `7`. This is the property the whole surface is built to hold: a restore
where nothing started must not render as a success.

## M10 — regression, against a properly isolated baseline

`git worktree add --detach`, `PYTHONPATH` at all three source roots, and the
session-end leak assertion from CLAUDE.md:

| | failure entries | leaks |
|---|---|---|
| baseline (`/tmp/wbase`, HEAD) | 108 | 0 |
| working tree | 107 | 0 |

The single difference is a baseline-only failure (`test_paths.py::
TestResolveProjectName::test_resolve_with_explicit_path`, cwd-sensitive and run
from `/tmp/wbase`). **No new failure.** Web: baseline 741 passed, working tree
**785 passed**, zero failed.

⚠ **And the first attempt at this measurement was itself wrong**, which is the
half worth keeping. The background task's captured output held only the `tail -3`
my own command printed, so `grep '^FAILED'` found 2 lines in each file, the diff
of two 0-line sets came back empty, and it printed **"IDENTIKUS HALMAZ"** — a
clean bill of health derived from comparing nothing with nothing. The tell was
that the summary line said 83 failures while the extraction found 2. Same class
as the zero with an empty breakdown: when a count and its own listing disagree,
the SHAPE of the input is what to inspect, not the conclusion.
