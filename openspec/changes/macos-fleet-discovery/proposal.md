## Why

The fleet's process reader is `/proc`-only, so on macOS it does not report *few* agents — it
reports **none**, and reports it as a count. Measured on this machine on 2026-08-27 with two
real `claude` sessions running (pids 37343 and 33393): `discover_agents()` returned `[]`,
`is_agent_process(37343)` returned `False`, and `parent_seat(37343)` returned `None`. The
screen's "0 agents in 0 of 22 projects" was never a measurement here — it was a blind read
rendered as a number, which is the false-absence class this codebase already hunts everywhere
else.

Two more readers were measured blind in the same pass, and one of them fails in the direction
that matters:

- `purpose._pid_state(37343)` returned `(False, False)` for a **live** pid, because it asks
  `os.path.isdir("/proc/<pid>")`. Every recorded orchestration run therefore reports `stale`
  on a Mac — "nothing is running", stated about a machine where something is.
- `instruct.remove_waiter()` reads argv from `/proc`, gets `[]`, and refuses every pid with
  "this pid is not a waiter process". That refusal is the safe direction, so nothing is
  killed wrongly — but the control is permanently dead and says nothing about why.

`instruct.live_waiters()` is **not** in this list: it was ported in the `macos-agent-owner`
change and answers correctly here. That is what makes the rest of the module misleading — one
function in it works, so a reader has no reason to suspect the others.

**A fourth module, found during implementation and named here rather than absorbed.** The
opening enumeration said "three modules are `/proc`-bound" — `discovery`, `instruct`,
`purpose` — and that was a summary of a grep, not a measurement of the tree. The check this
change's own spec demands (no `/proc` path built outside the source package) found
`awaiting.py:121`: `os.path.isdir(f"/proc/{pid}")`, which is False for every pid on a Mac, so
every recorded orchestrator and ralph pid read as **gone**. That module's own test
(`test_a_running_change_with_a_LIVE_pid_is_unverifiable_never_fine`) was failing at HEAD on
this platform and passes after the fix — verified in a clean HEAD worktree, not inferred.

The preceding change (`macos-agent-owner`) made it possible to *start* an agent from the fleet
screen on a Mac. This one makes it possible to *see* one. Without it the owner ships a control
whose result is invisible: the agent starts, survives a dashboard restart, and the screen still
says nothing is running.

## What Changes

- **New:** a platform-dispatched process source, `lib/set_orch/fleet/procsource/`, following the
  package shape the `macos-agent-owner` change just shipped for `scopes/` — `_linux.py`,
  `_darwin.py`, `_types.py`, and an **access-time** `__getattr__` dispatcher in `__init__.py`.
  Import-time binding was measured in that change to break delegation one-way (12 tests failed
  exactly that way); it is not repeated.
- **New:** a Darwin backend reading the same six facts from `ps` and `lsof` instead of `/proc`:
  live pids by executable identity, `cwd`, `argv`, `ppid`, one environment variable, and the
  `comm` of a single pid. Every one of the six was measured available on this machine before
  being specified — see design.md for the commands and their outputs.
- **Modified:** `discovery.py`, `instruct.py` and `purpose.py` stop opening `/proc` paths
  directly and ask the source instead. The `sys.platform == "darwin"` special case currently
  sitting inside `live_session_ids()` is folded into the dispatcher rather than left as a
  one-off — it was the precedent for this change, not the pattern to copy.
- **Consolidated:** `instruct.py` already carries a working macOS reader (`_ps_session`,
  `_ps_cwd`, `_waiters_from_ps`). Its behaviour is kept exactly and its bodies move into the
  Darwin backend, so there is **one** implementation of "the cwd of a pid on macOS" rather
  than two that can drift apart. This is a move, not a rewrite: `live_waiters()` must return
  the same thing before and after.
- **Preserved:** the `proc_root` parameter, because ~10 existing tests build a fake `/proc`
  tree under `tmp_path` and pass it in. The Linux backend keeps it, and the dispatcher lets a
  caller select a backend explicitly rather than only by `sys.platform`, so a Linux-tree test
  runs on a Mac and a Darwin-backend test runs on Linux.
- **Preserved:** the per-caller fail direction. `live_session_ids()` already documents that
  "unreadable" must stay distinct from "empty" — for a listing an empty screen is honest, but
  for the resume guard an empty set clears the way for a resume onto a live session, which
  forks its conversation silently. A Darwin backend whose `ps` or `lsof` fails must preserve
  that distinction rather than flatten it to an empty list.

Not in scope, and named so the boundary is visible: the fleet's git resolution, the session
record format, the waiters panel's layout, and Windows. Nothing here adds a platform beyond
the two that are measured.

## Capabilities

### New Capabilities

- `fleet-process-source`: the abstraction the fleet asks about a process — the six facts, the
  values that mean "could not answer" versus "answered, nothing there", and the access-time
  platform dispatch with explicit backend selection.
- `macos-process-reader`: the Darwin backend — which command answers which fact, identity
  matching rather than substring matching, batching, what `ps -E` can and cannot see, and the
  facts macOS answers less precisely than `/proc` does.
- `fleet-platform-neutral-readers`: `discovery.py`, `instruct.py` and `purpose.py` read
  through the source on every platform, and each caller's fail direction survives the move.

### Modified Capabilities

None. The three capabilities above are new; no existing spec in `openspec/specs/` states
requirements about where process facts come from.

## Impact

- `lib/set_orch/fleet/procsource/` — new package (Layer 1, core).
- `lib/set_orch/fleet/discovery.py` — `_live_agent_pids`, `_proc_cwd`, `_proc_argv`, `_ppid`,
  `_classify_kind`, `is_agent_process`, `live_session_ids`, `discover_agents`, `discover_agent`,
  `parent_seat`.
- `lib/set_orch/fleet/instruct.py` — `_proc_argv`, `_proc_env`, `remove_waiter`; and the
  already-working `_ps_session` / `_ps_cwd` / `_waiters_from_ps` move into the backend.
- `lib/set_orch/fleet/purpose.py` — `_pid_state`, `_status_of`, `read_purposes`.
- `lib/set_orch/fleet/awaiting.py` — `_pid_alive`. Not in the opening enumeration; see the
  paragraph above for how it was found and why that matters more than the fix.
- `tests/unit/test_fleet_discovery.py` and the other suites that pass a fake `proc_root` — must
  keep passing unchanged; a change to one of them is a signal the abstraction moved a contract,
  not a routine edit.
- External dependency: `/usr/sbin/lsof` and `/bin/ps` on macOS. Both ship with the OS; neither
  needs elevated privileges for same-user processes, which is measured, not assumed.
- No web change is required for the count to become non-zero — the fleet screen already renders
  whatever discovery returns. It is still looked at in the browser before this is called done.
