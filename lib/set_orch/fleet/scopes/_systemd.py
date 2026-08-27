"""The Linux backend: transient systemd scopes.

Moved here unedited from `fleet/scopes.py` when the module became a package;
the shared vocabulary then moved out to `_types`. Everything below this
paragraph is the original text.

Transient scopes — why a started agent outlives the service that started it.

Task 5.9. The finding it answers (CB-1) is that the dashboard unit runs with
`KillMode=control-group`, and every existing spawn uses `start_new_session=True`,
which changes the **process group** and not the **cgroup**. So an agent started
from the surface joins the service's cgroup and dies with it — including on the
automatic restart after any crash.

Splitting the owner out of the web service does not fix that; it only moves
which service kills it. What fixes it is starting the agent as its own transient
systemd scope, which lands at `app.slice/<name>.scope` — a **sibling** of the
service rather than a child.

Verified on this machine 2026-08-18:

    /user.slice/…/app.slice/fleet-probe-4166319.scope     ← the agent
    /user.slice/…/app.slice/set-web.service               ← the service

`assert_sibling()` below is not a belt-and-braces check; it is the whole point of
the module, and a scope that came out a child would give the surface a survival
promise it cannot keep. The check runs at start and refuses rather than warns.

A named scope also gives task 5.4's "stopping is a deliberate act" a mechanism
instead of a convention: the unit can be stopped by name and enumerated after a
restart, which is what recovery needs in order to be attempted at all.
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
from typing import Dict, List, Optional, Sequence

from ._types import (
    SCOPE_PREFIX,
    Scope,
    ScopeError,
    UNIT_SUFFIX,
    as_unit_name,
    sanitize,
    unit_name,
)

logger = logging.getLogger(__name__)

#: `systemd-run --user` places transient scopes here.
EXPECTED_SLICE = "app.slice"


def _systemctl(*args: str, check: bool = False, timeout: float = 20) -> subprocess.CompletedProcess:
    """Run systemctl, and never let it become this process's problem.

    A timeout here is information, not a crash: `systemctl stop` blocks until the
    unit is down, and a unit whose process ignores SIGTERM keeps it blocked for
    the unit's whole stop timeout. Callers decide what to do about that; raising
    out of a helper would only turn a slow stop into a traceback.
    """
    cmd = ["systemctl", "--user", *args]
    logger.debug("fleet scopes: %s", shlex.join(cmd))
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=check)
    except subprocess.TimeoutExpired:
        logger.warning("fleet scopes: %s timed out after %ss", shlex.join(cmd), timeout)
        return subprocess.CompletedProcess(cmd, returncode=124, stdout="", stderr="timeout")


def _show(unit: str, prop: str) -> str:
    proc = _systemctl("show", unit, "-p", prop, "--value")
    return proc.stdout.strip() if proc.returncode == 0 else ""


def service_cgroup(service: str = "set-web.service") -> str:
    return _show(service, "ControlGroup")


def assert_sibling(unit: str, *, service: str = "set-web.service") -> str:
    """Refuse a scope that landed inside a service's cgroup.

    Returns the scope's cgroup path. Raises when the scope is a descendant of
    the service — which would mean the survival property this module exists for
    is absent, while the surface would go on promising it.
    """
    scope_cg = _show(unit, "ControlGroup")
    if not scope_cg:
        raise ScopeError(f"{unit}: systemd reports no cgroup; cannot verify survival")
    svc_cg = service_cgroup(service)
    if svc_cg and (scope_cg == svc_cg or scope_cg.startswith(svc_cg.rstrip("/") + "/")):
        raise ScopeError(
            f"{unit}: started INSIDE {service}'s cgroup ({scope_cg}); "
            "it would die with that service, so the terminal's survival promise is false"
        )
    if f"/{EXPECTED_SLICE}/" not in scope_cg:
        # Not fatal — a differently configured machine may place it elsewhere, and
        # the sibling check above is the one that carries the guarantee. But the
        # difference is worth a line in the log rather than silence.
        logger.warning("fleet scopes: %s is outside %s (%s)", unit, EXPECTED_SLICE, scope_cg)
    return scope_cg


def start(
    argv: Sequence[str],
    *,
    label: str,
    cwd: str,
    env: Optional[Dict[str, str]] = None,
    verify_service: str = "set-web.service",
) -> Scope:
    """Start a command in its own transient scope, and verify it is a sibling.

    The scope is started with `--collect` so a finished unit does not linger in
    a failed state and block its own name from being reused.
    """
    unit = unit_name(label)
    existing = get(unit)
    # `not is_gone`, not `active`: a scope still shutting down holds its name and
    # its processes, and starting into it collides with both.
    if existing is not None and not is_gone(unit):
        raise ScopeError(f"{unit} is already running (pid {existing.pid}, state {existing.state or '?'})")

    cmd = [
        "systemd-run", "--user", "--scope", "--collect", "--quiet",
        f"--unit={unit}",
        f"--working-directory={cwd}",
    ]
    for key, value in (env or {}).items():
        cmd.append(f"--setenv={key}={value}")
    cmd.extend(argv)

    logger.info("fleet scopes: starting %s in %s", unit, cwd)
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        start_new_session=True,
    )
    # `systemd-run --scope` blocks for the child's lifetime, so we do not wait on
    # it; we wait for the unit to appear instead, which is the fact we need.
    scope = await_unit(unit)
    if scope is None:
        err = ""
        if proc.poll() is not None and proc.stderr:
            err = (proc.stderr.read() or b"").decode("utf-8", "replace").strip()[:400]
        raise ScopeError(f"{unit} did not appear after start{': ' + err if err else ''}")

    cgroup = assert_sibling(unit, service=verify_service)
    logger.info("fleet scopes: %s active, pid %s, cgroup %s", unit, scope.pid, cgroup)
    return Scope(unit=unit, pid=scope.pid, pids=scope.pids, cgroup=cgroup, active=True)


def child_exec(unit: str, argv: Sequence[str], cwd: str, env: Dict[str, str]) -> None:
    """Become the agent. Runs INSIDE the caller's forked pty child; never returns.

    `systemd-run --scope` moves the process into a transient unit at
    `app.slice/<unit>.scope` — a sibling of the dashboard's service rather than a
    member of its control group — while leaving it on the pty the parent forked.

    Lived in `owner.py`'s fork child until the package was split; it is the one
    platform-specific step that was above this package, and D1a moved it in.
    """
    os.chdir(cwd)
    os.execvpe(
        "systemd-run",
        ["systemd-run", "--user", "--scope", "--collect", "--quiet",
         f"--unit={unit}", *argv],
        env,
    )


def adopt(unit: str, child_pid: int, cwd: str) -> Scope:
    """Take up the agent the caller just forked, and verify it will survive.

    `child_pid` is unused here and that is not an oversight: systemd registered
    the unit when the child exec'd, so the authority on what is running is the
    unit, not the pid the parent happens to hold. A backend without a registry
    needs the pid, so the contract carries it on both.

    Raises `ScopeError` when the unit never became active, or when it came out
    inside the service's own control group.
    """
    scope = await_unit(unit)
    if scope is None:
        raise ScopeError(f"{unit} did not become active")
    cgroup = assert_survivable(unit, scope.pid)
    return Scope(unit=unit, pid=scope.pid, pids=scope.pids, cgroup=cgroup, active=True)


def assert_survivable(unit: str, pid: Optional[int] = None) -> str:
    """The cross-platform name for what `assert_sibling` checks here.

    `pid` is accepted and ignored — see `adopt`. Kept in the signature so that
    the caller has one call shape on every platform.
    """
    return assert_sibling(unit)


def forget(unit: str) -> None:
    """No record to drop: systemd's unit registry is the record."""
    return None


