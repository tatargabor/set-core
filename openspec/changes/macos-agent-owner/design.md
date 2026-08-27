## Context

The agent owner is a separate long-lived service that holds the ptys of agents
started from the Fleet screen. It exists because of finding CB-1: the dashboard unit
runs with `KillMode=control-group`, and `start_new_session=True` changes the process
group but not the control group, so an agent started by the dashboard joined the
dashboard's cgroup and died with it — including on the automatic restart after any
crash. `scopes.py` answers that by starting each agent as a transient systemd scope
at `app.slice/<name>.scope`, a sibling of the service rather than a child, and
`assert_sibling()` refuses a start that came out a child.

Every part of that is systemd. On macOS the result is a screen whose start control is
dead, reporting a socket under `/run/user/501/` and offering a `systemctl` command.

**Measured on this machine, 2026-08-27** (Darwin 25.4.0, Apple Silicon), because the
design below rests on it:

| Fact | Value |
|---|---|
| `com.set-core.web` (launchd job) `pgid` | equal to its own pid — the job leads its own process group |
| the same job's `getsid()` | `1` — it sits in launchd's session, and is not a session leader |
| `lsof -p <pid> -a -d cwd -Fn` on a same-user process | returns the working directory |
| `/Users/…/.local/share/set-core/runtime/set-agent-owner.sock` | 68 bytes, against a 104-byte `sun_path` limit |

The consequence that shapes the whole design: a child started with
`start_new_session=True` on macOS becomes a **session leader** — its session id equals
its own pid, and therefore differs from the dashboard's `1`. There is no cgroup to
escape, because the hazard cgroups created does not exist here. The macOS backend is
correspondingly much smaller than the systemd one; the work is in the boundary, the
verification and the record, not in reproducing scopes.

This is platform variation, not project-type variation: it does **not** belong behind
the `ProjectType` ABC, and stays in `lib/set_orch/fleet/`.

## Goals / Non-Goals

**Goals:**
- `+ start an agent` works on macOS, with the same survival property it promises on
  Linux, verified rather than assumed.
- One API for the owner and the API layer; no platform branching above the backend.
- The Linux path is byte-for-byte unchanged in behaviour.
- Waiters are measured on macOS, keeping could-not-measure distinct from none.
- Every operator-facing message names a command the running machine can execute.

**Non-Goals:**
- Making a pty-attached agent survive the **owner's** restart. It cannot, on either
  platform: the pty master dies with the process holding it, and the agent reaches
  EOF on its own tty. Only the dashboard's restart is survivable, which is the
  property CB-1 was about.
- Reproducing cgroup resource control on macOS. The scopes exist for lifetime, not
  for limits, and nothing in the framework reads a scope's resource accounting.
- Windows, or any third platform. The boundary makes one possible; this change does
  not add one.
- Changing the wire shapes, the surface, or what an agent is.

## Decisions

### D1 — `scopes` becomes a package with two backends, keeping its function API

