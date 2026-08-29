"""Client for the agent owner — how the dashboard reaches it (task 5.8).

Synchronous, because the caller is a FastAPI route and the requests are short.

**This client deliberately does NOT auto-start the owner, and that is the one
place it departs from the removed memory daemon's client, which did.** The departure is the
whole reason the split exists. A daemon started from inside the web service
becomes a child of `set-web.service` and joins its control group; the unit runs
with `KillMode=control-group`, so the next deploy or crash-restart would take the
owner — and with it every agent's terminal, and with that every pty-attached
agent — down with it (finding CB-1). Convenience here would silently rebuild the
defect the second service was created to remove.

So an unreachable owner is reported, never repaired: only systemd may start it.
The error carries the command, because an error that says "unavailable" and
leaves the reader to guess the remedy is how a screen ends up with a dead button.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import socket
import sys
from typing import Any, Dict, List, Optional

from .protocol import Request, Response

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 2.0
#: `start` waits for systemd to report the transient scope active, and `stop`
#: escalates to SIGKILL after its grace period — both are seconds, not
#: milliseconds, so a short read timeout would report a failure for work that is
#: proceeding normally.
READ_TIMEOUT = 30.0

#: The service manager's name for the owner, shared with the units the installer
#: places. One spelling, so the command the screen offers and the unit on disk
#: cannot drift apart.
SYSTEMD_UNIT = "set-agent-owner.service"
LAUNCHD_LABEL = "com.set-core.agent-owner"


def start_command() -> str:
    """The command that starts the owner ON THIS MACHINE.

    A function rather than a constant, and resolved at call time rather than at
    import, because the thing it names is a property of the running machine. A
    command borrowed from another platform's service manager is worse than no
    command at all: it reads as an instruction, and following it produces an
    error about an unknown tool that says nothing about the owner's actual state.
    """
    if sys.platform == "darwin":
        return f"launchctl kickstart -k gui/{os.getuid()}/{LAUNCHD_LABEL}"
    return f"systemctl --user start {SYSTEMD_UNIT}"


class OwnerClientError(RuntimeError):
    """The owner answered, and the answer was a refusal."""

    #: The owner's classification of the refusal, when it gave one. `None` means
    #: unclassified — from an older owner, or a refusal with no kind — and a
    #: caller must not read that as a kind of its own.
    kind: Optional[str] = None

    def __init__(self, message: str, kind: Optional[str] = None) -> None:
        super().__init__(message)
        self.kind = kind



class OwnerUnavailable(OwnerClientError):
    """The owner could not be reached at all."""


class OwnerClient:
    def __init__(self, socket_path: Optional[str] = None) -> None:
        from .ownerd import default_socket_path
        self.socket_path = socket_path or default_socket_path()

    # -- transport -------------------------------------------------------- #

    def _connect(self) -> socket.socket:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(CONNECT_TIMEOUT)
        try:
            sock.connect(self.socket_path)
        except OSError as exc:
            sock.close()
            raise OwnerUnavailable(
                f"the agent owner is not running ({self.socket_path}: {exc.strerror}). "
                f"Start it with `{start_command()}` — the dashboard must not start it "
                "itself, or it would die with the dashboard."
            ) from exc
        sock.settimeout(READ_TIMEOUT)
        return sock

    def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        req = Request(method=method, params=params or {})
        sock = self._connect()
        try:
            sock.sendall((req.to_json() + "\n").encode("utf-8"))
            line = self._read_line(sock)
        except OSError as exc:
            raise OwnerUnavailable(f"the agent owner stopped answering: {exc}") from exc
        finally:
            sock.close()

        try:
            resp = Response.from_json(line)
        except (ValueError, json.JSONDecodeError) as exc:
            raise OwnerClientError(f"unparseable answer from the agent owner: {exc}") from exc
        if not resp.ok:
            raise OwnerClientError(
                resp.error or "the agent owner refused without saying why",
                resp.error_kind,
            )
        return resp.result

    @staticmethod
    def _read_line(sock: socket.socket) -> str:
        buf = bytearray()
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                raise OwnerUnavailable("the agent owner closed the connection before answering")
            buf.extend(chunk)
            if b"\n" in buf:
                line, _ = buf.split(b"\n", 1)
                return line.decode("utf-8", errors="replace")

    # -- the owner's surface, one method each ----------------------------- #

    def health(self) -> Dict[str, Any]:
        return self.request("health")

    def list_agents(self) -> List[Dict[str, Any]]:
        return self.request("list")

    def orphans(self) -> List[Dict[str, Any]]:
        return self.request("orphans")

    def start(
        self,
        *,
        label: str,
        cwd: str,
        argv: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        rows: int = 40,
        cols: int = 120,
        requested_by: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        project: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ask the owner to start an agent.

        `provider`, `model` and `project` are NAMES, and that is the whole design:
        the owner resolves them on its own side, so the credential never crosses
        this socket, is never held by the caller, and cannot be logged by anything
        between the two. A caller that wanted to spend against another account
        would have to name a provider the configuration declares — which is a
        decision the configuration already made, not one this call can invent.
        """
        params: Dict[str, Any] = {"label": label, "cwd": cwd, "rows": rows, "cols": cols}
        if requested_by:
            params["requested_by"] = requested_by
        if argv:
            params["argv"] = list(argv)
        if env:
            params["env"] = dict(env)
        if provider:
            params["provider"] = provider
        if model:
            params["model"] = model
        if project:
            params["project"] = project
        return self.request("start", params)

    def stop(self, label: str) -> Dict[str, Any]:
        return self.request("stop", {"label": label})

    def rename(self, label: str, new_label: str) -> Dict[str, Any]:
        """Give a held agent another name. The agent keeps running."""
        return self.request("rename", {"label": label, "new_label": new_label})

    def recover(
        self,
        *,
        unit: str,
        session_id: str,
        cwd: str,
        label: Optional[str] = None,
        resume_argv: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"unit": unit, "session_id": session_id, "cwd": cwd}
        if label:
            params["label"] = label
        if resume_argv:
            params["resume_argv"] = list(resume_argv)
        return self.request("recover", params)

    def write(self, label: str, data: bytes) -> int:
        result = self.request(
            "write", {"label": label, "data_b64": base64.b64encode(data).decode("ascii")}
        )
        return int(result["written"])

    def resize(self, label: str, rows: int, cols: int) -> None:
        self.request("resize", {"label": label, "rows": rows, "cols": cols})

    def tail(self, label: str, max_bytes: Optional[int] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"label": label}
        if max_bytes is not None:
            params["max_bytes"] = max_bytes
        result = self.request("tail", params)
        result["data"] = base64.b64decode(result["data_b64"])
        return result


