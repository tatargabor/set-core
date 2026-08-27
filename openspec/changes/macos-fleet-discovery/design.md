## Context

The fleet reads process state directly from `/proc` in three modules. On macOS there is no
`/proc`, so each of them fails quietly and in its own way. Measured on this machine on
2026-08-27, with two live `claude` sessions (pids 37343 in `~/code/set-core`, 33393 in
`~/code/set-copilot`):

| reader | macOS answer | truth | direction of the error |
|---|---|---|---|
| `discovery.discover_agents()` | `[]` | 2 agents | **false absence**, rendered as a count |
| `discovery.is_agent_process(37343)` | `False` | `True` | false absence |
| `discovery.parent_seat(37343)` | `None` | `None` | right answer, wrong reason |
| `discovery.live_session_ids()` | correct | correct | already ported |
| `instruct.live_waiters()` | correct | correct | already ported |
| `instruct.remove_waiter(pid)` | always refuses | — | safe, but permanently dead |
| `purpose._pid_state(37343)` | `(False, False)` | `(True, True)` | every run reads `stale` |

The one that decides the shape of this design is the third row. `parent_seat` returns `None`
on both platforms, so a test — and a reader — cannot tell a correct answer from a blind one.
That is the whole argument for routing every process fact through one named source rather than
patching the six call sites: a patched call site is verified by the value it returns, and here
the value is the same either way.

The immediately preceding change, `macos-agent-owner`, ported the *writing* side (starting and
stopping an agent). It left the reading side, and shipped one function of it — `live_session_ids`
— because the waiters panel's `measured` flag depended on it. So the codebase now contains a
half-ported module, which is worse than an unported one: a reader who checks one function
concludes the module is fine.

## Goals / Non-Goals

**Goals:**

- One named source for every process fact the fleet reads, with two backends and no
  platform branching above the package.
- macOS answers the same six questions Linux does, from `ps` and `lsof`, with every command
  measured on this machine before being written into a spec.
- The per-caller fail direction survives the move. "Could not answer" and "answered, nothing
  there" stay distinct values wherever a caller acts on the difference.
- The ~10 existing tests that build a fake `/proc` under `tmp_path` keep passing **unchanged**.
  An edit to one of them is a signal that the abstraction moved a contract.
- A Darwin-backend test runs on Linux and a Linux-tree test runs on macOS, so neither half is
  verified only where it happens to be the default.

**Non-Goals:**

- Windows. Two platforms are measured; a third would be speculation with a spec attached.
- Changing what the fleet *does* with the facts — git resolution, session-record binding,
  the waiters panel's layout, the tile ordering. This change alters where a fact comes from,
  never what it means.
