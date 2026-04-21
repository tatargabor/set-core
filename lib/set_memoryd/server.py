"""asyncio Unix socket server wrapping shodh-memory MemorySystem.

Handles JSON-lines requests, idle timeout (30 min), graceful shutdown via SIGTERM.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

from .protocol import (
    SUPPORTED_METHODS,
    Request,
    Response,
    make_error,
    make_result,
)

logger = logging.getLogger("set-memoryd")

# Default idle timeout: 30 minutes
DEFAULT_IDLE_TIMEOUT = 30 * 60


class MemoryDaemon:
    """Per-project memory daemon backed by shodh MemorySystem."""

    def __init__(
        self,
        project: str,
        storage_path: str,
        socket_path: str,
        pid_path: str,
        idle_timeout: int = DEFAULT_IDLE_TIMEOUT,
    ):
        self.project = project
        self.storage_path = storage_path
        self.socket_path = socket_path
        self.pid_path = pid_path
        self.idle_timeout = idle_timeout

        self._memory = None  # lazy-loaded MemorySystem
        self._server: asyncio.Server | None = None
        self._last_activity = time.monotonic()
        self._shutdown_event = asyncio.Event()
        self._request_count = 0
        self._active_connections = 0

    def _init_memory(self) -> None:
        """Initialize shodh MemorySystem (one-time, lazy)."""
        if self._memory is not None:
            return

        try:
            from shodh.memory import Memory
        except ImportError:
            from shodh_memory import Memory

        self._memory = Memory(storage_path=self.storage_path)
        logger.info("MemorySystem initialized for project=%s storage=%s", self.project, self.storage_path)

    def _touch_activity(self) -> None:
        self._last_activity = time.monotonic()

    async def handle_request(self, request: Request) -> Response:
        """Dispatch a request to the appropriate MemorySystem method."""
        self._touch_activity()
        self._request_count += 1

        method = request.method
        params = request.params

        if method not in SUPPORTED_METHODS:
            return make_error(request.id, f"unknown method: {method}")

        # Daemon lifecycle methods
        if method == "health":
            return make_result(request.id, {
                "status": "ok",
                "project": self.project,
                "uptime_s": int(time.monotonic() - self._start_time),
                "requests": self._request_count,
                "connections": self._active_connections,
            })

        if method == "shutdown":
            self._shutdown_event.set()
            return make_result(request.id, {"status": "shutting_down"})

        # All other methods need MemorySystem
        try:
            self._init_memory()
        except Exception as e:
            return make_error(request.id, f"MemorySystem init failed: {e}")

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._dispatch, method, params
            )
            return make_result(request.id, result)
        except Exception as e:
            logger.error("method=%s error: %s", method, e)
            return make_error(request.id, str(e))

    def _dispatch(self, method: str, params: dict[str, Any]) -> Any:
        """Synchronous dispatch to MemorySystem (runs in executor)."""
        m = self._memory

        if method == "recall":
            kwargs = {
                "query": params.get("query", ""),
                "limit": params.get("limit", 5),
                "mode": params.get("mode", "hybrid"),
            }
            tags = params.get("tags")
            if tags:
                if isinstance(tags, str):
                    kwargs["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
                else:
                    kwargs["tags"] = tags
            results = m.recall(**kwargs)
            return _serialize(results)

        if method == "remember":
            kwargs = {
                "content": params.get("content", ""),
                "memory_type": params.get("type", "Learning"),
            }
            tags = params.get("tags")
            if tags:
                # shodh expects tags as a list, CLI passes comma-separated string
                if isinstance(tags, str):
                    kwargs["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
                else:
                    kwargs["tags"] = tags
            metadata = params.get("metadata")
            if metadata:
                kwargs["metadata"] = metadata
            return m.remember(**kwargs)

        if method == "proactive_context":
            results = m.proactive_context(
                context=params.get("context", ""),
                max_results=params.get("limit", 5),
            )
            return _serialize(results)

        if method == "list":
            kwargs = {"limit": params.get("limit", 20)}
            mem_type = params.get("type")
            if mem_type:
                kwargs["memory_type"] = mem_type
            results = m.list_memories(**kwargs)
            return _serialize(results)

        if method == "get":
            result = m.get_memory(params.get("id", ""))
            return _serialize(result)

        if method == "forget":
            return m.forget(params.get("id", ""))

        if method == "forget_by_tags":
            tags = params.get("tags", "")
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            return m.forget_by_tags(tags)

        if method == "forget_all":
            return m.forget_all()

        if method == "forget_by_age":
            return m.forget_by_age(int(params.get("days", 0)))

        if method == "forget_by_pattern":
            return m.forget_by_pattern(params.get("pattern", ""))

        if method == "forget_by_date":
            since = params.get("since") or "2000-01-01T00:00:00Z"
            until = params.get("until") or ""
            if not until:
                from datetime import datetime, timezone
                until = datetime.now(timezone.utc).isoformat()
            if hasattr(m, "forget_by_date"):
                return m.forget_by_date(since, until)
            raise RuntimeError("forget_by_date not available in this shodh-memory version")

        if method == "context_summary":
            kwargs = {}
            topic = params.get("topic")
            if topic:
                kwargs["topic"] = topic
            return m.context_summary(**kwargs)

        if method == "brain":
            return _serialize(m.brain_state())

        if method == "stats":
            return _serialize(m.get_stats())

        if method == "index_health":
            return _serialize(m.index_health())

        if method == "verify_index":
            return _serialize(m.verify_index())

        if method == "repair_index":
            if hasattr(m, "repair_index"):
                return _serialize(m.repair_index())
            raise RuntimeError("repair_index not available — upgrade shodh-memory to >=0.1.81")

        if method == "recall_by_date":
            kwargs = {"limit": params.get("limit", 20)}
            since = params.get("since")
            if since:
                kwargs["since"] = since
            until = params.get("until")
            if until:
                kwargs["until"] = until
            results = m.recall_by_date(**kwargs)
            return _serialize(results)

        if method == "flush":
            m.flush()
            return {"status": "flushed"}

        if method == "consolidation_report":
            kwargs = {}
            since = params.get("since")
            if since:
                kwargs["since"] = since
            return _serialize(m.consolidation_report(**kwargs))

        if method == "graph_stats":
            return _serialize(m.graph_stats())

        return make_error("", f"unimplemented method: {method}")

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a single client connection (JSON-lines protocol)."""
        self._active_connections += 1
        peer = writer.get_extra_info("peername") or "unix"
        logger.debug("connection opened: %s", peer)

        try:
            while True:
                line = await reader.readline()
                if not line:
                    break  # EOF

                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                try:
                    request = Request.from_json(line_str)
                except (json.JSONDecodeError, KeyError) as e:
                    resp = make_error("", f"invalid request: {e}")
                    writer.write((resp.to_json() + "\n").encode())
                    await writer.drain()
                    continue

                response = await self.handle_request(request)
                writer.write((response.to_json() + "\n").encode())
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            logger.error("connection error: %s", e)
        finally:
            self._active_connections -= 1
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _idle_watchdog(self) -> None:
        """Shutdown after idle_timeout seconds of inactivity."""
        while not self._shutdown_event.is_set():
            await asyncio.sleep(30)  # check every 30s
            elapsed = time.monotonic() - self._last_activity
            if elapsed >= self.idle_timeout:
                logger.info("idle timeout (%ds), shutting down", self.idle_timeout)
                self._shutdown_event.set()
                return

    async def run(self) -> None:
        """Start the daemon and run until shutdown."""
        self._start_time = time.monotonic()

        # Clean up stale socket
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        # Write PID file
        os.makedirs(os.path.dirname(self.pid_path), exist_ok=True)
        with open(self.pid_path, "w") as f:
            f.write(str(os.getpid()))

        # Install signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown_event.set)

        # Start server
        self._server = await asyncio.start_unix_server(
            self._handle_connection, path=self.socket_path
        )
        # Make socket accessible
        os.chmod(self.socket_path, 0o600)

        logger.info(
            "set-memoryd started: project=%s socket=%s pid=%d",
            self.project, self.socket_path, os.getpid(),
        )

        # Run until shutdown
        watchdog = asyncio.create_task(self._idle_watchdog())
        try:
            await self._shutdown_event.wait()
        finally:
            watchdog.cancel()
            await self._graceful_shutdown()

    async def _graceful_shutdown(self) -> None:
        """Clean shutdown: close server, flush memory, remove socket+PID."""
        logger.info("shutting down...")

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # Flush MemorySystem
        if self._memory is not None:
            try:
                self._memory.flush()
            except Exception as e:
                logger.error("flush error: %s", e)

        # Cleanup files
        for path in (self.socket_path, self.pid_path):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass

        logger.info("shutdown complete (served %d requests)", self._request_count)


def _serialize(obj: Any) -> Any:
    """Convert shodh result objects to JSON-serializable dicts/lists."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(item) for item in obj]
    # shodh Memory objects have __dict__ or to_dict()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return {k: _serialize(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)
