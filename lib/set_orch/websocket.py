"""WebSocket connection manager and endpoints for real-time streaming.

Manages per-project client connections and broadcasts watcher events.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("set-web.websocket")

router = APIRouter()


class ConnectionManager:
    """Track WebSocket connections per project and broadcast events."""

    def __init__(self):
        # project_name -> set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, project_name: str, websocket: WebSocket):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        if project_name not in self._connections:
            self._connections[project_name] = set()
        self._connections[project_name].add(websocket)
        logger.info(f"WS connect: {project_name} (total: {len(self._connections[project_name])})")

    def disconnect(self, project_name: str, websocket: WebSocket):
        """Remove a WebSocket connection."""
        conns = self._connections.get(project_name)
        if conns:
            conns.discard(websocket)
            if not conns:
                del self._connections[project_name]
        logger.info(f"WS disconnect: {project_name}")

    async def broadcast(self, project_name: str, message: dict[str, Any]):
        """Send a message to all clients connected to a project."""
        conns = self._connections.get(project_name)
        if not conns:
            return

        payload = json.dumps(message)
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        # Clean up dead connections
        for ws in dead:
            conns.discard(ws)
        if not conns:
            self._connections.pop(project_name, None)

    def client_count(self, project_name: str) -> int:
        return len(self._connections.get(project_name, set()))


# Singleton manager — shared between server.py lifespan and routes
connection_manager = ConnectionManager()


@router.websocket("/ws/{project}/stream")
async def websocket_stream(websocket: WebSocket, project: str):
    """WebSocket endpoint for real-time project updates.

    On connect: sends full current state.
    After: receives push events from the watcher.
    """
    await connection_manager.connect(project, websocket)

    # Send initial state
    try:
        watcher_mgr = websocket.app.state.watcher_manager
        watcher = watcher_mgr.get_watcher(project)
        if watcher:
            initial_state = watcher.get_initial_state()
            if initial_state:
                await websocket.send_json({
                    "event": "state_update",
                    "data": initial_state,
                })

            # Send initial log lines (get_tail is independent of offset tracking)
            initial_lines = watcher.log_tailer.get_tail(500)
            if initial_lines:
                await websocket.send_json({
                    "event": "log_lines",
                    "data": {"lines": initial_lines},
                })
    except Exception as e:
        logger.error(f"Error sending initial state: {e}")

    # Keep connection alive — events are pushed by the watcher via broadcast
    try:
        while True:
            # Wait for client messages (ping/pong or close)
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connection_manager.disconnect(project, websocket)
