"""JSON-lines protocol for wt-memoryd Unix socket communication.

Request:  {"id": "abc", "method": "recall", "params": {"query": "...", "limit": 3}}
Response: {"id": "abc", "result": [...]}
Error:    {"id": "abc", "error": "message"}

Each message is a single JSON line terminated by newline.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any


# All supported daemon methods (1:1 map to MemorySystem API)
SUPPORTED_METHODS = frozenset({
    # Core
    "recall", "remember", "proactive_context", "list", "get", "forget", "forget_by_tags",
    # Introspection
    "context_summary", "brain", "stats", "index_health", "verify_index",
    # Time-based
    "recall_by_date",
    # Maintenance
    "flush", "consolidation_report", "graph_stats",
    # Daemon lifecycle
    "health", "shutdown",
})


@dataclass
class Request:
    """A daemon request."""

    method: str
    params: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_json(self) -> str:
        return json.dumps({"id": self.id, "method": self.method, "params": self.params})

    @classmethod
    def from_json(cls, line: str) -> Request:
        data = json.loads(line)
        return cls(
            id=data.get("id", ""),
            method=data.get("method", ""),
            params=data.get("params", {}),
        )


@dataclass
class Response:
    """A daemon response."""

    id: str
    result: Any = None
    error: str | None = None

    def to_json(self) -> str:
        d: dict[str, Any] = {"id": self.id}
        if self.error is not None:
            d["error"] = self.error
        else:
            d["result"] = self.result
        return json.dumps(d)

    @classmethod
    def from_json(cls, line: str) -> Response:
        data = json.loads(line)
        return cls(
            id=data.get("id", ""),
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