def await_unit(unit: str, *, attempts: int = 40, interval: float = 0.1) -> Optional[Scope]:
    import time
    for _ in range(attempts):
        found = get(unit)
        if found is not None and found.active:
            return found
        time.sleep(interval)
    return None


#: Where the unified cgroup hierarchy is mounted.
CGROUP_ROOT = "/sys/fs/cgroup"


def pids_in(cgroup: str) -> List[int]:
    """Every live pid inside a cgroup, read from the kernel.

    ⚠ Not `systemctl show <unit> -p MainPID`. Measured 2026-08-18: a transient
    **scope** reports `MainPID=0`, because a scope adopts processes rather than
    forking them the way a service does — so the property that names the process
    for a service names nothing here. Reading `cgroup.procs` asks the kernel
    which processes are actually in the group, which is the question.
    """
    if not cgroup:
        return []
    path = os.path.join(CGROUP_ROOT, cgroup.lstrip("/"), "cgroup.procs")
    try:
        with open(path, "r") as fh:
            return [int(line) for line in fh.read().split() if line.strip().isdigit()]
    except OSError as exc:
        logger.debug("fleet scopes: cannot read %s: %s", path, exc)
        return []


def get(unit: str) -> Optional[Scope]:
    """One scope by unit name, or None when systemd does not know it."""
    unit = as_unit_name(unit)
    state = _show(unit, "ActiveState")
    if not state or state in {"inactive", "failed"} and not _show(unit, "ControlGroup"):
        return None
    cgroup = _show(unit, "ControlGroup")
    members = pids_in(cgroup)
    return Scope(
        unit=unit,
        pid=members[0] if members else None,
        pids=members,
        cgroup=cgroup,
        active=state == "active",
        state=state,
    )


