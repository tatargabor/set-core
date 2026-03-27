"""FastAPI application factory for the set-core unified web service.

Creates the app with CORS, lifespan management (watcher, Discord, supervisor,
issue engine), API routes, WebSocket endpoints, and static SPA file serving.

This is the SINGLE entry point — replaces both set-orch-core and set-manager.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router as api_router, include_optional_routers
from .chat import router as chat_router, session_manager
from .watcher import WatcherManager
from .websocket import router as ws_router, connection_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start watchers, Discord, supervisor, and issue engine on startup."""
    watcher = app.state.watcher_manager
    await watcher.start(connection_manager)

    # Start unified service (supervisor + issue engine)
    try:
        from .api.lifecycle import startup as service_startup, shutdown as service_shutdown
        await service_startup(app)
    except Exception as e:
        import traceback
        print(f"[SET] Service startup failed: {e}", flush=True)
        traceback.print_exc()

    # Start Discord bot if configured
    discord_bot = None
    try:
        from .config import get_discord_config, load_config_file
        orch_path = _find_orch_config()
        print(f"[SET] Discord: orch_config={'found' if orch_path else 'none'}", flush=True)
        config = load_config_file(orch_path) if orch_path else {}
        discord_config = get_discord_config(config)
        if discord_config:
            from .discord import DiscordBot
            from .discord.events import setup_event_handler
            project_name = config.get("project_name", "") or "set-core"
            discord_bot = DiscordBot(discord_config, project_name=project_name)
            await discord_bot.start()
            print("[SET] Discord bot starting...", flush=True)
            if await discord_bot.wait_ready(timeout=15):
                await setup_event_handler(discord_bot, discord_config)
                print("[SET] Discord bot connected", flush=True)
            else:
                print("[SET] Discord bot timeout — not connected", flush=True)
        else:
            print("[SET] Discord not configured", flush=True)
    except Exception as e:
        import traceback
        print(f"[SET] Discord bot startup failed: {e}", flush=True)
        traceback.print_exc()

    yield

    # Shutdown: Discord → service → sessions → watchers
    if discord_bot:
        try:
            await discord_bot.stop()
        except Exception:
            pass
    try:
        from .api.lifecycle import shutdown as service_shutdown
        await service_shutdown()
    except Exception:
        pass
    await session_manager.stop_all()
    await watcher.stop()


def _find_orch_config() -> str | None:
    """Find orchestration config file for Discord settings."""
    for candidate in [
        Path.cwd() / ".claude" / "orchestration.yaml",
        Path.cwd() / "set" / "orchestration" / "config.yaml",
    ]:
        if candidate.is_file():
            return str(candidate)
    return None


def create_app(web_dist_dir: str | None = None) -> FastAPI:
    """Create and configure the unified FastAPI application.

    Args:
        web_dist_dir: Path to the built SPA directory (web/dist/).
                      If None, tries to find it relative to the package.
    """
    app = FastAPI(
        title="set-core",
        version="0.2.0",
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

    # Service status endpoint
    @app.get("/api/service/status")
    async def service_status():
        from .api.lifecycle import get_service
        svc = get_service()
        if not svc:
            return {"status": "not_initialized"}
        return svc.status()

    # Core API routes (orchestration, sessions, media, actions, learnings, sentinel events)
    app.include_router(api_router)
    # Optional routes (sentinel control, issues, plugins) — depend on lifecycle
    include_optional_routers(app.router)
    # WebSocket and chat routes
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

        assets_dir = dist_path / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{file_path:path}")
        async def spa_catchall(request: Request, file_path: str):
            real_file = dist_path / file_path
            if file_path and real_file.is_file() and ".." not in file_path:
                return FileResponse(str(real_file))
            return FileResponse(str(index_html))

    return app
