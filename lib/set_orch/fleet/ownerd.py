"""The agent owner as a service — the socket the dashboard talks to (task 5.8).

`owner.py` holds the ptys and the scopes. This module is the *only* thing that
lets another process reach it: an `AF_UNIX` stream speaking the JSON-lines
protocol in `protocol.py`, one passthrough per `AgentOwner` method.

**Why a separate service at all** is in `owner.py`'s header and in
`templates/systemd/set-agent-owner.service`: the dashboard restarts on every
crash and every deploy, and an agent started from it joined its control group
and died with it (finding CB-1).

**Why this file must stay boring.** This service's uptime IS every held agent's
uptime — a pty master cannot be reacquired, so when this process exits, every
pty-attached agent it holds reaches EOF on its own tty and exits. A line of
business logic added here is a future outage of every running agent. Everything
below is therefore dispatch, and the one piece of real behaviour is the drain,
which is not a feature but a precondition:

**The drain, and the measurement that makes it mandatory.** A pty's buffer is
small and a writer blocks when it fills. Measured 2026-08-18 on this machine: a
child writing to its own tty with nobody reading the master stopped after
**17 408 bytes** of the 4 MB it was asked to write, and a **single** drain of the
master let it advance exactly **4 096 bytes** further before stopping again. So
an agent started under a framework-owned pty that nobody reads does not fail —
it *freezes*, after roughly one screenful, looking from the outside like an agent
that is thinking. Holding a master without draining it is not neutral.

**Nothing is persisted.** Drained bytes go into a bounded in-memory tail and
nowhere else — not to disk, not to a log. Diagnostics name the stream and the
failure kind, never the content.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import errno
import json
import logging
import os
import signal
import socket
import sys
import time
from typing import Any, Dict, List, Optional

from . import scopes
from .owner import FOREIGN, STARTED_HERE, AgentOwner, OwnedAgent, OwnerError, recover
from .protocol import (
    SUPPORTED_METHODS, Request, Response, make_error, make_frame, make_result,
)

logger = logging.getLogger(__name__)

#: How much of each agent's terminal output is kept in memory. Bounded because
#: it is a tail, not a transcript: the conversation already has a durable home in
#: the session log, and this service is the wrong place to grow a second one.
DEFAULT_TAIL_BYTES = 64 * 1024

#: The default command for a bare interactive session. Matches `owner.recover()`,
#: which resumes with the same argv — the two must not drift, because a resumed
#: agent and a fresh one appearing on the same screen with different permissions
#: would be a difference nothing on the surface explains.
DEFAULT_AGENT_ARGV = ("claude", "--dangerously-skip-permissions")


def default_socket_path() -> str:
    """`$XDG_RUNTIME_DIR/set-agent-owner.sock` — the unit file's `%t` expansion."""
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return os.path.join(runtime, "set-agent-owner.sock")


def _agent_payload(agent: OwnedAgent, *, tail_len: int = 0, dropped: bool = False) -> Dict[str, Any]:
    """What one owned agent looks like on the wire.

    The pty master's file descriptor is deliberately absent: it is a number that
    means something only inside this process, and a descriptor on the wire is an
    invitation to treat it as a handle somewhere it is not one.
    """
    return {
        "label": agent.label,
        "unit": agent.unit,
        "pid": agent.pid,
        "cwd": agent.cwd,
        "population": agent.population,
        "resumed_session": agent.resumed_session,
        "requested_by": agent.requested_by,
        "tail_bytes": tail_len,
        # A tail that has already lost its head says so. Silence here would let a
        # partial stream read as the whole one.
        "tail_truncated": dropped,
    }


