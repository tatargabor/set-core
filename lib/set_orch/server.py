"""FastAPI application factory for the set-web dashboard.

Creates the app with CORS, lifespan management (watcher start/stop),
API routes, WebSocket endpoints, and static SPA file serving.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router as api_router
from .chat import router as chat_router, session_manager
from .watcher import WatcherManager
from .websocket import router as ws_router, connection_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start file watchers on startup, stop on shutdown."""
    watcher = app.state.watcher_manager
    await watcher.start(connection_manager)
    yield
    await session_manager.stop_all()
    await watcher.stop()


def create_app(web_dist_dir: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        web_dist_dir: Path to the built SPA directory (web/dist/).
                      If None, tries to find it relative to the package.
    """
    app = FastAPI(
        title="set-core Web Dashboard",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS for dev (Vite dev server on different port)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # State
    app.state.watcher_manager = WatcherManager()

    # API, WebSocket, and chat routes
    app.include_router(api_router)
    app.include_router(ws_router)
    app.include_router(chat_router)

    # Static SPA serving
    if web_dist_dir is None:
        candidate = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
        if candidate.is_dir():
            web_dist_dir = str(candidate)

    if web_dist_dir and Path(web_dist_dir).is_dir():
        dist_path = Path(web_dist_dir)
        index_html = dist_path / "index.html"

        # Serve static assets (js, css, images) from /assets/
        assets_dir = dist_path / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        # Serve other static files at root (favicon.svg, icons.svg, etc.)
        @app.get("/{file_path:path}")
        async def spa_catchall(request: Request, file_path: str):
            # Try serving as a real file first
            real_file = dist_path / file_path
            if file_path and real_file.is_file() and ".." not in file_path:
                return FileResponse(str(real_file))
            # Otherwise return index.html for client-side routing
            return FileResponse(str(index_html))

    return app
