"""The agent owner — the one process whose lifetime is the agents' lifetime.

Tasks 5.8 and 5.11, and the module the measurement of 2026-08-18 reshaped.

**Why this is a separate service.** The dashboard unit runs with
`KillMode=control-group` and restarts on every crash and every deploy. An agent
started from it joins its cgroup and dies with it (finding CB-1). Splitting the
owner out and starting each agent in its own transient scope fixes that — the
scope is a sibling of the service, not a child (see `scopes.py`).

**Why this service must stay THIN, and the reason is stronger than "tidy".**
Measured, both directions:

    pty-attached agent, pty holder killed  →  scope inactive, agent DEAD
    no-pty agent, starter killed           →  scope active,   agent ALIVE

A transient scope protects against a cgroup kill. It cannot protect against the
agent's terminal disappearing: when the pty master closes, the slave returns EOF
and any process reading its own tty exits. So **the owner's lifetime is the
agents' lifetime**, not merely the terminal's. Every restart of this service
kills every agent it is holding.

That is the whole specification of what may live here: hold ptys, relay bytes,
start and stop named scopes. Discovery, state, the API and the screen belong to
the web service, which may then restart as often as development needs. *A line
of business logic added here is a future outage of every running agent.*

**Nothing is persisted.** Bytes pass through; they are not written down, not
cached, and not logged. Diagnostics name the stream and the failure kind only.
"""

from __future__ import annotations

import errno
import fcntl
import logging
import os
import pty
import signal
import struct
import termios
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from . import discovery, scopes
from .scopes import Scope, ScopeError

logger = logging.getLogger(__name__)

#: How each agent was acquired. Carried as a fact rather than inferred, because
#: the surface's rules differ per population and a guess here becomes a promise.
STARTED_HERE = "started-here"
FOREIGN = "foreign"


def _describe_exit(status: int) -> str:
    """A wait status as a sentence, because the raw number is not one.

    Task 5.6 asks for the exit SIGNAL in the log, and `waitpid` returns a packed
    status where 36608 means "killed by SIGKILL" and nothing about it says so.
    A log line an operator has to decode by hand is a log line they will skip,
    and the whole point of logging the lifecycle is that an orphan is findable
    from the logs rather than only from the screen.
    """
    if os.WIFSIGNALED(status):
        signum = os.WTERMSIG(status)
        try:
            name = signal.Signals(signum).name
        except ValueError:
            name = f"signal {signum}"
        return f"killed by {name}"
    if os.WIFEXITED(status):
        code = os.WEXITSTATUS(status)
        if code == 0:
            return "exited cleanly"
        # 128+N is the shell's convention for "died on signal N", and it is the
        # COMMON case here rather than an exotic one: an agent under a pty runs
        # below a shell, so a SIGTERM arrives as exit code 143 — measured on the
        # first real stop. Reporting only the number leaves the reader to do the
        # arithmetic, and a reader who has to do arithmetic stops reading.
        if 128 < code < 128 + signal.NSIG:
            try:
                return f"exited with code {code} (128+{signal.Signals(code - 128).name})"
            except ValueError:
                pass
        return f"exited with code {code}"
    return f"ended with raw wait status {status}"


class OwnerError(RuntimeError):
    """An agent could not be started, written to, or recovered."""


@dataclass
class OwnedAgent:
    """An agent this owner started and holds the terminal for."""

    label: str
    unit: str
    pid: Optional[int]
    cwd: str
    #: The pty master. Held by this process and unobtainable from any other —
    #: `/proc/<pid>/fd/<n>` for a master points at `/dev/ptmx`, and opening that
    #: allocates a NEW pair rather than returning this one (measured 2026-08-17).
    master_fd: int
    #: The pid `pty.fork()` returned — this owner's own child, and the only pid
    #: it may `waitpid()` on. NOT the same question as `pid`, which is whatever
    #: `cgroup.procs` listed first and may name a grandchild.
    child_pid: Optional[int] = None
    population: str = STARTED_HERE
    #: Set when the framework resumed an existing session rather than starting a
    #: new one, so the surface can say which of the two acts it performed.
    resumed_session: Optional[str] = None


