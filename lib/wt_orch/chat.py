"""WebSocket chat endpoint for interactive agent communication.

Spawns a Claude Code subprocess per project, bridges stdin/stdout
to WebSocket messages for real-time interactive chat from the web UI.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .api import _resolve_project

logger = logging.getLogger("wt-web.chat")

router = APIRouter()

# ─── Agent subprocess manager ─────────────────────────────────────────


class AgentProcess:
    """Manages a single Claude Code subprocess for a project."""

    def __init__(self, project_name: str, project_path: Path):
        self.project_name = project_name
        self.project_path = project_path
        self.process: asyncio.subprocess.Process | None = None
        self.session_id: str | None = None
        self._read_task: asyncio.Task | None = None
        self._clients: set[WebSocket] = set()

    async def start(self) -> None:
        """Spawn the claude subprocess."""
        if self.process and self.process.returncode is None:
            return  # Already running

        cmd = [
            "claude",
            "-p",
            "--output-format", "stream-json",
            "--input-format", "stream-json",
            "--verbose",
            "--permission-mode", "auto",
        ]

        logger.info(f"Spawning agent for {self.project_name}: {' '.join(cmd)}")

        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.project_path),
            # Process group for clean shutdown
            preexec_fn=os.setsid,
        )

        # Start reading stdout and stderr
        self._read_task = asyncio.create_task(self._read_stdout())
        asyncio.create_task(self._read_stderr())

    async def _read_stdout(self) -> None:
        """Read agent stdout and forward events to connected clients."""
        if not self.process or not self.process.stdout:
            return

        try:
            async for line in self.process.stdout:
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                try:
                    event = json.loads(line_str)
                except json.JSONDecodeError:
                    logger.warning(f"Non-JSON stdout: {line_str[:200]}")
                    continue

                # Extract session ID from init event
                if event.get("type") == "system" and event.get("subtype") == "init":
                    self.session_id = event.get("session_id")
                    # Send init event to clients
                    await self._broadcast({"type": "status", "status": "ready"})
                    continue

                # Map Claude stream-json events to our chat protocol
                mapped = self._map_event(event)
                if mapped:
                    await self._broadcast(mapped)

        except Exception as e:
            logger.error(f"Error reading agent stdout: {e}")
        finally:
            # Agent process exited
            await self._broadcast({
                "type": "error",
                "message": "Agent session ended",
            })

    def _map_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """Map a Claude stream-json event to our chat WebSocket protocol."""
        evt_type = event.get("type", "")

        if evt_type == "assistant":
            msg = event.get("message", {})
            content_blocks = msg.get("content", [])
            for block in content_blocks:
                if block.get("type") == "text":
                    return {
                        "type": "assistant_text",
                        "content": block.get("text", ""),
                    }
                elif block.get("type") == "tool_use":
                    return {
                        "type": "tool_use",
                        "tool": block.get("name", "unknown"),
                        "tool_use_id": block.get("id", ""),
                        "input": _summarize_input(block.get("input", {})),
                    }
            # If no content blocks we recognize, still notify about thinking
            if msg.get("stop_reason") is None:
                return {"type": "status", "status": "thinking"}
            return None

        elif evt_type == "result":
            return {
                "type": "assistant_done",
                "result": event.get("result", ""),
                "cost_usd": event.get("total_cost_usd"),
                "duration_ms": event.get("duration_ms"),
                "num_turns": event.get("num_turns"),
            }

        elif evt_type == "tool_result":
            return {
                "type": "tool_result",
                "tool_use_id": event.get("tool_use_id", ""),
                "output": _summarize_output(event.get("output", "")),
            }

        # Unknown event — forward type for debugging
        return None

    async def _read_stderr(self) -> None:
        """Log agent stderr output."""
        if not self.process or not self.process.stderr:
            return
        try:
            async for line in self.process.stderr:
                line_str = line.decode("utf-8", errors="replace").strip()
                if line_str:
                    logger.debug(f"Agent stderr [{self.project_name}]: {line_str}")
        except Exception:
            pass

    async def send_message(self, content: str) -> None:
        """Send a user message to the agent's stdin."""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Agent process not running")
        if self.process.returncode is not None:
            raise RuntimeError("Agent process has exited")

        # stream-json input format: send as JSON with type "user"
        msg = json.dumps({"type": "user", "content": content}) + "\n"
        self.process.stdin.write(msg.encode("utf-8"))
        await self.process.stdin.drain()
        await self._broadcast({"type": "status", "status": "thinking"})

    async def stop(self) -> None:
        """Stop the agent subprocess."""
        if not self.process or self.process.returncode is not None:
            return

        pid = self.process.pid
        logger.info(f"Stopping agent for {self.project_name} (PID {pid})")

        try:
            # Send SIGTERM to process group
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            return

        # Wait up to 5 seconds
        try:
            await asyncio.wait_for(self.process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning(f"Agent {self.project_name} didn't stop, sending SIGKILL")
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

        if self._read_task:
            self._read_task.cancel()

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.returncode is None

    def add_client(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def remove_client(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    @property
    def has_clients(self) -> bool:
        return len(self._clients) > 0

    async def _broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to all connected chat clients."""
        payload = json.dumps(message)
        dead: list[WebSocket] = []
        for ws in self._clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)


# ─── Global agent manager ─────────────────────────────────────────────


class AgentManager:
    """Track one agent subprocess per project."""

    def __init__(self):
        self._agents: dict[str, AgentProcess] = {}

    def get(self, project_name: str) -> AgentProcess | None:
        agent = self._agents.get(project_name)
        if agent and not agent.is_running:
            del self._agents[project_name]
            return None
        return agent

    async def get_or_create(self, project_name: str, project_path: Path) -> AgentProcess:
        agent = self.get(project_name)
        if agent:
            return agent

        agent = AgentProcess(project_name, project_path)
        self._agents[project_name] = agent
        await agent.start()
        return agent

    async def stop(self, project_name: str) -> None:
        agent = self._agents.pop(project_name, None)
        if agent:
            await agent.stop()

    async def shutdown_all(self) -> None:
        """Stop all agents — called on server shutdown."""
        for name in list(self._agents.keys()):
            await self.stop(name)


agent_manager = AgentManager()


# ─── WebSocket endpoint ───────────────────────────────────────────────


@router.websocket("/ws/{project}/chat")
async def websocket_chat(websocket: WebSocket, project: str):
    """Interactive chat WebSocket endpoint.

    Spawns or reuses a Claude Code subprocess for the project.
    User messages → agent stdin, agent stdout → client.
    """
    await websocket.accept()

    try:
        project_path = _resolve_project(project)
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.close()
        return

    agent = await agent_manager.get_or_create(project, project_path)
    agent.add_client(websocket)

    # Notify client about connection state
    await websocket.send_json({
        "type": "status",
        "status": "ready" if agent.is_running else "starting",
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })
                continue

            msg_type = msg.get("type", "")

            if msg_type == "message":
                content = msg.get("content", "").strip()
                if not content:
                    continue

                # Check if agent is still running
                if not agent.is_running:
                    # Try to restart
                    agent = await agent_manager.get_or_create(project, project_path)
                    agent.add_client(websocket)

                try:
                    await agent.send_message(content)
                except RuntimeError as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e),
                    })

            elif msg_type == "stop":
                await agent_manager.stop(project)
                await websocket.send_json({
                    "type": "status",
                    "status": "stopped",
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Chat WebSocket error: {e}")
    finally:
        agent.remove_client(websocket)
        # Don't stop the agent on disconnect — user may reconnect


# ─── Helpers ──────────────────────────────────────────────────────────


def _summarize_input(input_data: Any) -> str:
    """Create a brief summary of tool input for display."""
    if isinstance(input_data, str):
        return input_data[:500]
    if isinstance(input_data, dict):
        # For common tools, extract key info
        if "command" in input_data:
            return input_data["command"][:500]
        if "file_path" in input_data:
            return f"file: {input_data['file_path']}"
        if "pattern" in input_data:
            return f"pattern: {input_data['pattern']}"
        if "query" in input_data:
            return f"query: {input_data['query']}"
        return json.dumps(input_data)[:500]
    return str(input_data)[:500]


def _summarize_output(output: Any) -> str:
    """Create a brief summary of tool output for display."""
    if isinstance(output, str):
        if len(output) > 1000:
            return output[:500] + f"\n... ({len(output)} chars total)"
        return output
    return str(output)[:1000]