- Making `parent_seat` work better. It already returns `None` correctly on Linux for a
  different, documented reason (0 of 23 agents had an agent ancestor; a framework-started
  agent's parent is the owner process). This change only stops it being `None` *blindly*.
- Privilege escalation. Everything here works for same-user processes without `sudo`, which
  is measured. A fact that would need root is reported as unavailable, not asked for.

## Decisions

### D1 — A package with two backends, mirroring `fleet/scopes/`

`lib/set_orch/fleet/procsource/` with `_types.py`, `_linux.py`, `_darwin.py` and an
`__init__.py` that dispatches. This is not a fresh choice; it is the shape the `macos-agent-owner`
change shipped one commit ago for the same problem, and consistency between the two is worth
more than any refinement.

**Access-time delegation, never import-time binding.** `__getattr__` resolves against the
backend on attribute access. Binding names at import (`argv = _backend.argv`) freezes them to
the function objects that existed when the dispatcher was first imported, which makes the
delegation one-way: a test replacing `_linux.argv` changes what the backend's own internals
see and not what reaches callers, so the two halves of one call chain run different code.
Measured in the previous change — twelve tests in `test_fleet_owner.py` failed exactly that
way. *Alternative considered:* explicit re-export. Rejected on that measurement.

### D2 — The source is an object, not a module of functions

`scopes/` dispatches to module-level functions. This package returns a `ProcSource` instance
instead, because macOS needs **batching** and module functions have nowhere to put it.

Measured costs on this machine (632 processes):

```
ps -A -o pid=,ppid=,comm=     0.01 s     (five runs, all 0.01)
ps -p <pid> -o comm=          0.00 s
lsof -a -d cwd -Fpn -p 37343,33393   0.014 s   (both cwds, one call)
```

`/proc` answers per-pid for free; macOS answers per-pid for a fork each. `discover_agents()`
asks six questions about every agent, so a per-pid Darwin implementation would spawn a process
per question. One `ps` for the whole table plus one batched `lsof` for the matched pids answers
all of it in ~25 ms. The instance is where that snapshot lives.

**A snapshot is scoped to one pass and never cached across calls.** `DarwinProcSource()` is
constructed by the caller that wants a consistent reading and discarded after; a stale snapshot
would report a dead agent as live, which is the direction that lets a resume fork a live
session. *Alternative considered:* a module-level cache with a TTL. Rejected — a TTL turns a
correctness property into a timing question, and the cost it would save is 10 ms.

### D3 — `proc_root` keeps its exact current meaning

The existing signature convention is already in the tree and already documented on
`live_waiters()`: `proc_root` **explicitly selects the `/proc` reader whatever the platform**,
and its absence means "dispatch by platform". This change generalises that one function's rule
into the dispatcher rather than inventing a new one:

```python
procsource.for_root(None)            # platform dispatch
procsource.for_root("/tmp/fake")     # Linux backend, rooted there — what the tests do
procsource.backend("darwin")         # explicit backend, for a Darwin test on Linux
```

The existing keyword defaults stay `proc_root: str = "/proc"` where they already are, so no
call site outside the fleet changes and no existing test is touched. `"/proc"` as a *default*
means dispatch; `"/proc"` passed explicitly on Linux resolves to the same backend anyway, so
the ambiguity is unobservable. *Alternative considered:* replacing `proc_root` with a `source`
parameter everywhere. Rejected — it would edit ~10 tests, and an edited test cannot testify
that behaviour was preserved.

### D4 — The six facts, and the command that answers each on macOS

Every row was run on this machine before it was written down.

| fact | Linux | macOS | measured result |
|---|---|---|---|
| live pids by identity | walk `/proc/*/comm` | `ps -A -o pid=,comm=` | `37343 claude`, `33393 claude` |
| `cwd` | `readlink /proc/<pid>/cwd` | `lsof -a -d cwd -Fpn -p <csv>` | `/Users/…/set-core`, `/Users/…/set-copilot` |
| `argv` | `/proc/<pid>/cmdline` | `ps -ww -A -o pid=,args=` | `claude --dangerously-skip-permissions` |
| `ppid` | `/proc/<pid>/stat`, after the last `)` | `ps -o pid=,ppid=` | `37343 → 37323`, `33393 → 5741` |
| one env var | `/proc/<pid>/environ` | `ps -E -p <pid> -o command=` | 24 assignments visible for pid 37343 |
| `comm` of one pid | `/proc/<pid>/comm` | `ps -p <pid> -o comm=` | `claude` |

**Identity, never substring.** Both backends compare the *basename* of `comm` for equality. The
Linux reader's docstring records why: matching command lines instead found 31 false positives,
all shell snapshots whose path contains the word. macOS `comm` prints a full path for system
binaries (measured: strings up to 277 characters) and the bare name for the agent, so the
basename is taken on both. Linux truncates `comm` to 15 characters and macOS does not — which
is invisible for `claude` at 6 characters, and is written into the spec so a longer binary name
later is a known difference rather than a surprise.

### D5 — `lsof`'s exit code is not usable, and this is the trap the change exists to avoid

Measured:

```
lsof -a -d cwd -Fpn -p 37343,999999   →  prints 37343's cwd correctly,  rc=1
lsof -a -d cwd -Fpn -p 999999         →  prints nothing,                rc=1
```

A dead pid anywhere in the batch sets the exit code, and the exit code cannot distinguish
"answered nothing" from "answered some". A backend that followed the ordinary rule —
`returncode != 0 → return None` — would turn a **successful** batched read into "the machine
could not be measured", every time the batch contained one exited process, which during a
discovery pass is common rather than exceptional.

So: **`lsof`'s stdout is parsed regardless of exit code.** Failure is concluded only when the
process could not be run at all (`OSError`, timeout) or produced no parseable output *and*
wrote to stderr. This is the same class as the `?Es`-is-not-`Z` finding from the previous
change — a documented signal read as if it meant what the manual implies, in a place where
being wrong is silent.

### D6 — Fail direction is a property of the fact, and is stated per method

The source returns `None` for "could not answer" and an empty container for "answered, nothing
there". The two are never collapsed, because two callers already act on the difference in
opposite ways, and `live_session_ids()` documents it: for a listing, unreadable → empty is
honest, an empty screen states what is known. For the resume guard, an empty set *clears the
way* for a resume onto a live session, which forks its conversation silently — so undeterminable
liveness must be treated as live.

This means the Darwin backend cannot use a bare `except: return []` anywhere, and the spec
states the value for each failure rather than a blanket rule.

### D7 — `instruct.py`'s working macOS readers move rather than being rewritten

`_ps_session`, `_ps_cwd` and the `ps` table walk in `_waiters_from_ps` already work and were
verified in the previous change. Their bodies move into `_darwin.py` unedited where possible.
The reason is not tidiness: two implementations of "the cwd of a pid on macOS" will drift, and
the one that drifts will be the one nobody is looking at. `live_waiters()` returning the same
value before and after is the acceptance condition for this decision, asserted with a real
`sac.mjs wait` process rather than only with a fake table.

## Risks / Trade-offs

- **A refactor of a blind reader is unfalsifiable by its return value.** `parent_seat` returns
  `None` correctly on Linux and blindly on macOS; a test asserting `None` passes either way.
  → Every macOS test asserts against a **live pid on this machine** (the session's own process
  is always available), not against a value that a blind implementation would also produce.
  Where a fixture is used, it asserts the *command that was run*, not only the parsed result.

- **`ps` joins argv with spaces, so an argument containing a space cannot be recovered.**
  → Accepted, and already accepted in the shipped waiter reader for the same reason: the two
  consumers test fixed positions (`argv[1].endswith("sac.mjs")`, `argv[2] == "wait"`) and
  membership of `-p` / `--print`, none of which a space breaks. Written into the spec as a
  stated limitation so a future consumer needing exact argv knows it is not available here.

- **`ps -E` shows the environment only for same-user processes.** Measured working for the
  dashboard's own launchd job and for pid 37343. → A process owned by another user yields no
  assignments, which the backend reports as `None` (unknown), never as "the variable is
  absent". `remove_waiter` treats an unknown session as alive and refuses, which is the
  direction that cannot kill a working waiter.

- **The snapshot can go stale inside one pass.** A process that exits between the `ps` and the
  `lsof` appears live with no cwd. → `discover_agents()` already skips a pid with no readable
  cwd, so the outcome is an omission from a listing, not a false claim. Stated rather than
  fixed: closing it would need an atomic process snapshot the OS does not offer.

- **`lsof` is an external binary this code now depends on.** → It ships with macOS at
  `/usr/sbin/lsof` and is on the default `PATH` (measured). Absent or unrunnable, the backend
  reports cwd as unknown per pid and the fleet still lists the agents, with the field missing
  and marked missing — the same fail-open choice `read_messaging_projects` makes and states.

- **This makes a previously-empty screen full, on a machine whose behaviour nobody has seen.**
  → A non-zero count is not the acceptance condition. The screen is opened in a browser and
  looked at, per `.claude/rules/ui-quality.md`; the task stays open if the browser cannot be
  reached, and the commit says so.

## Migration Plan

No data migration and no persisted format changes. The rollout is a single commit whose
rollback is a revert: the package is new, and the three callers change only in which function
they ask. Verification order, because the later steps cannot be trusted until the earlier ones
hold:

1. The existing `/proc`-fixture tests pass **unedited** — proves the Linux path did not move.
2. `live_waiters()` returns the same value before and after the consolidation — proves D7 was
   a move.
3. On this Mac, with real agents running: `discover_agents()` names them with the right `cwd`,
   `is_agent_process(<live pid>)` is `True`, `purpose` reports a live run as `running`.
4. The fleet screen is opened in a browser and looked at.

## Open Questions

- Whether `purpose._pid_state`'s `comm == "claude"` literal should move to `discovery.AGENT_COMM`
  now that both backends resolve identity the same way. It is a duplicated constant with one
  spelling in two modules; folding it in is correct but touches a module this change otherwise
  only reads from. **Decided during implementation, and recorded in tasks.md either way** —
  not left to the reader to discover from a diff.
