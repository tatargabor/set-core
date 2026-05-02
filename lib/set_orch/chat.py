"""WebSocket chat endpoint for interactive agent communication.

Uses claude -p --resume {session_id} for multi-turn chat.
Each message spawns a clean subprocess; Claude Code maintains
context server-side via --resume.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .api.helpers import _resolve_project
from .chat_context import build_chat_context

logger = logging.getLogger("set-web.chat")

router = APIRouter()

# ─── Chat session (resume-based) ─────────────────────────────────────


class ChatSession:
    """Manages a resume-based chat session for a project."""

    def __init__(self, project_name: str, project_path: Path):
        self.project_name = project_name
        self.project_path = project_path
        self.session_id: str | None = None
        self.messages: list[dict[str, Any]] = []
        self.status: str = "idle"  # idle | running
        # Resolve model via the unified config; falls back to the framework
        # default (opus-4-6) when no operator override is set.
        from .model_config import resolve_model
        self.model: str = resolve_model("agent", project_dir=str(project_path))
        self._current_process: asyncio.subprocess.Process | None = None
        self._clients: set[WebSocket] = set()
        self._generation: int = 0  # Incremented on stop/new_session to invalidate stale tasks
        self._state_watcher: asyncio.Task | None = None
        self._last_state_mtime: float = 0.0

    async def send_message(self, text: str) -> None:
        """Send a user message — spawns a claude subprocess.

        Caller must set self.status = "running" before calling to
        prevent races between WS message arrival and task scheduling.
        """
        gen = self._generation
        self.messages.append({"role": "user", "content": text, "timestamp": _now_ms()})
        await self._broadcast({"type": "status", "status": "thinking"})

        try:
            await self._run_claude(text)
        except Exception as e:
            logger.error(f"Claude run failed [{self.project_name}]: {e}")
            if self._generation == gen:
                await self._broadcast({"type": "error", "message": str(e)})
        finally:
            if self._generation == gen:
                self.status = "idle"
                self._current_process = None

    async def stop(self) -> None:
        """Kill the current subprocess if running."""
        self._generation += 1
        proc = self._current_process
        if not proc or proc.returncode is not None:
            return

        logger.info(f"Stopping claude process for {self.project_name} (PID {proc.pid})")
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
        except ProcessLookupError:
            pass

        self.status = "idle"
        self._current_process = None
        await self._broadcast({"type": "status", "status": "idle"})

    def new_session(self) -> None:
        """Clear session state for a fresh conversation."""
        self._generation += 1
        self.session_id = None
        self.messages = []
        self.status = "idle"

    def _build_claude_cmd(self, text: str, context: str) -> list[str]:
        """Build the claude subprocess argv.

        Contract: every claude invocation in this codebase passes --model
        explicitly. Resume does NOT exempt — relying on the CLI's session-
        side model carry-over creates an implicit dependency that the
        upcoming model-config rollout cannot audit. --model is appended
        before --resume so the current `self.model` value wins.
        """
        cmd = [
            "claude", "-p", "--output-format", "stream-json", "--verbose",
            "--model", self.model,
        ]
        if context:
            cmd.extend(["--append-system-prompt", context])
        if self.session_id:
            cmd.extend(["--resume", self.session_id])
        else:
            cmd.extend(["--permission-mode", "auto"])
        cmd.extend(["--", text])
        return cmd

    async def _run_claude(self, text: str, *, _retry: bool = False) -> None:
        """Core subprocess logic — spawn claude, stream JSON, broadcast."""
        gen = self._generation
        env = {**os.environ}
        env.pop("CLAUDECODE", None)  # Prevent nested session protection

        # Build dynamic supervisor context (fresh on every message)
        context = build_chat_context(self.project_path)

        cmd = self._build_claude_cmd(text, context)

        logger.info(f"Spawning claude [{self.project_name}]: {' '.join(cmd[:8])}...")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.project_path),
            env=env,
        )
        self._current_process = proc

        # Collect stderr for post-exit analysis
        stderr_lines: list[str] = []

        async def _collect_stderr():
            if not proc.stderr:
                return
            try:
                async for line in proc.stderr:
                    s = line.decode("utf-8", errors="replace").strip()
                    if s:
                        stderr_lines.append(s)
                        logger.debug(f"Claude stderr [{self.project_name}]: {s}")
            except Exception:
                pass

        stderr_task = asyncio.create_task(_collect_stderr())

        # Collect assistant response for history
        assistant_text = ""
        tool_blocks: list[dict] = []
        result_event: dict[str, Any] | None = None

        try:
            async for line in proc.stdout:
                if self._generation != gen:
                    break  # Session was reset, abandon this run

                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                try:
                    event = json.loads(line_str)
                except json.JSONDecodeError:
                    logger.debug(f"Non-JSON stdout: {line_str[:200]}")
                    continue

                evt_type = event.get("type", "")

                # Extract session_id from init event
                if evt_type == "system" and event.get("subtype") == "init":
                    sid = event.get("session_id")
                    if sid:
                        self.session_id = sid
                        logger.info(f"Session ID [{self.project_name}]: {sid}")
                    continue

                mapped = self._map_event(event)
                if not mapped:
                    continue

                # Track assistant content for history
                if mapped["type"] == "assistant_text":
                    assistant_text += mapped.get("content", "")
                elif mapped["type"] == "tool_use":
                    tool_blocks.append({
                        "tool": mapped.get("tool", ""),
                        "input": mapped.get("input", ""),
                    })
                elif mapped["type"] == "assistant_done":
                    result_event = mapped

                await self._broadcast(mapped)

        except Exception as e:
            logger.error(f"Error reading claude stdout [{self.project_name}]: {e}")

        # Wait for process and stderr to finish
        await proc.wait()
        await stderr_task

        if self._generation != gen:
            return  # Session was reset while we were running

        exit_code = proc.returncode
        logger.info(f"Claude exited [{self.project_name}]: code={exit_code}")

        # Handle stale session_id — retry fresh (once only)
        if exit_code != 0 and self.session_id and not _retry:
            stderr_text = " ".join(stderr_lines).lower()
            if "session" in stderr_text or not assistant_text:
                logger.warning(f"Possible stale session, retrying fresh [{self.project_name}]")
                self.session_id = None
                await self._broadcast({"type": "error", "message": "Session expired, retrying..."})
                await self._run_claude(text, _retry=True)
                return

        # Store assistant response in history
        if assistant_text or tool_blocks:
            msg: dict[str, Any] = {
                "role": "assistant",
                "content": assistant_text,
                "timestamp": _now_ms(),
            }
            if tool_blocks:
                msg["tool_blocks"] = tool_blocks
            if result_event:
                msg["cost_usd"] = result_event.get("cost_usd")
                msg["duration_ms"] = result_event.get("duration_ms")
            self.messages.append(msg)

        # Send final done if we didn't already
        if not result_event:
            await self._broadcast({"type": "assistant_done"})

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

        return None

    def add_client(self, ws: WebSocket) -> None:
        self._clients.add(ws)
        # Start state watcher if not running
        if not self._state_watcher:
            self._state_watcher = asyncio.create_task(self._watch_state())

    def remove_client(self, ws: WebSocket) -> None:
        self._clients.discard(ws)
        # Stop state watcher if no clients
        if not self._clients and self._state_watcher:
            self._state_watcher.cancel()
            self._state_watcher = None

    async def _watch_state(self) -> None:
        """Poll the orchestration state (LineagePaths.state_file) for changes."""
        from .paths import LineagePaths as _LP_chat
        state_paths = [Path(_LP_chat(str(self.project_path)).state_file)]
        try:
            while True:
                await asyncio.sleep(5)
                if not self._clients:
                    break
                for sp in state_paths:
                    try:
                        mtime = sp.stat().st_mtime
                    except OSError:
                        continue
                    if mtime > self._last_state_mtime:
                        self._last_state_mtime = mtime
                        try:
                            data = json.loads(sp.read_text())
                            summary = self._summarize_state(data)
                            await self._broadcast({"type": "state_update", **summary})
                        except Exception as e:
                            logger.debug(f"State watch read error: {e}")
                    break  # Use first found path
        except asyncio.CancelledError:
            pass

    @staticmethod
    def _summarize_state(data: dict[str, Any]) -> dict[str, Any]:
        """Build a compact state summary for the frontend."""
        changes = data.get("changes", [])
        by_status: dict[str, int] = {}
        for c in changes:
            s = c.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
        done = sum(by_status.get(s, 0) for s in ("done", "merged", "completed"))
        return {
            "status": data.get("status", "unknown"),
            "total": len(changes),
            "done": done,
            "by_status": by_status,
            "changes": [
                {"name": c.get("name", "?"), "status": c.get("status", "?")}
                for c in changes
            ],
        }

    async def _broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to all connected WebSocket clients."""
        payload = json.dumps(message)
        dead: list[WebSocket] = []
        for ws in self._clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)