`lib/set_orch/fleet/scopes.py` becomes `lib/set_orch/fleet/scopes/` holding
`__init__.py` (the shared `Scope` dataclass, `ScopeError`, `sanitize`, `unit_name`,
`SCOPE_PREFIX`, and dispatch), `_systemd.py` (today's implementation, moved), and
`_darwin.py` (new). Selection is by `sys.platform` at import.

*Why not an `if` inside each function:* the systemd implementation is ~400 lines of
`systemctl show` parsing, unit-state vocabulary (`active` vs `deactivating` vs gone)
and cgroup arithmetic. Interleaving a second platform through it would make both
harder to read and would put the Linux path — the one in daily use — one editing
mistake away from a regression.

*Why not a `ProjectType`-style plugin:* profiles describe the project being built.
This describes the machine the framework runs on. Routing it through profiles would
make a Mac's fleet depend on which kind of project is open.

**`owner.py` reaches into two private names**, `scopes._await_unit` and
`scopes._as_scope`. Those become part of the backend contract under public names, or
`owner.py` stops needing them. Left as-is they would be defined on one backend only,
and the split would look complete while `owner.py` broke on the other.

### D1a — AMENDED during implementation: the boundary is wider than the `scopes` API

**What D1 assumed:** that `scopes`' function API is the platform boundary and
`owner.py` merely calls it.

**What is actually true**, found while splitting the package: `owner.py` does its own
`pty.fork()` and, in the forked child, execs systemd directly —

    os.execvpe("systemd-run",
        ["systemd-run", "--user", "--scope", "--collect", "--quiet",
         f"--unit={unit}", *argv], child_env)      # owner.py:174

So the platform-specific step sits ABOVE the package. And `scopes.start()` — the
function the original task list said to implement for Darwin — is called from nowhere
outside the backend: verified by grep across `lib`, `tests` and `bin`. Implementing it
would have produced a function the fleet never runs, and the macOS start path would
still have gone through a hardcoded `systemd-run`.

**The finding that makes the fix small.** `pty.fork()` is documented as "fork and make
the child a session leader with a controlling terminal", and it calls `os.setsid()` in
the child. The pty fork therefore ALREADY confers the property the measurement above
identified as the one that survives. macOS needs no wrapper process at all: the child
execs the agent's own argv, and the survival comes from the fork that had to happen
anyway for the terminal.

**The amended contract** adds four operations to the backend:

| Operation | systemd | darwin |
|---|---|---|
| `child_exec(unit, argv, cwd, env)` — in the forked child | exec `systemd-run --scope --unit=…` | exec `argv` directly |
| `adopt(unit, child_pid, cwd) -> Scope` — in the parent | `await_unit(unit)`, ignoring `child_pid` | verify, record, return |
| `assert_survivable(unit, pid)` | today's `assert_sibling` cgroup check | session-leadership check |
| `forget(unit)` | no-op | drop the record |

`owner.py`'s exec block becomes one call to `child_exec`. `assert_sibling` is kept as
the systemd backend's own name for what it does — the cross-platform requirement is
survivability, and only one platform expresses it as a sibling relationship.

*Why not push the pty fork itself into the backend:* the pty is the owner's, not the
scope's — the owner holds the master for the process's whole life, and the replay
buffer, the drain and the window size all belong to it. Moving the fork would take
those with it.

### D2 — On macOS the survival check is session leadership, read back from the kernel

The backend starts the agent with `start_new_session=True` and then **reads** the
result: `os.getsid(pid) == pid` (it leads its own session) and `os.getpgid(pid)`
differs from the dashboard's process group. Both come from the running kernel, not
from the flag that was passed — a spawn flag is an intention, and the requirement is
about what actually happened.

*Why session leadership rather than "not the dashboard's pgid" alone:* a process can
share neither pgid nor session with the dashboard and still be reached by a signal
sent to a group it joined later. A session leader of a session containing only itself
and its own children is the strongest statement macOS lets us make cheaply, and it is
the exact analogue of "sibling, not child".

*Alternative considered — `launchd` submit per agent:* `launchctl submit` would give
a unit registry and a supervised lifetime, closest to the systemd design. Rejected:
it makes every agent a persistent user agent that launchd may restart, and a
restarted agent with a dead pty is a worse failure than no agent. The framework wants
a process, not a service.

### D3 — A JSON record replaces the unit registry, and is never the authority on liveness

systemd enumerates `set-agent-*.scope` units for free; macOS has nothing equivalent.
The Darwin backend keeps a record under the runtime directory holding, per label: pid,
process start time, cwd and the label itself.

Reads reconcile against the running system: an entry is reported alive only when a
process with that pid exists **and** its start time matches the recorded one. The
start-time comparison is the pid-recycling guard — a pid alone would let an unrelated
process inherit an agent's identity, and the surface would then offer to stop it.

*Why start time and not a cookie in the environment:* reading another process's
environment on macOS requires privileges the owner does not have; start time comes
from `ps` for any same-user process.

### D4 — The socket path is resolved by one function, checked against `sun_path`

`default_socket_path()` gains a macOS branch under the framework's per-user runtime
directory, and grows a length check that refuses with the path, its byte length and
the limit. The measured candidate is 68 bytes against 104, with headroom for a long
user name.

*Why the check earns its place:* an over-long `sun_path` fails at bind with an errno
that reads as a missing directory. That is the class of message that sends a reader
to check a directory which is present — the same false trail this change is fixing at
the level of `systemctl`.

*Why not `$TMPDIR`:* it is 49 bytes here and would fit, but it is per-session and
subject to periodic cleaning, and a control socket that disappears on a schedule is a
fleet that stops answering for no visible reason.

### D5 — Waiters are read from `ps`, with `lsof` only for the few that matched

`live_waiters()` splits into a platform-neutral matcher and a platform process
source. Linux keeps the `/proc` walk. macOS runs one `ps -A -o pid=,command=`, matches
waiter argv, and then calls `lsof` **per matched waiter** for the working directory.

*Why not `lsof` over every pid:* it would be a whole-machine syscall sweep on the
fleet's polling path, paid by every reader for a field most processes never need.
*Why not `psutil`:* it is not a dependency of `set-core` today, and adding one for two
fields that `ps` already prints is a dependency the install has to carry on every
platform.

A working directory `lsof` cannot supply is reported unknown and the waiter is still
listed — dropping it would be the false absence this capability exists to prevent.

### D6 — The start command is resolved next to the socket path

`START_COMMAND` becomes a function resolved per platform, returning the launchd
invocation on macOS and today's `systemctl --user start set-agent-owner.service` on
Linux. The reason string the client already produces is kept and the command is added
to it, so the remedy never replaces the diagnosis.

## Risks / Trade-offs

- **launchd may kill descendants of a job it stops, defeating D2.** → This is the
  macOS analogue of CB-1 and is the one assumption the design cannot be built on
  without evidence. It is the first task: start a setsid'd child under the dashboard
  job, `launchctl kickstart -k` the job, and assert the child is still alive. If it
  dies, D2 is wrong and the fallback is a double-fork reparented to launchd, or D2's
  rejected alternative — reopened with the measurement that forced it.
- **pid recycling between a record write and a read.** → Start-time comparison (D3).
  The residual window is a pid reused by a process started in the same clock tick as
  the original, which `ps` start-time resolution cannot separate; accepted, and noted
  where the comparison is written.
- **`lsof` absent, slow, or blocked by privacy controls.** → The field is optional by
  spec; the waiter is listed with an unknown directory. A missing `lsof` degrades one
  field, never the measurement.
- **Converting a module to a package breaks an import somewhere.** → `from . import
  scopes` and `scopes.foo()` keep working; `from .scopes import X` also keeps working
  for names re-exported from `__init__`. The risk is a name that exists on one
  backend only — which D1's private-name item is specifically about.
- **Two backends, one test suite that only ever runs on one of them.** → The Darwin
  backend's logic that can be tested without Darwin (record reconciliation, path
  resolution, `sun_path` refusal, argv matching) is separated from the calls that
  cannot, so CI on Linux still covers it. The survival check itself is verified on the
  machine, and the task list says so rather than pretending a unit test proves it.