class AgentOwner:
    """Holds the ptys. One instance per owner process."""

    def __init__(self) -> None:
        self._agents: Dict[str, OwnedAgent] = {}

    # -- lifecycle ------------------------------------------------------- #

    def start(
        self,
        argv: Sequence[str],
        *,
        label: str,
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        rows: int = 40,
        cols: int = 120,
        resumed_session: Optional[str] = None,
    ) -> OwnedAgent:
        """Start an agent under a framework-owned pty, inside its own scope.

        The pty is forked here so that this process holds the master; the child
        execs `systemd-run --scope`, which moves the agent into a sibling cgroup
        while leaving it on this pty.
        """
        if label in self._agents:
            raise OwnerError(f"{label} is already owned here")
        unit = scopes.unit_name(label)
        existing = scopes.get(unit)
        # `not is_gone`, never `active`: a scope in `deactivating` is not active
        # and still holds live processes (measured 2026-08-18).
        if existing is not None and not scopes.is_gone(unit):
            raise OwnerError(
                f"{unit} is already running (pid {existing.pid}); "
                "stop it before starting, or recover it instead"
            )

        child_env = dict(os.environ)
        # A session started as another session's child writes no transcript at
        # all — measured 2026-08-18, and it makes the agent invisible to every
        # source the fleet reads. Anything the framework starts must not inherit
        # that marker.
        for key in [k for k in child_env if k.startswith("CLAUDE")]:
            child_env.pop(key, None)
        child_env["TERM"] = "xterm-256color"
        child_env.update(env or {})

        pid, master_fd = pty.fork()
        if pid == 0:  # pragma: no cover - executed in the forked child
            try:
                os.chdir(cwd)
                os.execvpe(
                    "systemd-run",
                    ["systemd-run", "--user", "--scope", "--collect", "--quiet",
                     f"--unit={unit}", *argv],
                    child_env,
                )
            except BaseException:
                os._exit(127)

        self._set_window(master_fd, rows, cols)
        scope = scopes._await_unit(unit)
        if scope is None:
            os.close(master_fd)
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
            raise OwnerError(f"{unit} did not become active; the agent was not started")

        # The guarantee this whole module rests on. Refuse rather than warn: a
        # scope inside the service's cgroup would give the surface a survival
        # promise that is simply false.
        cgroup = scopes.assert_sibling(unit)
        agent = OwnedAgent(
            label=label, unit=unit, pid=scope.pid, cwd=cwd,
            master_fd=master_fd, child_pid=pid, resumed_session=resumed_session,
        )
        self._agents[label] = agent
        logger.info(
            "fleet owner: started %s as %s (pid %s, cgroup %s)%s",
            label, unit, scope.pid, cgroup,
            f", resumed session {resumed_session}" if resumed_session else "",
        )
        return agent

    def stop(self, label: str) -> Dict[str, object]:
        """Stop an agent deliberately — never as a side effect of a view.

        Returns what was actually found, not just whether the unit is down.

        **MEASURED 2026-08-18: this used to report success for a label that never
        existed.** `POST /api/fleet/agents/nincs-ilyen/stop` answered
        `{"gone": true}` with a 200, because `scopes.stop` on an unknown unit
        finds nothing running and "nothing is running" is technically true. It is
        also a false value: the surface would confirm that an agent had been
        stopped when there had never been one, and this module's own docstring
        claimed the owner "refuses anything it does not hold" — which it did not.

        Three outcomes, and they are genuinely different acts:

        - `started-here` — this owner holds the terminal; stopping it is the
          ordinary case.
        - `orphan` — a framework scope of this name is running but its terminal
          died with a previous owner. Stopping it is legitimate (it is the first
          half of `recover()`), and the caller is told which act it performed.
        - not found — nothing of that name is running anywhere. `found` is False,
          and the caller decides what a request to stop nothing means; the HTTP
          route answers 404 rather than reporting a stop that stopped nothing.
        """
        agent = self._agents.get(label)
        unit = agent.unit if agent else scopes.unit_name(label)

        if agent is None and scopes.is_gone(unit):
            logger.info("fleet owner: nothing named %s is running; not reporting a stop", label)
            return {"label": label, "unit": unit, "found": False, "gone": True, "population": None}

        population = STARTED_HERE if agent is not None else FOREIGN
        gone = scopes.stop(unit)
        if agent is not None:
            self._close(agent)
            self._agents.pop(label, None)
        logger.info(
            "fleet owner: stopped %s (unit %s, %s, gone=%s)", label, unit, population, gone
        )
        return {"label": label, "unit": unit, "found": True, "gone": gone, "population": population}

    def _close(self, agent: OwnedAgent) -> None:
        try:
            os.close(agent.master_fd)
        except OSError as exc:
            logger.debug("fleet owner: closing master for %s: %s", agent.label, exc)
        self._reap(agent)

    def _reap(self, agent: OwnedAgent, *, timeout: float = 2.0) -> bool:
        """Collect the forked child, so a long-lived owner does not fill with zombies.

        MEASURED 2026-08-18: one start/stop cycle left the owner holding a
        `Zs  [claude] <defunct>` child. This service is long-lived by design —
        its uptime is every agent's uptime — so one unreaped child per agent
        lasts as long as the service does.

        The second cost is worse than the first, because it corrupts
        measurement: `ps -p <pid>` reports a **zombie as an existing process**,
        so a check written as "is the agent still running" answers yes for one
        that is dead. That check misfired here while verifying the stop path,
        which is the proxy-instead-of-the-thing class caught in the act.
        """
        if agent.child_pid is None:
            return True
        deadline = time.monotonic() + timeout
        while True:
            try:
                collected, status = os.waitpid(agent.child_pid, os.WNOHANG)
            except ChildProcessError:
                return True          # already reaped, or never ours to reap
            except OSError as exc:
                logger.debug("fleet owner: waitpid for %s: %s", agent.label, exc)
                return False
            if collected:
                logger.info(
                    "fleet owner: reaped %s (pid %s, %s)",
                    agent.label, collected, _describe_exit(status),
                )
                return True
            if time.monotonic() >= deadline:
                logger.warning(
                    "fleet owner: %s (pid %s) has not exited; not reaped",
                    agent.label, agent.child_pid,
                )
                return False
            time.sleep(0.05)

    # -- the relay -------------------------------------------------------- #

    def write(self, label: str, data: bytes) -> int:
        """Send keystrokes to an agent this owner started.

        Task 5.2: a write into a terminal the framework does not own is refused.
        The check is ownership of the *handle*, not a claim about the session —
        this owner can only write to a master it is holding, so the refusal is
        structural and cannot drift out of agreement with reality.
        """
        agent = self._agents.get(label)
        if agent is None:
            raise OwnerError(
                f"no terminal owned here for {label}; "
                "the framework never writes into a session it did not start"
            )
        try:
            return os.write(agent.master_fd, data)
        except OSError as exc:
            if exc.errno in (errno.EIO, errno.EBADF):
                logger.warning("fleet owner: terminal for %s is gone (%s)", label, exc.errno)
                self._agents.pop(label, None)
                raise OwnerError(f"the terminal for {label} has closed") from exc
            raise

    def read(self, label: str, size: int = 65536) -> bytes:
        agent = self._agents.get(label)
        if agent is None:
            raise OwnerError(f"no terminal owned here for {label}")
        try:
            return os.read(agent.master_fd, size)
        except OSError as exc:
            if exc.errno in (errno.EIO, errno.EBADF):
                # EOF on the master means the agent's tty closed, so the process
                # is on its way out — reap it here or nothing ever will.
                self._agents.pop(label, None)
                self._reap(agent)
                return b""
            raise

    @staticmethod
    def _set_window(fd: int, rows: int, cols: int) -> None:
        try:
            fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except OSError as exc:
            logger.debug("fleet owner: cannot set window size: %s", exc)

    def resize(self, label: str, rows: int, cols: int) -> None:
        agent = self._agents.get(label)
        if agent is None:
            raise OwnerError(f"no terminal owned here for {label}")
        self._set_window(agent.master_fd, rows, cols)

    # -- what this owner can say about the world -------------------------- #

    def owned(self) -> List[OwnedAgent]:
        return list(self._agents.values())

    def population_of(self, unit_or_label: str) -> str:
        """`started-here` only while THIS owner holds the handle.

        An agent started by a previous owner is `foreign` to this one even
        though the framework started it, because the property the surface needs
        is "can I type into this", and that is a fact about the handle rather
        than about history.
        """
        label = unit_or_label
        if label.startswith(scopes.SCOPE_PREFIX):
            label = scopes.Scope(unit=label, pid=None, cgroup="", active=False).label
        return STARTED_HERE if label in self._agents else FOREIGN

    def orphans(self) -> List[Scope]:
        """Framework scopes that are running with no terminal held here.

        These are the agents of a previous owner: alive in their own cgroup,
        unreachable because the only handle to their terminal died with whoever
        held it. They are what `recover()` exists for.
        """
        return [
            scope for scope in scopes.list_scopes()
            # A scope that is shutting down but still holds a pid is an orphan
            # too — and the one most worth showing, because it is the one that
            # will not die on its own.
            if not scopes.scope_is_gone(scope) and self.population_of(scope.unit) == FOREIGN
        ]


