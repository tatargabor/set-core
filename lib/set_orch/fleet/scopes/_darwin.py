"""The macOS backend: sessions instead of control groups.

macOS has no systemd, no transient units and no cgroups, so nothing here
reproduces a scope. It does not need to. The hazard scopes exist for is
systemd-specific — the dashboard's unit runs with `KillMode=control-group`, and
a process started by it joins that group and dies with it (finding CB-1). launchd
has no equivalent: a job is killed by pid, and a process that has left the job's
session is not reached.

MEASURED 2026-08-27 on Darwin 25.4.0, against a throwaway launchd job shaped like
the dashboard's (`pgid` equal to its own pid, `sid` 1):

    child spawned WITH  start_new_session  →  survives kickstart -k, kill -9, unload
    child spawned WITHOUT start_new_session →  KILLED by kickstart -k

The control is what makes that a measurement rather than a reassurance: the plain
child dies, so session leadership is the mechanism and not an incidental property
of the spawn. `assert_survivable` below therefore reads the session back from the
kernel, and refuses when it is not the agent's own.

**The agent is already a session leader before this module sees it.** `pty.fork()`
is documented as "fork and make the child a session leader with a controlling
terminal" and calls `os.setsid()` in the child. The owner forks a pty for the
terminal regardless, so the survival property arrives for free and `child_exec`
below is a plain exec. Do not add a wrapper process back: there is nothing for it
to do, and it would put a process between the owner's pty and the agent.

What systemd gave for free and this module must keep itself is the REGISTRY —
which agents exist, under what names. That is the record in `_record.py` terms
below: a JSON file beside the owner's socket, reconciled against the running
system on every read and never trusted about liveness.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import time
from typing import Dict, List, Optional, Sequence

from ._types import (
    SCOPE_PREFIX,
    Scope,
    ScopeError,
    as_unit_name,
    sanitize,
    unit_name,
)

logger = logging.getLogger(__name__)

RECORD_NAME = "agents.json"


# --------------------------------------------------------------------------- #
# the record — what systemd's unit registry did, kept by hand
# --------------------------------------------------------------------------- #

def _record_path() -> str:
    from ..ownerd import _runtime_dir
    return os.path.join(_runtime_dir(), RECORD_NAME)


def _read_record() -> Dict[str, dict]:
    try:
        with open(_record_path()) as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        # Not silence, and not a crash either: a corrupt record must not take the
        # fleet down, but it must not read as "no agents" without saying so —
        # that is the empty-versus-unknown confusion this framework keeps
        # finding, and here it would offer to start a second agent under a name
        # that is already taken.
        logger.warning("fleet scopes (darwin): cannot read %s: %s", _record_path(), exc)
        return {}
    return data if isinstance(data, dict) else {}


def _write_record(data: Dict[str, dict]) -> None:
    path = _record_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp{os.getpid()}"
    # Written whole and renamed: a reader that arrives mid-write must see the old
    # record or the new one, never half of either.
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    os.replace(tmp, path)


#: BSD state letters that mean the process is finished, whatever else the field
#: says. `Z` is the documented zombie; `E` is the flag for "trying to exit", and
#: it is the one that actually appears here.
_FINISHED_STATES = ("Z", "E")


def _is_finished(pid: int) -> bool:
    """Whether the process has exited, whether or not it has been reaped.

    MEASURED 2026-08-27, and it is why this function exists: `os.kill(pid, 0)`
    SUCCEEDS for an exited-but-unreaped process, and its start time still
    matches, so both other liveness checks pass for a process that has already
    gone. The agent is the owner's own forked child and the owner reaps it only
    after the stop returns, so the window is the normal case rather than a race.

    **The state letter is `?Es`, not `Z`** — and getting that wrong cost three
    acceptance runs. A first version tested `startswith("Z")`, which is the
    documented zombie state and is what a `fork()`-ed child in a plain script
    reports; an agent killed on its pty reports `?E` instead, `E` being the BSD
    flag for "trying to exit". So `stop()` polled a dead process for its full
    grace AND kill grace, reported `survived SIGKILL`, and left the entry in the
    record — while `ps` from outside showed `?Es` the whole time.

    Matching the FLAG rather than the state letter is what makes this right for
    both: `Z` for the reaped-later zombie, `E` for the exiting one.

    systemd has no equivalent problem because the unit, not the pid, is the
    authority there. Here the pid is all there is, so its state has to be asked
    for explicitly.
    """
    try:
        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "state="],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    state = proc.stdout.strip()
    if not state:
        # `ps` prints nothing for a pid it cannot find, which is the strongest
        # form of finished there is.
        return True
    return any(ch in state for ch in _FINISHED_STATES)


def _started_at(pid: int) -> Optional[str]:
    """The process's start time, as the machine reports it.

    This is the pid-recycling guard. A pid on its own is not an identity: the
    kernel reuses them, and a record naming a pid that now belongs to something
    else would let the fleet report a stranger as its agent and offer to stop it.

    Not read from the environment — another process's environment needs
    privileges the owner does not have — and not stored as a cookie the agent
    would have to cooperate in keeping.
    """
    try:
        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("fleet scopes (darwin): cannot read start time of %s: %s", pid, exc)
        return None
    value = proc.stdout.strip()
    return value or None


def _alive(pid: Optional[int], started_at: Optional[str]) -> bool:
    """Whether the recorded process is still THAT process.

    Both halves are required. `kill(pid, 0)` alone answers "some process has this
    pid", which is the question that lets a recycled pid pass. A record with no
    start time is treated as alive-if-present rather than dead: refusing to see a
    live agent is the failure that loses work.
    """
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True          # exists, owned by somebody else — still not gone
    if _is_finished(pid):
        return False         # exited; the pid lingers only until it is reaped
    if started_at is None:
        return True
    now = _started_at(pid)
    if now is None:
        return True
    return now == started_at


# --------------------------------------------------------------------------- #
# the contract
# --------------------------------------------------------------------------- #

def child_exec(unit: str, argv: Sequence[str], cwd: str, env: Dict[str, str]) -> None:
    """Become the agent. Runs INSIDE the caller's forked pty child; never returns.

    A plain exec, deliberately. `pty.fork()` has already made this process a
    session leader — see the module docstring for the measurement — so there is
    no wrapper to run and no unit to register with.
    """
    os.chdir(cwd)
    os.execvpe(argv[0], list(argv), env)


def assert_survivable(unit: str, pid: Optional[int] = None) -> str:
    """Refuse an agent that would die with the dashboard. Returns "" — no cgroup.

    Read back from the kernel rather than inferred from the spawn: the
    requirement is about what actually happened, and a flag that was passed is
    not evidence that it took effect.
    """
    if pid is None:
        raise ScopeError(f"{unit}: no pid to verify; the survival promise cannot be checked")
    try:
        sid = os.getsid(pid)
        pgid = os.getpgid(pid)
    except (ProcessLookupError, PermissionError) as exc:
        raise ScopeError(f"{unit}: cannot read the session of pid {pid} ({exc})") from exc

    if sid != pid:
        raise ScopeError(
            f"{unit}: pid {pid} is in session {sid}, not its own — it shares a "
            f"lifetime with whatever leads that session and would die with it. "
            "Measured 2026-08-27: a child in the dashboard job's session is killed "
            "by `launchctl kickstart -k`; one leading its own session is not."
        )
    if pgid != pid:
        raise ScopeError(
            f"{unit}: pid {pid} leads session {sid} but sits in process group "
            f"{pgid}; a signal to that group would reach it"
        )
    return ""


def adopt(unit: str, child_pid: int, cwd: str) -> Scope:
    """Take up the agent the caller just forked: verify it, then record it."""
    assert_survivable(unit, child_pid)
    data = _read_record()
    # Drop entries whose process has ended, so the record stays the size of the
    # live fleet rather than of every agent ever started. Done HERE, at a write,
    # rather than on a read: `get()` distinguishes "never recorded" from
    # "recorded and ended", and pruning during a read would flip a name from the
    # second answer to the first while a caller was acting on it.
    for stale in [u for u, e in data.items()
                  if u != unit and not _alive(e.get("pid"), e.get("started_at"))]:
        logger.debug("fleet scopes (darwin): pruning ended agent %s from the record", stale)
        data.pop(stale)
    data[unit] = {
        "unit": unit,
        "pid": child_pid,
        "started_at": _started_at(child_pid),
        "cwd": cwd,
    }
    _write_record(data)
    logger.info("fleet scopes (darwin): adopted %s as pid %s in %s", unit, child_pid, cwd)
    return Scope(unit=unit, pid=child_pid, pids=[child_pid], cgroup="", active=True, state="active")


def forget(unit: str) -> None:
    data = _read_record()
    if data.pop(unit, None) is not None:
        _write_record(data)
        logger.debug("fleet scopes (darwin): dropped %s from the record", unit)


def get(unit: str) -> Optional[Scope]:
    """The recorded agent, reconciled against the running system.

    Returns None for a name that was never recorded, and an INACTIVE scope for one
    that was recorded and is gone — the two are different answers, and the caller
    distinguishes "no such agent" from "that agent has ended".
    """
    unit = as_unit_name(unit)
    entry = _read_record().get(unit)
    if entry is None:
        return None
    pid = entry.get("pid")
    alive = _alive(pid, entry.get("started_at"))
    return Scope(
        unit=unit,
        pid=pid if alive else None,
        pids=[pid] if alive and pid else [],
        cgroup="",
        active=alive,
        state="active" if alive else "inactive",
    )


def list_scopes() -> List[Scope]:
    """Every agent this framework recorded, live ones and ended ones alike."""
    out: List[Scope] = []
    for unit in sorted(_read_record()):
        scope = get(unit)
        if scope is not None:
            out.append(scope)
    return out


def is_gone(unit: str) -> bool:
    scope = get(unit)
    return scope is None or not scope.active


def scope_is_gone(scope: Optional[Scope]) -> bool:
    """Gone means gone, not merely 'not active'.

    The systemd backend has a third state — `deactivating`, whose processes are
    still running — and answers this question by checking for a live pid rather
    than by reading the state word. There is no deactivating here, but the same
    rule is applied for the same reason: a scope holding a live pid is not gone,
    whatever it is called.
    """
    if scope is None:
        return True
    if scope.pid is not None or scope.pids:
        return False
    return not scope.active


def await_unit(unit: str, *, attempts: int = 40, interval: float = 0.1) -> Optional[Scope]:
    """Kept for the one shape across platforms.

    Returns at once: there is no registry to become consistent with, and `adopt`
    has already written the record by the time anyone can ask.
    """
    scope = get(unit)
    return scope if scope is not None and scope.active else None


def scope_of(pid: int) -> Optional[str]:
    """Which recorded agent holds this pid, if any."""
    for unit, entry in _read_record().items():
        if entry.get("pid") == pid and _alive(pid, entry.get("started_at")):
            return unit
    return None


def stop(unit: str, *, grace: float = 5.0, kill_grace: float = 5.0) -> bool:
    """Stop the agent, and say whether it is gone.

    Signals the process GROUP, not the pid. The agent leads its own session, so
    its group holds it and every child it started; signalling the pid alone would
    leave an agent's own children running with nothing holding their terminal —
    the same reason the systemd backend stops the unit rather than its main pid.
    """
    unit = as_unit_name(unit)
    entry = _read_record().get(unit)
    if entry is None:
        return True                      # nothing recorded under that name
    pid = entry.get("pid")
    if not _alive(pid, entry.get("started_at")):
        forget(unit)
        return True

    for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, kill_grace)):
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError) as exc:
            logger.debug("fleet scopes (darwin): signalling %s (%s): %s", unit, sig, exc)
            break
        logger.info(
            "fleet scopes (darwin): sent %s to %s (pid %s, pgid %s, owner pgid %s)",
            sig.name, unit, pid, pgid, os.getpgid(0),
        )
        deadline = time.monotonic() + wait
        polls = 0
        while time.monotonic() < deadline:
            if not _alive(pid, entry.get("started_at")):
                forget(unit)
                return True
            polls += 1
            if polls % 10 == 1:
                # Why this is not silent: a stop that reports "survived SIGKILL"
                # gives a reader no way to tell a process that ignored the signal
                # from a liveness check that is answering the wrong question.
                logger.debug(
                    "fleet scopes (darwin): %s still reads alive after %s "
                    "(pid %s, finished=%s, started_at now %r, recorded %r)",
                    unit, sig.name, pid, _is_finished(pid), _started_at(pid),
                    entry.get("started_at"),
                )
            time.sleep(0.1)

    gone = not _alive(pid, entry.get("started_at"))
    if gone:
        forget(unit)
    else:
        logger.error("fleet scopes (darwin): %s (pid %s) survived SIGKILL", unit, pid)
    return gone