class OwnerDaemon:
    """One socket, one `AgentOwner`, one event loop."""

    def __init__(
        self,
        socket_path: str,
        *,
        owner: Optional[AgentOwner] = None,
        tail_bytes: int = DEFAULT_TAIL_BYTES,
    ) -> None:
        self.socket_path = socket_path
        self.owner = owner or AgentOwner()
        self.tail_bytes = tail_bytes
        self.started_at = time.time()
        self._tails: Dict[str, bytearray] = {}
        self._dropped: Dict[str, bool] = {}
        self._drained: Dict[str, int] = {}
        self._server: Optional[asyncio.AbstractServer] = None
        self._stopping = asyncio.Event()
        #: label -> the connections currently watching that terminal. A terminal
        #: may have several viewers; none of them owns it.
        self._subscribers: Dict[str, List[asyncio.StreamWriter]] = {}
        #: the per-connection handler tasks. asyncio makes one per accepted
        #: connection and keeps no public handle on them, so shutdown cannot
        #: reach them without this set — see `shutdown()` for why that matters.
        self._clients: "set[asyncio.Task]" = set()

    # -- the drain -------------------------------------------------------- #

    def _attach_drain(self, agent: OwnedAgent) -> None:
        """Read the pty master continuously, so the agent is never blocked on it."""
        loop = asyncio.get_running_loop()
        self._tails.setdefault(agent.label, bytearray())
        self._dropped.setdefault(agent.label, False)
        self._drained.setdefault(agent.label, 0)
        try:
            # The fd, and deliberately NOT the label: the callback outlives every
            # name the agent will ever have (see `_drain`).
            loop.add_reader(agent.master_fd, self._drain, agent.master_fd)
        except (OSError, ValueError) as exc:
            # An agent nobody drains freezes after about a screenful (see the
            # module header), so this is not a degraded mode — say so loudly.
            logger.error(
                "fleet owner: cannot watch the terminal of %s (%s); it will block once "
                "its pty buffer fills", agent.label, exc,
            )

    def _drain(self, fd: int) -> None:
        """One readable pty master, drained under the name it has NOW.

        **Keyed by fd, and that is the bug this carries a name for.** It used to
        take the label the agent had when the reader was installed, and a rename
        re-keys the owner's map — so the very next read asked for a name nobody
        held, got an `OwnerError`, and the `except` below turned that into an
        empty read, which this method reads as EOF. Measured 2026-08-23 on a live
        agent, six seconds after the rename:

            16:12:28  fleet owner: renamed consumer-app-… to … (pid …, unchanged)
            16:12:34  fleet owner: terminal of consumer-app-… reached EOF after 0 bytes

        Both halves fail in the reassuring direction. The reader is REMOVED, so
        the terminal goes silent for every viewer — a keystroke still reaches the
        pty, it just never echoes, which reads as *I cannot type into it* rather
        than as a broken terminal. And an undrained pty fills after about a
        screenful, at which point the agent itself blocks (see the module
        header): a rename, whose whole promise is that the process is untouched,
        eventually stops it.

        `label_for_fd` asks the owner, so no name is carried across a rename here
        or anywhere downstream — `_rekey` has already moved the stores.
        """
        label = self.owner.label_for_fd(fd)
        if label is None:
            # Not EOF either: nothing is held on this fd, so there is nothing to
            # read and nowhere to put it. Said with the fd, because there is no
            # name left to say it with.
            self._detach_drain(fd)
            logger.warning(
                "fleet owner: nothing is owned on fd %s any more; stopped draining it", fd,
            )
            return
        try:
            data = self.owner.read(label)
        except OwnerError as exc:
            # A refusal is NOT an end-of-file, and reporting it as one is what
            # made a rename look like a terminal that had finished.
            self._detach_drain(fd)
            logger.warning("fleet owner: stopped draining %s: %s", label, exc)
            return
        if not data:
            self._detach_drain(fd)
            logger.info("fleet owner: terminal of %s reached EOF after %d bytes",
                        label, self._drained.get(label, 0))
            return
        self._drained[label] = self._drained.get(label, 0) + len(data)
        tail = self._tails.setdefault(label, bytearray())
        tail.extend(data)
        if len(tail) > self.tail_bytes:
            del tail[: len(tail) - self.tail_bytes]
            self._dropped[label] = True
        self._publish(label, data)

    def _drain_from(self, data: bytes, label: str = "term") -> None:
        """Feed one chunk as though the pty had produced it. Test seam only.

        Named so it cannot be mistaken for a production path: the real drain is
        driven by `loop.add_reader` on a pty master, and a test that reached for
        that would need a pty, a child and a race.
        """
        self._drained[label] = self._drained.get(label, 0) + len(data)
        self._tails.setdefault(label, bytearray()).extend(data)
        self._publish(label, data)

    def _detach_drain(self, fd: int) -> None:
        try:
            asyncio.get_running_loop().remove_reader(fd)
        except (OSError, ValueError, RuntimeError) as exc:
            logger.debug("fleet owner: removing reader for fd %s: %s", fd, exc)

    # -- the stream (task 5.3 / 6.4) ------------------------------------- #

    #: How much unwritten output a viewer may accumulate before it is dropped.
    #: A viewer that cannot keep up must not be able to stall the drain, because
    #: the drain is what keeps the AGENT running (see the module header).
    SLOW_VIEWER_BYTES = 4 * 1024 * 1024

    #: The most RAW output one frame may carry. Not a tuning knob — a protocol
    #: limit, measured on 2026-08-19 against a live terminal.
    #:
    #: A frame is one JSON line, and the payload is base64, so N raw bytes
    #: become 4N/3 on the wire. asyncio's StreamReader refuses a line longer
    #: than 64 KiB by default and raises `LimitOverrunError`, which is NOT the
    #: connection closing: the reading task dies with an exception nobody
    #: retrieves, and the viewer is told the owner hung up on it.
    #:
    #: Both of this file's own sizes crossed that line. `owner.read()` takes up
    #: to 65536 bytes at once, and `tail_bytes` is 65536 — so a replay of a
    #: screen that already held ~48 KiB was not merely at risk, it was
    #: GUARANTEED to kill the connection. That is why the first attach to a
    #: fresh agent worked (0 bytes replayed) and the reattach after a minute of
    #: output never could.
    #:
    #: 32 KiB raw → ~43.7 KB of base64 plus a short envelope: under the limit
    #: with room for the JSON around it, and still one syscall's worth.
    MAX_FRAME_BYTES = 32 * 1024

    def _frames(self, label: str, data: bytes, replay: bool = False) -> List[bytes]:
        """Encode one chunk as one or more wire frames, none over the limit.

        Split rather than truncated: a terminal replay with a hole in the middle
        renders as garbage — escape sequences do not survive being cut — and a
        hole that is not announced is worse than a slow screen.
        """
        out: List[bytes] = []
        for start in range(0, max(len(data), 1), self.MAX_FRAME_BYTES):
            piece = data[start : start + self.MAX_FRAME_BYTES]
            if not piece:
                break
            out.append(
                (make_frame(label, base64.b64encode(piece).decode("ascii"), replay=replay) + "\n").encode("utf-8")
            )
        return out

    def _publish(self, label: str, data: bytes) -> None:
        """Push one chunk to every viewer of this terminal.

        Written without awaiting, because this runs inside the drain callback and
        the drain must never block: an owner that waits on a slow browser is an
        owner that is not reading the pty, and an agent whose pty is not read
        freezes after about a screenful.

        So backpressure is handled by DROPPING the viewer rather than by slowing
        the source. A dropped viewer sees its stream end and can reattach — a
        frozen agent looks like one that is thinking.
        """
        watchers = self._subscribers.get(label)
        if not watchers:
            return
        frames = self._frames(label, data)
        for writer in list(watchers):
            try:
                pending = writer.transport.get_write_buffer_size()  # type: ignore[union-attr]
            except (AttributeError, TypeError):
                pending = 0
            if writer.is_closing() or pending > self.SLOW_VIEWER_BYTES:
                logger.warning(
                    "fleet owner: dropping a viewer of %s (%s)",
                    label, "closing" if writer.is_closing() else f"{pending} bytes behind",
                )
                self._unsubscribe(label, writer)
                continue
            try:
                for frame in frames:
                    writer.write(frame)
            except (ConnectionResetError, BrokenPipeError, RuntimeError) as exc:
                logger.debug("fleet owner: viewer of %s went away: %s", label, exc)
                self._unsubscribe(label, writer)

    def _subscribe(self, label: str, writer: asyncio.StreamWriter) -> None:
        self._subscribers.setdefault(label, []).append(writer)
        logger.info(
            "fleet owner: a viewer attached to %s (%d watching)",
            label, len(self._subscribers[label]),
        )

    def _unsubscribe(self, label: str, writer: asyncio.StreamWriter) -> None:
        watchers = self._subscribers.get(label)
        if not watchers or writer not in watchers:
            return
        watchers.remove(writer)
        if not watchers:
            self._subscribers.pop(label, None)
        logger.info("fleet owner: a viewer detached from %s (%d left)", label, len(watchers))

    #: Every per-label store this daemon keeps. Named ONCE, so that a rename and
    #: a forget cannot disagree about what "everything about this label" is —
    #: and so that a store added later is a one-line change here rather than a
    #: silent omission in two places. `_rekey` and the rename test both read it.
    LABEL_KEYED = ("_tails", "_dropped", "_drained", "_subscribers")

    def _rekey(self, label: str, new_label: str) -> None:
        """Carry every per-label store from one name to the other.

        The viewers move rather than being dropped: a rename must be invisible to
        the process, and a browser whose terminal went silent because the name
        changed underneath it would be exactly the opposite of invisible.
        """
        for name in self.LABEL_KEYED:
            store = getattr(self, name)
            if label in store:
                store[new_label] = store.pop(label)

    def _forget(self, label: str) -> None:
        self._tails.pop(label, None)
        self._dropped.pop(label, None)
        self._drained.pop(label, None)
        # The viewers are told by their stream ending, not by a message: a
        # terminal that stopped and a connection that dropped look the same from
        # the browser, and both mean "reattach or give up".
        for writer in self._subscribers.pop(label, []):
            if not writer.is_closing():
                writer.close()

    # -- dispatch --------------------------------------------------------- #

    #: Methods whose meaning depends on WHICH connection asked. Everything else
    #: is a fact about the owner and answers the same on any connection.
    CONNECTION_SCOPED = frozenset({"attach", "detach"})

    async def dispatch(
        self, request: Request, writer: Optional[asyncio.StreamWriter] = None
    ) -> Response:
        if request.method not in SUPPORTED_METHODS:
            return make_error(
                request.id,
                f"unknown method {request.method!r}; this owner answers "
                + ", ".join(sorted(SUPPORTED_METHODS)),
            )
        if request.method in self.CONNECTION_SCOPED and writer is None:
            return make_error(
                request.id,
                f"{request.method} is meaningless without a connection to attach; "
                "it cannot be issued out of band",
            )
        handler = getattr(self, f"_do_{request.method}")
        try:
            if request.method in self.CONNECTION_SCOPED:
                result = await handler(request.params, writer)
            else:
                result = await handler(request.params)
        except OwnerError as exc:
            # An expected refusal — a label already owned, a scope that will not
            # die, a terminal this owner does not hold. Not a daemon fault.
            logger.info("fleet owner: refused %s: %s", request.method, exc)
            return make_error(request.id, str(exc))
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("fleet owner: bad %s request: %s", request.method, exc)
            return make_error(request.id, f"bad request: {exc}")
        except Exception as exc:  # pragma: no cover - the unexpected, logged not swallowed
            logger.exception("fleet owner: %s failed", request.method)
            return make_error(request.id, f"{type(exc).__name__}: {exc}")
        return make_result(request.id, result)

    async def _do_health(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ok": True,
            "pid": os.getpid(),
            "uptime_seconds": round(time.time() - self.started_at, 1),
            "socket": self.socket_path,
            # The number that matters operationally: restarting this service
            # ends this many agents.
            "held": len(self.owner.owned()),
        }

    async def _do_list(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            _agent_payload(
                a,
                tail_len=len(self._tails.get(a.label, b"")),
                dropped=self._dropped.get(a.label, False),
            )
            for a in self.owner.owned()
        ]

    async def _do_orphans(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        orphans = await asyncio.to_thread(self.owner.orphans)
        return [
            {"unit": s.unit, "label": s.label, "pid": s.pid, "cgroup": s.cgroup}
            for s in orphans
        ]

    async def _do_start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        label = params["label"]
        cwd = params["cwd"]
        argv = list(params.get("argv") or DEFAULT_AGENT_ARGV)
        # Blocking: `start` waits for systemd to report the scope active. Off the
        # loop, or every other agent's drain stalls behind it.
        agent = await asyncio.to_thread(
            self.owner.start,
            argv,
            label=label,
            cwd=cwd,
            env=params.get("env"),
            rows=int(params.get("rows", 40)),
            cols=int(params.get("cols", 120)),
            requested_by=params.get("requested_by"),
        )
        self._attach_drain(agent)
        return _agent_payload(agent)

    async def _do_stop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        label = params["label"]
        agent = next((a for a in self.owner.owned() if a.label == label), None)
        if agent is not None:
            self._detach_drain(agent.master_fd)
        result = await asyncio.to_thread(self.owner.stop, label)
        self._forget(label)
        return result

    async def _do_rename(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Rename a held agent. Nothing is stopped, started or resumed.

        Not run on a thread: this touches dictionaries only, and the owner's map
        must not be mutated from a thread while the loop reads it.
        """
        label = params["label"]
        new_label = params["new_label"]
        agent = self.owner.rename(label, new_label)
        if agent.label != label:
            self._rekey(label, agent.label)
        return _agent_payload(
            agent,
            tail_len=len(self._tails.get(agent.label, b"")),
            dropped=self._dropped.get(agent.label, False),
        )

    async def _do_recover(self, params: Dict[str, Any]) -> Dict[str, Any]:
        agent = await asyncio.to_thread(
            recover,
            self.owner,
            unit=params["unit"],
            session_id=params["session_id"],
            cwd=params["cwd"],
            label=params.get("label"),
            resume_argv=params.get("resume_argv"),
        )
        self._attach_drain(agent)
        return _agent_payload(agent)

    async def _do_write(self, params: Dict[str, Any]) -> Dict[str, Any]:
        import base64
        data = base64.b64decode(params["data_b64"])
        written = self.owner.write(params["label"], data)
        return {"written": written}

    async def _do_resize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self.owner.resize(params["label"], int(params["rows"]), int(params["cols"]))
        return {"ok": True}

    async def _do_attach(
        self, params: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> Dict[str, Any]:
        """Turn this connection full-duplex for one terminal.

        After this the owner pushes frames as output arrives, and the same
        connection keeps accepting `write`/`resize`/`detach` — one socket for
        both directions, because a terminal split across two connections can
        deliver a keystroke before the output that prompted it.

        The buffered tail is sent first and **marked as replay**, so the viewer
        sees the screen as it already is rather than starting blank halfway
        through a session. A viewer that cannot tell replay from live output has
        no way to know whether what it is looking at is happening now.
        """
        label = params["label"]
        if label not in self._tails:
            raise OwnerError(f"no terminal owned here for {label}")
        self._subscribe(label, writer)
        tail = bytes(self._tails[label])
        if tail:
            for frame in self._frames(label, tail, replay=True):
                writer.write(frame)
        # THE GEOMETRY THE REPLAY WAS DRAWN AT — B-16.
        #
        # A terminal is a fixed-grid device: the buffered tail is bytes a program
        # laid out for a specific number of columns. A viewer that renders it at
        # a different width does not adapt the screen, it destroys it — and the
        # damage is silent, because the result still looks like a terminal. The
        # viewer had no way to know the width: this ack carried how MUCH was
        # replayed and never what shape it was.
        #
        # Sent as `null` rather than a guess when the fd cannot answer. A wrong
        # geometry here is worse than an absent one, because the viewer would
        # apply it.
        window = None
        try:
            window = self.owner.window(label)
        except OwnerError:  # pragma: no cover - the label was checked above
            logger.debug("fleet owner: no window geometry for %s", label)
        return {
            "attached": label,
            "replayed_bytes": len(tail),
            # A replay that begins mid-stream says so; the viewer's first screen
            # is then honestly incomplete rather than silently so.
            "replay_truncated": self._dropped.get(label, False),
            "viewers": len(self._subscribers.get(label, [])),
            "rows": window[0] if window else None,
            "cols": window[1] if window else None,
        }

    async def _do_detach(
        self, params: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> Dict[str, Any]:
        """Stop watching. Never stops the AGENT — that is `stop`, and it is a
        different act with a different consequence (task 5.4: stopping is
        deliberate, never a side effect of closing a view)."""
        label = params["label"]
        self._unsubscribe(label, writer)
        return {"detached": label, "viewers": len(self._subscribers.get(label, []))}

    async def _do_tail(self, params: Dict[str, Any]) -> Dict[str, Any]:
        import base64
        label = params["label"]
        if label not in self._tails:
            raise OwnerError(f"no terminal owned here for {label}")
        tail = bytes(self._tails[label])
        limit = int(params.get("max_bytes", self.tail_bytes))
        clipped = tail[-limit:] if limit < len(tail) else tail
        return {
            "data_b64": base64.b64encode(clipped).decode("ascii"),
            "bytes": len(clipped),
            "drained_total": self._drained.get(label, 0),
            # True when bytes were lost before this tail begins — either the ring
            # wrapped or this answer clipped it. A tail that silently starts
            # mid-stream is the false-absence class.
            "truncated": self._dropped.get(label, False) or len(clipped) < len(tail),
        }

    # -- the socket ------------------------------------------------------- #

    async def _serve_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._clients.add(task)
        try:
            while True:
                line = await reader.readline()
                if not line:
                    return
                try:
                    request = Request.from_json(line.decode("utf-8"))
                except (ValueError, UnicodeDecodeError) as exc:
                    response: Response = make_error("", f"unparseable request: {exc}")
                else:
                    response = await self.dispatch(request, writer)
                writer.write((response.to_json() + "\n").encode("utf-8"))
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            logger.debug("fleet owner: client went away mid-request")
        finally:
            if task is not None:
                self._clients.discard(task)
            # A connection that goes away is a viewer that went away. Nothing
            # else reports it, and a subscriber list that only grows would push
            # into dead transports for the life of the service.
            for label in list(self._subscribers):
                self._unsubscribe(label, writer)
            # `close()` schedules a callback on the loop, so a transport closed
            # after the loop is gone raises `RuntimeError: Event loop is closed`
            # — and this `finally` may be running inside the garbage collector,
            # where nothing can catch it. Python reports that as an *unraisable*
            # exception: the traceback is printed, the interpreter carries on,
            # and no caller ever sees a failure. Measured 2026-08-19: four per
            # test session, and the symptom that finally surfaced was a
            # `KeyError` in an unrelated import lock (task 10.3).
            try:
                writer.close()
            except RuntimeError as exc:
                logger.debug(
                    "fleet owner: closing a client transport after the loop: %s", exc
                )

    def _claim_socket(self) -> None:
        """Take the socket path, or refuse — never clobber a live owner.

        Two owners on one path is the worst failure this service has: the second
        answers `list` with agents it does not hold, and a `write` addressed to a
        real agent lands nowhere. Unlinking a socket is cheap and irreversible,
        so the question asked first is whether anything is listening — not
        whether a file is present, which a crashed owner leaves behind too.
        """
        if not os.path.exists(self.socket_path):
            return
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        probe.settimeout(1.0)
        try:
            probe.connect(self.socket_path)
        except OSError as exc:
            if exc.errno in (errno.ECONNREFUSED, errno.ENOENT):
                logger.warning(
                    "fleet owner: removing the stale socket at %s (nothing listening: %s)",
                    self.socket_path, exc.strerror,
                )
                os.unlink(self.socket_path)
                return
            raise
        finally:
            probe.close()
        raise OwnerError(
            f"another agent owner is already listening on {self.socket_path}; "
            "refusing to start a second one — it would answer for terminals it does not hold"
        )

    async def serve(self) -> None:
        self._claim_socket()
        self._server = await asyncio.start_unix_server(self._serve_client, path=self.socket_path)
        os.chmod(self.socket_path, 0o600)
        logger.info(
            "fleet owner: listening on %s (pid %s)", self.socket_path, os.getpid()
        )
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._request_stop, sig)
        async with self._server:
            await self._stopping.wait()
        await self.shutdown()

    def _request_stop(self, sig: signal.Signals) -> None:
        held = len(self.owner.owned())
        # Not a warning about a mistake — the mechanism. Stated with the number
        # because "the service stopped" and "eleven agents ended" are the same
        # event and only one of them is obvious from the outside.
        logger.info(
            "fleet owner: %s received; %d held agent(s) will end with this process, "
            "because a pty master cannot outlive the process holding it",
            sig.name, held,
        )
        self._stopping.set()

    async def shutdown(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        # `wait_closed()` answers about the LISTENING sockets, not about the
        # handlers — on this runtime it returns with client coroutines still
        # suspended on `readline()`. Whatever happens to them then happens after
        # the loop is gone: the `finally` above runs from the garbage collector,
        # so the unsubscribe is skipped and the close raises where nothing can
        # catch it. Cancelling here runs each handler's cleanup while the loop
        # is still alive, which is the only moment it can do its job.
        clients = list(self._clients)
        for task in clients:
            task.cancel()
        if clients:
            await asyncio.gather(*clients, return_exceptions=True)
            logger.debug("fleet owner: %d client handler(s) cancelled", len(clients))
        for agent in self.owner.owned():
            self._detach_drain(agent.master_fd)
        try:
            os.unlink(self.socket_path)
        except OSError as exc:
            logger.debug("fleet owner: unlinking %s: %s", self.socket_path, exc)
        logger.info("fleet owner: stopped")


# --------------------------------------------------------------------------- #
# entry point — installed as `set-agent-owner` (pyproject `[project.scripts]`)
# --------------------------------------------------------------------------- #

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="set-agent-owner",
        description="Holds the terminals of agents started from the fleet screen.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    serve_cmd = sub.add_parser("serve", help="run the owner service")
    serve_cmd.add_argument("--socket", default=None, help="socket path")
    serve_cmd.add_argument("--tail-bytes", type=int, default=DEFAULT_TAIL_BYTES)
    serve_cmd.add_argument("--log-level", default="INFO")

    health_cmd = sub.add_parser("health", help="ask a running owner how it is")
    health_cmd.add_argument("--socket", default=None, help="socket path")

    args = parser.parse_args(argv)
    socket_path = args.socket or default_socket_path()

    if args.command == "health":
        from .owner_client import OwnerClient, OwnerUnavailable
        try:
            print(json.dumps(OwnerClient(socket_path).health(), indent=2))
        except OwnerUnavailable as exc:
            print(str(exc), file=sys.stderr)
            return 3
        return 0

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    daemon = OwnerDaemon(socket_path, tail_bytes=args.tail_bytes)
    try:
        asyncio.run(daemon.serve())
    except OwnerError as exc:
        logger.error("%s", exc)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