# --------------------------------------------------------------------------- #
# recovery — task 5.11
# --------------------------------------------------------------------------- #

def _refuse_if_the_session_is_running(session_id: str) -> None:
    """Task 5.7: never resume a session a live process is bound to.

    Stopping the scope (below) covers the agents THIS framework started. It says
    nothing about the rest, and the rest is most of them: a session started by
    hand in a terminal has no scope, so every check based on units would clear it
    for resume — and a resume against a live session forks its conversation into
    a branch the running original never sees, with nothing reporting it
    (design §6.1). That is the one failure in this module that is silent, so the
    check is on the session rather than on the unit.

    **Undeterminable liveness is treated as live**, which is why this asks
    `live_session_ids()` — the one reader in `discovery` that returns `None`
    rather than an empty set when it cannot look. Every other reader flattens
    that into "no agents", which is right for a listing and exactly backwards
    here: it would read as "nothing is running" and clear the way.
    """
    live = discovery.live_session_ids()
    if live is None:
        raise OwnerError(
            f"cannot determine whether {session_id} is running; refusing to resume — "
            "a resume against a live session forks its conversation silently"
        )
    if session_id in live:
        raise OwnerError(
            f"session {session_id} is bound to a live process; refusing to resume — "
            "a resume against a live session forks its conversation silently"
        )