def owner_available(socket_path: Optional[str] = None) -> bool:
    """Whether the owner is reachable right now.

    Asks by connecting, not by checking that the socket file exists: a crashed
    owner leaves the file behind, so file-presence answers a different question
    than the one the surface needs.
    """
    try:
        OwnerClient(socket_path).health()
    except OwnerClientError:
        return False
    return True


# --------------------------------------------------------------------------- #
# the streaming half — one attached terminal (tasks 5.3, 6.4)
# --------------------------------------------------------------------------- #

class OwnerStream:
    """An attached terminal: one asyncio connection to the owner, full-duplex.

    Separate from `OwnerClient` because it is a different shape, not a different
    transport: the sync client is request/response, this one carries a
    conversation. Sharing a class would mean a connection that is sometimes
    stateful and callers could not tell which by looking.

    **One socket carries both directions.** Splitting them across two connections
    would let a keystroke arrive before the output that prompted it, and a
    terminal in which cause and effect can reorder is not a terminal.

    **One reader owns the socket, and this is not a style choice — it is the two
    bugs an end-to-end probe found on 2026-08-19, both invisible to unit tests:**

    - *A request that reads its own answer eats the frames it passes over.* The
      obvious client sends `attach` and reads lines until one carries an `id`,
      skipping frames on the way. The owner sends the replayed screen BEFORE the
      response, so that skip silently discarded it: 1752 bytes sent, 44 arrived,
      and the first screen was wrong rather than absent.
    - *Two coroutines cannot read one stream.* With output pumping and a
      keystroke's request both reading, the connection died on the first
      keystroke — a terminal that shows output until you touch it.

    So exactly one loop reads: responses resolve futures by id, frames go to a
    queue. Nothing else may call `readline`.

    Nothing is persisted: frames pass through to the caller and are not written
    down, not cached, not logged. Diagnostics name the stream and the failure
    kind only.
    """

    #: Frames buffered for a consumer that is behind. The owner drops a viewer
    #: whose socket backs up; this bounds the same risk one hop later, and drops
    #: the OLDEST rather than the newest — on a terminal the recent screen is
    #: what the reader needs, and a gap that is admitted beats a stale tail.
    MAX_QUEUED_FRAMES = 2048

    #: The longest single wire line this client will accept.
    #:
    #: asyncio's default is 64 KiB, and a line longer than that does not read as
    #: a short read or a closed socket — `readline` raises `LimitOverrunError`,
    #: the read loop dies, and every waiter is told the OWNER closed the
    #: connection. The owner had done nothing of the sort.
    #:
    #: The owner now splits its frames (`OwnerDaemon.MAX_FRAME_BYTES`), so this
    #: is the second wall rather than the first: it keeps a client from being
    #: killed by an owner that is older, differently configured, or fixed later.
    #: Generous on purpose — the cost of a high limit is a buffer, the cost of a
    #: low one is a terminal that dies exactly when it has something to show.
    READ_LIMIT = 8 * 1024 * 1024

    def __init__(self, label: str, socket_path: Optional[str] = None) -> None:
        from .ownerd import default_socket_path
        self.label = label
        self.socket_path = socket_path or default_socket_path()
        self._reader = None
        self._writer = None
        self._pending: Dict[str, "asyncio.Future"] = {}
        self._frames: Optional["asyncio.Queue"] = None
        self._pump = None
        self._dropped_frames = 0

    async def open(self) -> Dict[str, Any]:
        """Attach, and return the owner's acknowledgement.

        Raises rather than degrading: a terminal that silently attaches to
        nothing is a black rectangle the reader has no way to interpret.
        """
        import asyncio
        try:
            self._reader, self._writer = await asyncio.open_unix_connection(
                self.socket_path, limit=self.READ_LIMIT
            )
        except OSError as exc:
            raise OwnerUnavailable(
                f"the agent owner is not running ({self.socket_path}: {exc}). "
                f"Start it with `{start_command()}`."
            ) from exc
        self._frames = asyncio.Queue()
        # Started BEFORE the attach request, so the replayed screen — which the
        # owner writes before the response — is queued rather than skipped.
        self._pump = asyncio.create_task(self._read_loop())
        return await self._request("attach", {"label": self.label})

    async def _read_loop(self) -> None:
        import asyncio, json as _json
        assert self._reader is not None and self._frames is not None
        failure = "the agent owner closed the terminal connection"
        try:
            while True:
                line = await self._reader.readline()
                if not line:
                    break
                try:
                    payload = _json.loads(line)
                except ValueError:
                    logger.warning("fleet stream: unparseable line on %s", self.label)
                    continue
                request_id = payload.get("id")
                if request_id is not None:
                    future = self._pending.pop(str(request_id), None)
                    if future is not None and not future.done():
                        if payload.get("error") is not None:
                            future.set_exception(OwnerClientError(payload["error"]))
                        else:
                            future.set_result(payload.get("result"))
                    continue
                data = payload.get("data_b64")
                if data is None:
                    continue
                frame = (base64.b64decode(data), bool(payload.get("replay")))
                if self._frames.qsize() >= self.MAX_QUEUED_FRAMES:
                    self._frames.get_nowait()
                    self._dropped_frames += 1
                    if self._dropped_frames == 1:
                        logger.warning(
                            "fleet stream: %s is behind; dropping the oldest frames", self.label
                        )
                self._frames.put_nowait(frame)
        except (ConnectionResetError, asyncio.IncompleteReadError, OSError) as exc:
            logger.debug("fleet stream: %s read loop ended: %s", self.label, type(exc).__name__)
        except (ValueError, asyncio.LimitOverrunError) as exc:
            # A frame the reader refuses is OUR limit refusing it, not the owner
            # hanging up — and the difference is the whole diagnosis. Reported
            # loudly and by name, because the previous wording sent a reader
            # looking at the owner's logs, where nothing was wrong.
            failure = f"the terminal stream broke while reading a frame ({type(exc).__name__})"
            logger.error("fleet stream: %s: %s", self.label, failure)
        finally:
            # Everyone waiting is told, rather than left on a future that will
            # never resolve — a hung terminal looks exactly like a busy one.
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(OwnerUnavailable(failure))
            self._pending.clear()
            if self._frames is not None:
                self._frames.put_nowait(None)

    async def _request(self, method: str, params: Dict[str, Any]) -> Any:
        import asyncio
        assert self._writer is not None
        request = Request(method=method, params=params)
        future = asyncio.get_running_loop().create_future()
        self._pending[request.id] = future
        try:
            self._writer.write((request.to_json() + "\n").encode("utf-8"))
            await self._writer.drain()
        except OSError as exc:
            self._pending.pop(request.id, None)
            raise OwnerUnavailable(f"the agent owner stopped answering: {exc}") from exc
        return await future

    async def frames(self):
        """Yield terminal frames as `(data: bytes, replay: bool)` until the stream ends.

        Ends when the owner closes the connection — which is also what a stopped
        agent looks like from here. The two are deliberately the same signal: for
        a viewer, "the terminal ended" and "the connection ended" call for the
        same response, and inventing a difference would suggest one it cannot act
        on.
        """
        assert self._frames is not None
        while True:
            item = await self._frames.get()
            if item is None:
                return
            yield item

    async def write(self, data: bytes) -> int:
        result = await self._request(
            "write", {"label": self.label, "data_b64": base64.b64encode(data).decode("ascii")}
        )
        return int(result["written"])

    async def resize(self, rows: int, cols: int) -> None:
        await self._request("resize", {"label": self.label, "rows": rows, "cols": cols})

    async def close(self) -> None:
        """Detach. Never stops the agent — that is a different act (task 5.4)."""
        if self._writer is None:
            return
        try:
            await self._request("detach", {"label": self.label})
        except (OwnerClientError, OwnerUnavailable, OSError) as exc:
            logger.debug("fleet stream: detach on %s: %s", self.label, exc)
        if self._pump is not None:
            self._pump.cancel()
        try:
            self._writer.close()
        except OSError:
            pass
        self._reader = self._writer = self._pump = None
