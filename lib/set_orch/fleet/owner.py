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
import shutil
import signal
import struct
import termios
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

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


def _drain(fd: int, *, deadline: float = 0.4, cap: int = 1200) -> str:
    """Whatever the child already wrote to its terminal. Never blocks.

    A failed start's only explanation is usually the text the child printed
    before dying, and that text is on the pty this owner holds — nowhere else.
    Read non-blocking with a short deadline, because the alternative is a caller
    hanging on a child that is not going to say anything.

    Terminal control sequences are stripped: they are noise in an error message,
    and one of them can move a reader's cursor when the message is echoed.
    """
    import re
    import select

    chunks: list = []
    end = time.monotonic() + deadline
    try:
        while time.monotonic() < end and sum(len(c) for c in chunks) < cap:
            ready, _, _ = select.select([fd], [], [], max(0.0, end - time.monotonic()))
            if not ready:
                break
            data = os.read(fd, 4096)
            if not data:
                break
            chunks.append(data)
    except OSError:
        pass
    text = b"".join(chunks).decode("utf-8", errors="replace")
    text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text)
    return " ".join(text.split())[-cap:]


def _reap(pid: int) -> Optional[int]:
    """The child's wait status if it has already ended, else `None` — never blocks.

    `None` means *still running*, which is a different answer from *ended with
    status 0* and must not collapse into it: the first says the scope is the
    thing that failed, the second says the child is.
    """
    try:
        done, status = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        # Already reaped elsewhere. We cannot say how it ended, and saying nothing
        # is correct — inventing a status here would be a false value.
        return None
    except OSError:
        return None
    return status if done == pid else None


class OwnerError(RuntimeError):
    """An agent could not be started, written to, or recovered."""


class CommandNotResolvable(OwnerError):
    """The command a start names cannot be executed in the environment the child gets.

    A subclass rather than a message, because the two failures need different
    answers: this one is knowable BEFORE anything is claimed, and the caller can
    act on it (install the command, fix the service's PATH). The generic
    `OwnerError` covers what is only knowable afterwards.
    """


class EnvironmentNotDelivered(OwnerError):
    """A variable the resolver returned is absent from — or altered in — the child env.

    Its own class, for the same reason `CommandNotResolvable` has one: this is
    knowable BEFORE anything is created, and it names a framework defect rather
    than a caller mistake. The caller cannot fix it by supplying different input.

    ⚠ Why a guard exists at all when `build_child_env` applies the caller's
    variables last and therefore cannot lose one today. Because "cannot today" is
    a property of five lines that two tracks edit at once, and a lost variable
    does NOT fail loudly: measured 2026-08-29, dropping
    `CLAUDE_CODE_MAX_CONTEXT_TOKENS` produces a working agent that compacts in a
    loop and reads from outside as a slow model. The failure direction is silent
    success, which is the one direction a guard has to cover.
    """


def assert_env_survived(resolved: Dict[str, str], child_env: Dict[str, str]) -> None:
    """Refuse unless every resolved variable is in `child_env` with its value.

    Checked against the environment *about to be used*, not against the mapping
    that was passed in — comparing the input to itself would measure a proxy and
    pass whatever the builder did with it.
    """
    lost = [
        key for key, value in (resolved or {}).items()
        if child_env.get(key) != value
    ]
    if lost:
        # The NAMES, not the values: a resolved environment carries credentials,
        # and this message reaches a log and an HTTP answer.
        raise EnvironmentNotDelivered(
            "the resolved environment did not survive into the child: "
            + ", ".join(sorted(lost))
        )