def list_scopes() -> List[Scope]:
    """Every framework-owned agent scope systemd currently knows about.

    Enumerated from systemd rather than from anything the framework wrote down:
    a record of what we started is a record of our intent, and after a crash the
    two differ exactly when it matters.
    """
    proc = _systemctl("list-units", "--type=scope", "--all", "--no-legend", "--plain")
    if proc.returncode != 0:
        logger.warning("fleet scopes: list-units failed: %s", proc.stderr.strip()[:200])
        return []
    found: List[Scope] = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        unit = parts[0]
        if not unit.startswith(SCOPE_PREFIX) or not unit.endswith(".scope"):
            continue
        scope = get(unit)
        if scope is not None:
            found.append(scope)
    return found


def stop(unit: str, *, grace: float = 5.0, kill_grace: float = 5.0) -> bool:
    """Stop a scope by name. True when it is gone afterwards.

    Stopping by name is what makes recovery possible at all (task 5.11): a pid
    is reused and a remembered one may name something else entirely, while the
    unit name is the identity systemd itself keeps.
    """
    unit = as_unit_name(unit)
    if not unit.startswith(SCOPE_PREFIX) or not unit.endswith(".scope"):
        raise ScopeError(f"refusing to stop {unit}: not a framework-owned agent scope")

    logger.info("fleet scopes: stopping %s (grace %ss)", unit, grace)
    # `--no-block` on purpose. A plain `systemctl stop` waits for the unit to be
    # down, and an interactive agent commonly ignores SIGTERM — measured
    # 2026-08-18, an interactive shell in a scope kept `stop` blocked past 20s.
    # Waiting inside systemctl gives us no way to escalate; waiting here does.
    _systemctl("stop", "--no-block", unit)
    if _await_gone(unit, grace):
        logger.info("fleet scopes: %s stopped on SIGTERM", unit)
        return True

    # Escalation, stated rather than silent. "Stopping is a deliberate act"
    # (task 5.4) is only true if it finishes; a stop that hangs forever is not a
    # gentler stop, it is a stop that did not happen.
    logger.warning("fleet scopes: %s ignored SIGTERM after %ss, sending SIGKILL", unit, grace)
    _systemctl("kill", "--signal=SIGKILL", unit)
    if _await_gone(unit, kill_grace):
        logger.info("fleet scopes: %s stopped on SIGKILL", unit)
        return True

    logger.error("fleet scopes: %s still active after SIGKILL", unit)
    return False


#: States in which systemd still has work to do on a unit. None of them is
#: `active`, and every one of them can hold live processes — which is exactly
#: why "not active" is the wrong question to ask when stopping.
LIVE_STATES = frozenset({"active", "activating", "deactivating", "reloading"})


def is_gone(unit: str) -> bool:
    """Whether a scope is REALLY gone — no processes left, not merely not-`active`.

    MEASURED 2026-08-18 on a live interactive agent, and the defect this replaces
    failed in the reassuring direction: `stop()` returned `gone=True` in **0.0
    seconds** and logged "stopped on SIGTERM" while `systemctl show` reported
    `deactivating` and the agent's pid was **still alive**. The old check was
    `not scope.active`, and `active` is the string comparison `ActiveState ==
    "active"` — so every intermediate state read as gone the instant the stop was
    requested, before anything had died.

    Two things make it worth this much comment. It is **load-bearing for task
    5.11**: `recover()` stops an orphaned scope and re-reads before resuming,
    precisely so a resume never lands on a live session — but a re-read that asks
    the same wrong question returns the same wrong answer, so the guard against
    the §6.1 silent fork was open. And the surface would have reported an agent
    as stopped while it was running, which is the false-value class.

    So the question asked is about the PROCESSES, with the state as a secondary
    check rather than the primary one: a cgroup that still holds a pid is not
    gone, whatever systemd calls the unit at that moment.
    """
    return scope_is_gone(get(unit))


def scope_is_gone(scope: Optional[Scope]) -> bool:
    """The same question asked of a Scope already in hand.

    Separate from `is_gone` so a caller that already holds the object — every
    caller iterating `list_scopes()` — does not pay a second `systemctl show`
    per unit just to re-derive what it is looking at. One definition, two
    entry points, so the two cannot drift.
    """
    if scope is None:
        return True
    # The processes are the fact. A cgroup that still holds a pid is not gone,
    # whatever systemd calls the unit at this moment.
    if scope.pids:
        return False
    return scope.state not in LIVE_STATES


def _await_gone(unit: str, seconds: float, interval: float = 0.2) -> bool:
    import time
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if is_gone(unit):
            return True
        time.sleep(interval)
    return is_gone(unit)


def scope_of(pid: int) -> Optional[str]:
    """The framework scope a pid belongs to, or None.

    Read from the process's own cgroup line rather than by matching what we
    started: this answers for a process the current owner never started, which
    is the case recovery has to handle.
    """
    try:
        with open(f"/proc/{pid}/cgroup", "r") as fh:
            raw = fh.read()
    except OSError:
        return None
    for line in raw.splitlines():
        _, _, path = line.partition("::")
        segment = os.path.basename(path.strip() or line.strip())
        if segment.startswith(SCOPE_PREFIX) and segment.endswith(".scope"):
            return segment
    return None