def recover(
    owner: AgentOwner,
    *,
    unit: str,
    session_id: str,
    cwd: str,
    label: Optional[str] = None,
    resume_argv: Optional[Sequence[str]] = None,
) -> OwnedAgent:
    """Replace an orphaned agent: stop its scope, then resume its session.

    **Not reattachment.** The terminal handle died with the previous owner and
    cannot be reacquired — `/proc/<pid>/fd/<n>` for a pty master points at
    `/dev/ptmx`, and opening that allocates a new pair (measured 2026-08-17). So
    what survives is the *transcript*, and the honest act is to start a new
    process on it.

    **The order is the whole of it, and it is enforced here rather than trusted
    to a caller.** Resuming while the old scope is still up produces two live
    sessions appending to one transcript, neither aware of the other, with
    nothing reporting it (design §6.1). This function stops first and verifies
    the stop before it resumes; a scope that will not die aborts the recovery
    rather than proceeding into a fork.
    """
    unit = scopes._as_scope(unit)
    _refuse_if_the_session_is_running(session_id)
    scope = scopes.get(unit)
    if scope is not None and not scopes.is_gone(unit):
        logger.info("fleet owner: recovery stopping %s before resume", unit)
        if not scopes.stop(unit):
            raise OwnerError(
                f"{unit} is still active after stop; refusing to resume — "
                "a resume against a live session forks its conversation silently"
            )
    # Re-read rather than trust the stop's return: the check that matters is the
    # state now, not the call's opinion of it a moment ago.
    still = scopes.get(unit)
    if still is not None and not scopes.is_gone(unit):
        # ⚠ The re-read is only a guard if it asks a DIFFERENT question than the
        # one that can be wrong. It used to ask `still.active`, which is exactly
        # what `stop()` had already mis-answered — so the check that exists to
        # prevent the §6.1 silent fork passed on a scope whose agent was alive.
        raise OwnerError(
            f"{unit} is not gone (state {still.state or '?'}, pids {still.pids}); refusing to resume"
        )

    argv = list(resume_argv or ["claude", "--dangerously-skip-permissions", "--resume", session_id])
    return owner.start(
        argv,
        label=label or scopes.Scope(unit=unit, pid=None, cgroup="", active=False).label,
        cwd=cwd,
        resumed_session=session_id,
    )