def build_child_env(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """The environment a started child gets. One owner, one place, one order.

    Extracted from `start()` on 2026-08-29 because two tracks needed it at once:
    the command resolution below has to see the FINAL environment, and the
    provider/model track supplies its own keys through `env`. Two sessions
    editing one inline block is the collision this removes.

    **The order is the contract, not a detail.** The `CLAUDE*` strip runs BEFORE
    the caller's `env` is applied, and reversing the two would silently drop a
    key the caller deliberately set — `CLAUDE_CODE_MAX_CONTEXT_TOKENS` being the
    measured example, whose loss is not an error but a compaction loop that looks
    from outside like a slow model. Held by a test rather than by this paragraph.

    The strip itself: a session started as another session's child writes no
    transcript at all (measured 2026-08-18), which makes the agent invisible to
    every source the fleet reads. Anything the framework starts must not inherit
    that marker.
    """
    child_env = dict(os.environ)
    for key in [k for k in child_env if k.startswith("CLAUDE")]:
        child_env.pop(key, None)
    child_env["TERM"] = "xterm-256color"
    child_env.update(env or {})
    return child_env


def resolve_in_env(command: str, env: Dict[str, str]) -> Optional[str]:
    """Where `command` would be found by a child running with `env` — or `None`.

    ⚠ The environment is a PARAMETER and nothing here reads `os.environ`. That is
    the whole point: measured 2026-08-29, this service's own PATH and the PATH a
    started child gets are not the same string, and resolving against the wrong
    one is the "measure a proxy instead of the thing" class — the check passes
    while the child still cannot exec.

    A command containing a separator is a path, not a name: PATH is not consulted
    for it, exactly as `execvp` does not.
    """
    if not command:
        return None
    if os.sep in command or (os.altsep and os.altsep in command):
        return command if os.access(command, os.X_OK) and os.path.isfile(command) else None
    path = env.get("PATH")
    if path is None:
        # ⚠ NOT `shutil.which(command, path=None)`. Measured while writing the test
        # for this function: `which` treats `None` as "use os.environ['PATH']", so an
        # environment carrying no PATH at all would have resolved against THIS
        # process's — the exact proxy this function exists to avoid, and failing in
        # the direction that passes the check and leaves the child unable to exec.
        # An env with no PATH is refused instead, which is also fail-closed.
        return None
    return shutil.which(command, path=path)


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
    #: Who asked for this agent, as a seat identity. RECORDED rather than
    #: derived, because process ancestry cannot answer it: measured 2026-08-19,
    #: an agent started here has the owner — a plain python process — as its
    #: parent, and systemd above that, so no walk up the tree will ever find the
    #: requester. A relation that only exists at the moment of the act has to be
    #: written down during it.
    requested_by: Optional[str] = None


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
        requested_by: Optional[str] = None,
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

        child_env = build_child_env(env)
        # Before anything is created. A refusal here costs nothing; the same
        # defect discovered later is an agent that runs on the wrong provider.
        assert_env_survived(env or {}, child_env)

        # Resolve HERE — after the child env is final (the `CLAUDE*` strip above and
        # the caller's `env=` are both already applied) and before anything is
        # claimed. Both halves are requirements rather than placement preferences:
        #
        # * resolving earlier would consult a different environment than the child
        #   gets, and pass while the child still failed;
        # * refusing later means the caller waits out `await_unit`'s liveness poll
        #   and is then told the SCOPE did not become active — a true sentence about
        #   the symptom that points away from the missing command. Measured
        #   2026-08-29: `systemd-run` exits 1 immediately, no unit ever registers,
        #   and the four-second wait bought the reader nothing but a wrong cause.
        if not resolve_in_env(argv[0], child_env):
            raise CommandNotResolvable(
                f"{argv[0]} cannot be executed by the started child: "
                f"not found on PATH={child_env.get('PATH', '')!r}"
            )

        pid, master_fd = pty.fork()
        if pid == 0:  # pragma: no cover - executed in the forked child
            try:
                # How the child becomes the agent is the platform's business, not
                # this module's. It was `systemd-run` inline here until the
                # backend split (design D1a) — the one systemd command that had
                # escaped the scopes package, and the reason the macOS start path
                # could not work however the rest of the port went.
                scopes.child_exec(unit, argv, cwd, child_env)
            except BaseException:
                os._exit(127)

        self._set_window(master_fd, rows, cols)

        # The guarantee this whole module rests on. Refuse rather than warn: an
        # agent inside the dashboard's own lifetime would give the surface a
        # survival promise that is simply false. `adopt` raises rather than
        # returning a bad scope, so there is no state where this succeeded and
        # the promise is absent.
        try:
            scope = scopes.adopt(unit, pid, cwd)
        except scopes.ScopeError as exc:
            # ⚠ Ask the CHILD what happened before quoting the scope. A scope that
            # never became active and a child that died are two different failures
            # that arrive here as one exception, and only the second one can say
            # anything actionable. Reporting the scope for both is how a caller
            # gets a true sentence about the symptom and nothing about the cause —
            # the shape measured on 2026-08-29, where an unresolvable command was
            # reported as a scope that did not become active.
            # What the CHILD said before it died, off the pty this owner holds.
            # Measured 2026-08-29: an engine refusing a bad seat exits at once,
            # the scope never registers a cgroup, and the caller was told
            # "systemd reports no cgroup" — a true sentence about the symptom,
            # while the engine's own explanation sat unread in the terminal.
            # ⚠ Drained BEFORE the fd is closed; afterwards there is nothing left
            # to read and the error would be as blind as before.
            said = _drain(master_fd)
            os.close(master_fd)
            gone = _reap(pid)
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
            detail = f": {said}" if said else ""
            if gone is not None:
                raise OwnerError(
                    f"the agent was not started: the child {_describe_exit(gone)}{detail}"
                ) from exc
            raise OwnerError(f"{exc}; the agent was not started{detail}") from exc
        cgroup = scope.cgroup
        agent = OwnedAgent(
            label=label, unit=unit, pid=scope.pid, cwd=cwd,
            master_fd=master_fd, child_pid=pid, resumed_session=resumed_session,
            requested_by=requested_by,
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
        if agent is not None:
            unit = agent.unit
        else:
            # Deriving is right for an ORPHAN — a scope this owner does not hold,
            # whose unit was named from its label by whoever started it. It is
            # wrong for a label that was RENAMED: the derived unit is then a live
            # agent's unit, held here under a different name, and stopping it
            # through the old name would make the old label addressable again
            # through a back door the map has already closed.
            unit = scopes.unit_name(label)
            held = self._held_by_unit(unit)
            if held is not None:
                raise OwnerError(
                    f"nothing is held under {label}; {unit} belongs to {held.label}. "
                    "A renamed agent is reachable under its current name only"
                )

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

    def _held_by_unit(self, unit: str) -> Optional[OwnedAgent]:
        """The agent this owner holds in `unit`, or None.

        The map is keyed by LABEL, and after a rename a label no longer predicts
        a unit — which is the whole point of storing the unit. So the question
        "is this unit one of mine" has to be asked of the units themselves.
        """
        return next((a for a in self._agents.values() if a.unit == unit), None)

    def rename(self, label: str, new_label: str) -> OwnedAgent:
        """Give a held agent a different name, and change nothing else.

        The process, its pty, its scope and its session are untouched: this
        re-keys a dictionary. That is possible only because the unit is a stored
        fact — a unit name cannot be changed once systemd knows it, so an
        implementation that re-derived the unit from the label would have to
        destroy and re-create the agent to rename it, taking the in-flight turn
        and the terminal history with it.

        **A taken name is refused, never derived around.** Restore derives a free
        variant because the alternative there is losing an agent while nobody is
        watching; a rename is a deliberate act by someone looking at the screen,
        and a name they did not choose appearing instead is a false value they
        have no reason to question.
        """
        agent = self._agents.get(label)
        if agent is None:
            raise OwnerError(
                f"this owner does not hold {label}; only an agent whose terminal "
                "the framework holds can be renamed — a name the runtime derived "
                "belongs to the runtime"
            )
        wanted = str(new_label).strip()
        if not wanted:
            raise OwnerError("a new name is required; an agent cannot be nameless")
        if wanted == label:
            return agent
        holder = self._agents.get(wanted)
        if holder is not None:
            raise OwnerError(
                f"{wanted} is already held here (pid {holder.pid}); "
                "choose another name or rename that agent first"
            )
        self._agents[wanted] = self._agents.pop(label)
        agent.label = wanted
        logger.info(
            "fleet owner: renamed %s to %s (unit %s, pid %s — unchanged)",
            label, wanted, agent.unit, agent.pid,
        )
        return agent

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

    @staticmethod
    def _get_window(fd: int) -> Optional[Tuple[int, int]]:
        """The pty's CURRENT geometry, asked of the kernel.

        Read rather than remembered, deliberately. A stored copy of a size that
        `resize` also writes is a second place, and it drifts the first time
        anything else changes the window — another viewer, the program itself,
        a `stty`. The question this answers is *what geometry was the buffered
        screen drawn at*, and only the fd knows.

        `None` when the fd cannot answer (closed, or not a tty): the caller then
        says nothing rather than guessing, because a wrong geometry is worse
        here than an absent one — it would be applied.
        """
        try:
            packed = fcntl.ioctl(fd, termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
        except OSError as exc:
            logger.debug("fleet owner: cannot read window size: %s", exc)
            return None
        rows, cols, _, _ = struct.unpack("HHHH", packed)
        if rows <= 0 or cols <= 0:
            return None
        return rows, cols

    def window(self, label: str) -> Optional[Tuple[int, int]]:
        """`(rows, cols)` of one owned terminal, or `None` if it cannot be read."""
        agent = self._agents.get(label)
        if agent is None:
            raise OwnerError(f"no terminal owned here for {label}")
        return self._get_window(agent.master_fd)

    # -- what this owner can say about the world -------------------------- #

    def owned(self) -> List[OwnedAgent]:
        return list(self._agents.values())

    def label_for_fd(self, master_fd: int) -> Optional[str]:
        """The name this owner holds `master_fd` under RIGHT NOW, or None.

        The map is keyed by label and a rename re-keys it, so a label captured
        at any earlier moment stops naming an agent the instant it is renamed —
        while the fd goes on naming the same pty for as long as the agent lives.
        Anything long-lived that watches a terminal must therefore ask this
        rather than remember a name (measured 2026-08-23: the drain remembered
        one, and a rename killed it — see `ownerd._drain`).
        """
        return next(
            (a.label for a in self._agents.values() if a.master_fd == master_fd), None
        )

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
    unit = scopes.as_unit_name(unit)
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
