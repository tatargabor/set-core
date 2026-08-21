"""JSON-lines protocol between the dashboard and the agent owner.

    Request:  {"id": "abc", "method": "start", "params": {...}}
    Response: {"id": "abc", "result": {...}}
    Error:    {"id": "abc", "error": "message"}

One newline-terminated JSON object per message, over an `AF_UNIX` stream.

**This is deliberately the same shape as `set_memoryd.protocol`** — task 5.8 says
extend the daemon shape this repository already has rather than invent a second
one. It is *copied* rather than imported, and the reason is measured rather than
stylistic: `set_memoryd` is not a packaged module (`pyproject.toml`'s
`packages.find` include list names `set_tools*`, `set_orch*`, `set_workcycle*`
and `gui*` only, and `import set_memoryd` fails in the installed environment).
Importing it would make the owner service — which systemd starts — depend on a
module that only resolves when `PYTHONPATH` happens to carry `lib/`.

A second copy drifts, so the bound on the drift is stated here: the two daemons'
method sets are disjoint and neither imports the other's, and what is shared is
forty lines of envelope. If a third daemon appears, this is the point at which
the envelope should become a packaged module instead of a third copy.

**Bytes travel base64-encoded, never as text.** Keystrokes and terminal output
are arbitrary bytes — a partial UTF-8 sequence split across two reads is normal
on a pty — and JSON cannot hold them. Encoding them as a string would force a
lossy decode at the boundary, silently, in the direction that looks like data.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

#: Everything the owner will answer. The list is short on purpose: this is the
#: whole surface of a service whose uptime is every agent's uptime, and each
#: entry is a passthrough to `AgentOwner` rather than a behaviour of its own.
SUPPORTED_METHODS = frozenset({
    # lifecycle
    "start", "stop", "recover", "rename",
    # what this owner can say about the world
    "health", "list", "orphans",
    # the relay
    "write", "resize", "tail",
    # the relay, as a stream: `attach` turns the connection full-duplex and the
    # owner pushes frames until `detach` or the client goes away.
    "attach", "detach",
})

#: A pushed terminal frame, distinguishable from a response by carrying no `id`.
#: The reader must branch on this rather than on presence-of-`result`, because a
#: response whose result happens to be null would otherwise read as a frame.
FRAME_KEY = "stream"


def make_frame(label: str, data_b64: str, *, replay: bool = False) -> str:
    """One terminal frame, ready to write to the wire.

    `replay` marks the buffered tail sent at attach time — the screen as it was
    before this viewer arrived. A viewer that cannot tell replay from live output
    has no way to know whether what it is looking at is happening now.
    """
    return json.dumps({FRAME_KEY: label, "data_b64": data_b64, "replay": replay})


@dataclass
class Request:
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_json(self) -> str:
        return json.dumps({"id": self.id, "method": self.method, "params": self.params})

    @classmethod
    def from_json(cls, line: str) -> "Request":
        data = json.loads(line)
        if not isinstance(data, dict):
            raise ValueError("a request must be a JSON object")
        return cls(
            id=str(data.get("id", "")),
            method=str(data.get("method", "")),
            params=data.get("params") or {},
        )


@dataclass
class Response:
    id: str
    result: Any = None
    error: Optional[str] = None

    def to_json(self) -> str:
        payload: Dict[str, Any] = {"id": self.id}
        if self.error is not None:
            payload["error"] = self.error
        else:
            payload["result"] = self.result
        return json.dumps(payload)

    @classmethod
    def from_json(cls, line: str) -> "Response":
        data = json.loads(line)
        return cls(
            id=str(data.get("id", "")),
            result=data.get("result"),
            error=data.get("error"),
        )

    @property
    def ok(self) -> bool:
        return self.error is None


def make_error(request_id: str, message: str) -> Response:
    return Response(id=request_id, error=message)


def make_result(request_id: str, result: Any) -> Response:
    return Response(id=request_id, result=result)