# ─── Session manager ─────────────────────────────────────────────────


class SessionManager:
    """Track one ChatSession per project."""

    def __init__(self):
        self._sessions: dict[str, ChatSession] = {}

    def get_or_create(self, project_name: str, project_path: Path) -> ChatSession:
        session = self._sessions.get(project_name)
        if not session:
            session = ChatSession(project_name, project_path)
            self._sessions[project_name] = session
        return session

    async def stop(self, project_name: str) -> None:
        session = self._sessions.get(project_name)
        if session:
            await session.stop()

    async def stop_all(self) -> None:
        """Stop all sessions — called on server shutdown."""
        for session in self._sessions.values():
            await session.stop()


session_manager = SessionManager()


# ─── WebSocket endpoint ───────────────────────────────────────────────


@router.websocket("/ws/{project}/chat")
async def websocket_chat(websocket: WebSocket, project: str):
    """Interactive chat WebSocket endpoint.

    Each message spawns a fresh claude -p --resume process.
    Server maintains history for replay on reconnect.
    """
    await websocket.accept()

    try:
        project_path = _resolve_project(project)
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.close()
        return

    session = session_manager.get_or_create(project, project_path)
    session.add_client(websocket)

    # Replay history + current status on connect
    await websocket.send_json({
        "type": "history_replay",
        "messages": session.messages,
        "status": session.status,
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = msg.get("type", "")
            logger.info(f"WS received [{project}]: type={msg_type}")

            if msg_type == "message":
                content = msg.get("content", "").strip()
                if not content:
                    continue

                if session.status == "running":
                    await websocket.send_json({
                        "type": "error",
                        "message": "Already processing a message, please wait",
                    })
                    continue

                # Set running synchronously to prevent race with rapid messages
                session.status = "running"
                asyncio.create_task(session.send_message(content))

            elif msg_type == "start":
                # Explicit client-initiated greeting — only spawned on user request.
                if session.status == "running":
                    await websocket.send_json({
                        "type": "error",
                        "message": "Already processing a message, please wait",
                    })
                    continue

                logger.info(f"Start greeting requested [{project}]")
                session.status = "running"
                asyncio.create_task(session.send_message(
                    "Say hi and give a short orchestration status summary."
                ))

            elif msg_type == "stop":
                await session.stop()

            elif msg_type == "new_session":
                await session.stop()
                session.new_session()
                await session._broadcast({"type": "session_cleared"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Chat WebSocket error: {e}")
    finally:
        session.remove_client(websocket)


# ─── Helpers ──────────────────────────────────────────────────────────


def _now_ms() -> int:
    import time
    return int(time.time() * 1000)


def _summarize_input(input_data: Any) -> str:
    """Create a brief summary of tool input for display."""
    if isinstance(input_data, str):
        return input_data[:500]
    if isinstance(input_data, dict):
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