- **The Linux path regressing while nobody is looking at it.** → The move is a move:
  the systemd implementation is relocated without edits in its own step, so any later
  diff against it is readable.

## Migration Plan

1. Additive throughout. No existing installation changes behaviour: on Linux the
   resolver returns what it returned before, and the systemd backend is the same code.
2. On macOS the installer places and loads the new job. A Mac that never had a working
   start control gains one; nothing is taken away.
3. Rollback is a revert. There is no persisted state to unwind except the Darwin
   record file, which is regenerated and is meaningless to the Linux path.
4. An existing Mac install picks this up on the next `install.sh`, which is how the
   dashboard's own job is already managed.

## Open Questions

- ~~**Does a setsid'd grandchild survive `launchctl kickstart -k` of the job that
  started it?**~~ **ANSWERED by measurement, 2026-08-27 — see "The measurement that
  settles D2" below. Yes, and the control shows `setsid` is what does it.**
- ~~**Does the owner need to know the dashboard's pid at all on macOS?**~~ **ANSWERED
  — no.** The control run showed the killed child was the one sharing the job's
  process group, and the surviving children led their own sessions. `getsid(pid) ==
  pid` therefore already excludes membership of the dashboard's group, so asking
  launchd for the dashboard's pid would add a dependency and a failure mode to
  re-derive a fact the session check has settled. The Darwin backend asks the kernel
  about the agent only.
- ~~**Should the Darwin record live beside the socket or under the existing runtime
  tree used by `set-paths`?**~~ **ANSWERED while writing task 2.1 — beside the socket,
  in `$XDG_DATA_HOME/set-core/runtime/`.** `set-paths` resolves per project and the
  owner is per machine, so its tree was the wrong shape; `paths.SET_TOOLS_DATA_DIR` is
  already the framework's per-user, per-machine location and needed no new convention.
  Measured: the socket path that falls out is 68 bytes against macOS's 104.

## The measurement that settles D2

Run 2026-08-27 on this machine (Darwin 25.4.0, Apple Silicon), against a throwaway
launchd job built to have the same shape as the dashboard's — `pgid` equal to its own
pid, `sid` 1 — spawning one child and then staying alive so the job could be restarted
under it. The job and every child were removed afterwards; `com.set-core.web` was not
touched.

**With `start_new_session=True`** the child came out `pgid == pid`, `sid == pid` — a
session leader of its own session:

| What was done to the job | The child afterwards |
|---|---|
| `launchctl kickstart -k gui/501/<job>` | alive, reparented to `ppid 1` |
| `kill -9` of the job's pid | alive, `ppid 1` |
| `launchctl unload` of the job | alive, `ppid 1` |

**The control — the same job, the same restart, a child spawned WITHOUT
`start_new_session`** — came out `pgid` equal to the job's and `sid 1`, sharing the
job's process group. `launchctl kickstart -k` **killed it.**

The control is the half that makes this a measurement rather than a reassurance. Had
the plain child survived too, the three rows above would have proved only that nothing
on this machine kills anything, and D2's verification would have been reading a
property that costs nothing to hold. It does not survive, so:

- **D2 is confirmed.** Session leadership is the mechanism, not an incidental
  attribute of the spawn.
- **The verification in task 4.1 is meaningful.** `os.getsid(pid) == pid` distinguishes
  exactly the case that survives from exactly the case that dies, which is what a check
  guarding a survival promise has to do.
- **The fallbacks in the risk register are not needed.** No double-fork, and
  `launchctl submit` stays rejected.
