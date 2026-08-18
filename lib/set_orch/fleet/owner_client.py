"""Client for the agent owner — how the dashboard reaches it (task 5.8).

Synchronous, because the caller is a FastAPI route and the requests are short.

**This client deliberately does NOT auto-start the owner, and that is the one
place it departs from `set_memoryd.client`, which does.** The departure is the
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
import socket
from typing import Any, Dict, List, Optional

from .protocol import Request, Response

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 2.0
#: `start` waits for systemd to report the transient scope active, and `stop`
#: escalates to SIGKILL after its grace period — both are seconds, not
#: milliseconds, so a short read timeout would report a failure for work that is
#: proceeding normally.
READ_TIMEOUT = 30.0

START_COMMAND = "systemctl --user start set-agent-owner.service"


class OwnerClientError(RuntimeError):
    """The owner answered, and the answer was a refusal."""


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
                f"Start it with `{START_COMMAND}` — the dashboard must not start it "
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
            raise OwnerClientError(resp.error or "the agent owner refused without saying why")
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
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"label": label, "cwd": cwd, "rows": rows, "cols": cols}
        if argv:
            params["argv"] = list(argv)
        if env:
            params["env"] = dict(env)
        return self.request("start", params)

    def stop(self, label: str) -> Dict[str, Any]:
        return self.request("stop", {"label": label})

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
