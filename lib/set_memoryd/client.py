"""Synchronous client for set-memoryd Unix socket daemon.

Connects to the daemon, sends JSON-lines requests, reads responses.
Auto-starts daemon if not running (max 1 retry).
"""

from __future__ import annotations

import json
import socket
import time
from typing import Any

from .protocol import Request, Response
from .lifecycle import (
    socket_path_for,
    storage_path_for,
    resolve_project,
    ensure_running,
    is_running,
    STARTUP_TIMEOUT,
)

# Connection timeout
CONNECT_TIMEOUT = 2.0
# Read timeout (some operations like remember can be slow)
READ_TIMEOUT = 15.0


class DaemonError(Exception):
    """Raised when daemon communication fails."""
    pass


class DaemonUnavailable(DaemonError):
    """Raised when daemon cannot be reached or started."""
    pass


class MemoryClient:
    """Sync client for per-project memory daemon."""

    def __init__(self, project: str | None = None, project_dir: str | None = None):
        """Initialize client for a project.

        Args:
            project: Project name (e.g., "set-core"). Auto-detected if None.
            project_dir: Working directory for project resolution.
        """
        if project is None:
            import os
            if project_dir:
                old_cwd = os.getcwd()
                try:
                    os.chdir(project_dir)
                    project = resolve_project()
                finally:
                    os.chdir(old_cwd)
            else:
                project = resolve_project()

        self.project = project
        self.socket_path = socket_path_for(project)
        self._sock: socket.socket | None = None

    @classmethod
    def for_project(cls, project_dir: str | None = None) -> MemoryClient:
        """Create client with auto-detected project. Auto-starts daemon."""
        client = cls(project_dir=project_dir)
        client._ensure_daemon()
        return client

    def _ensure_daemon(self) -> None:
        """Ensure daemon is running, start if needed."""
        if not ensure_running(self.project, storage_path_for(self.project)):
            raise DaemonUnavailable(f"failed to start daemon for {self.project}")

    def _connect(self) -> socket.socket:
        """Connect to daemon socket."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(CONNECT_TIMEOUT)
        try:
            sock.connect(self.socket_path)
        except (ConnectionRefusedError, FileNotFoundError, OSError) as e:
            sock.close()
            raise DaemonUnavailable(f"cannot connect to {self.socket_path}: {e}")
        sock.settimeout(READ_TIMEOUT)
        return sock

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a request and return the result.

        Raises DaemonError on communication failure.
        Returns the result value from the response.
        """
        req = Request(method=method, params=params or {})
        line = req.to_json() + "\n"

        # Try with auto-start on first failure
        for attempt in range(2):
            try:
                sock = self._connect()
                try:
                    sock.sendall(line.encode())
                    resp_line = self._read_line(sock)
                finally:
                    sock.close()

                resp = Response.from_json(resp_line)
                if not resp.ok:
                    raise DaemonError(resp.error)
                return resp.result

            except DaemonUnavailable:
                if attempt == 0:
                    # Auto-start and retry
                    self._ensure_daemon()
                    # Wait for socket
                    deadline = time.monotonic() + STARTUP_TIMEOUT
                    while time.monotonic() < deadline:
                        if is_running(self.project):
                            break
                        time.sleep(0.05)
                    continue
                raise
            except (OSError, json.JSONDecodeError) as e:
                if attempt == 0:
                    self._ensure_daemon()
                    continue
                raise DaemonError(f"communication error: {e}")

        raise DaemonUnavailable("failed after retry")

    def _read_line(self, sock: socket.socket) -> str:
        """Read a single newline-terminated line from socket."""
        buf = bytearray()
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                if buf:
                    return buf.decode("utf-8", errors="replace").strip()
                raise DaemonError("connection closed before response")
            buf.extend(chunk)
            if b"\n" in buf:
                # Return first complete line
                line, _ = buf.split(b"\n", 1)
                return line.decode("utf-8", errors="replace")

    # ─── Convenience methods (1:1 with MemorySystem) ─────────

    def recall(
        self,
        query: str,
        limit: int = 5,
        mode: str = "hybrid",
        tags: str = "",
    ) -> list:
        return self.request("recall", {
            "query": query, "limit": limit, "mode": mode, "tags": tags,
        })

    def remember(
        self,
        content: str,
        memory_type: str = "Learning",
        tags: str = "",
        metadata: dict | None = None,
    ) -> Any:
        params: dict[str, Any] = {"content": content, "type": memory_type, "tags": tags}
        if metadata:
            params["metadata"] = metadata
        return self.request("remember", params)

    def proactive_context(self, context: str, limit: int = 5) -> list:
        return self.request("proactive_context", {"context": context, "limit": limit})

    def list_memories(self, memory_type: str = "", limit: int = 20) -> list:
        return self.request("list", {"type": memory_type, "limit": limit})

    def get(self, memory_id: str) -> Any:
        return self.request("get", {"id": memory_id})

    def forget(self, memory_id: str) -> Any:
        return self.request("forget", {"id": memory_id})

    def forget_by_tags(self, tags: str) -> Any:
        return self.request("forget_by_tags", {"tags": tags})

    def context_summary(self, topic: str = "") -> Any:
        return self.request("context_summary", {"topic": topic})

    def brain(self) -> Any:
        return self.request("brain")

    def stats(self) -> Any:
        return self.request("stats")

    def index_health(self) -> Any:
        return self.request("index_health")

    def verify_index(self) -> Any:
        return self.request("verify_index")

    def recall_by_date(self, since: str = "", until: str = "", limit: int = 20) -> Any:
        return self.request("recall_by_date", {"since": since, "until": until, "limit": limit})

    def flush(self) -> Any:
        return self.request("flush")

    def consolidation_report(self, since: str = "") -> Any:
        return self.request("consolidation_report", {"since": since})

    def graph_stats(self) -> Any:
        return self.request("graph_stats")

    def health(self) -> dict:
        return self.request("health")

    def shutdown(self) -> Any:
        return self.request("shutdown")
