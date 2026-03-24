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

from fastapi.responses import Response

from .api import router as api_router
from .chat import router as chat_router, session_manager
from .watcher import WatcherManager
from .websocket import router as ws_router, connection_manager

# Manager proxy config
MANAGER_URL = os.environ.get("SET_MANAGER_URL", "http://localhost:3112")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start file watchers and Discord bot on startup, stop on shutdown."""
    watcher = app.state.watcher_manager
    await watcher.start(connection_manager)

    # Start Discord bot if configured (global auto_enable or per-project config)
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
            # Setup event handler (stores config/member on bot for watcher bridge)
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

    # Shutdown: Discord first (flush pending), then sessions, then watchers
    if discord_bot:
        try:
            await discord_bot.stop()
        except Exception:
            pass
    await session_manager.stop_all()
    await watcher.stop()


def _find_orch_config() -> str | None:
    """Find orchestration config file for Discord settings."""
    from pathlib import Path
    for candidate in [
        Path.cwd() / ".claude" / "orchestration.yaml",
        Path.cwd() / "wt" / "orchestration" / "config.yaml",
    ]:
        if candidate.is_file():
            return str(candidate)
    return None


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

    # Manager API proxy — forward /api/manager/* to set-manager service
    @app.api_route("/api/manager/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def manager_proxy(request: Request, path: str):
        """Reverse proxy to set-manager API. Strips /api/manager prefix."""
        import aiohttp
        target_url = f"{MANAGER_URL}/api/{path}"
        qs = str(request.query_params)
        if qs:
            target_url += f"?{qs}"

        body = await request.body() if request.method in ("POST", "PUT", "PATCH") else None
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length", "transfer-encoding")
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    data=body,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    resp_body = await resp.read()
                    return Response(
                        content=resp_body,
                        status_code=resp.status,
                        media_type=resp.content_type,
                    )
        except aiohttp.ClientError:
            return Response(
                content='{"error": "set-manager is not running"}',
                status_code=502,
                media_type="application/json",
            )

    @app.post("/api/manager-start")
    async def start_manager():
        """Start set-manager if not running. Called from web UI when manager is offline."""
        import asyncio
        import shutil
        # Check if already running
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{MANAGER_URL}/api/manager/status", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        return {"status": "already_running"}
        except Exception:
            pass
        # Remove stale PID file
        pid_file = Path.home() / ".local" / "share" / "set-core" / "manager" / "manager.pid"
        pid_file.unlink(missing_ok=True)
        # Start manager in background
        manager_bin = shutil.which("set-manager")
        if not manager_bin:
            return Response(content='{"error": "set-manager not found in PATH"}', status_code=500, media_type="application/json")
        proc = await asyncio.create_subprocess_exec(
            manager_bin, "serve",
            stdout=open("/tmp/set-manager.log", "a"),
            stderr=open("/tmp/set-manager.log", "a"),
            start_new_session=True,
        )
        return {"status": "started", "pid": proc.pid}

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
