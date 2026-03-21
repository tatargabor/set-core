"""File watcher for real-time state and log change detection.

Uses watchfiles (Rust-based) to monitor orchestration files and push
updates to connected WebSocket clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

logger = logging.getLogger("set-web.watcher")


class LogTailer:
    """Track file offset and yield only new lines (tail -f semantics)."""

    def __init__(self, path: Path):
        self.path = path
        self._offset = 0
        self._initialized = False

    def get_tail(self, n: int = 200) -> list[str]:
        """Read last n lines independently (does not affect offset tracking)."""
        if not self.path.exists():
            return []
        try:
            with open(self.path) as f:
                lines = f.readlines()
            return [l.rstrip() for l in lines[-n:]]
        except OSError:
            return []

    def read_new_lines(self) -> list[str]:
        """Read lines appended since last call. First call returns last 200 lines."""
        if not self.path.exists():
            return []

        try:
            file_size = self.path.stat().st_size
        except OSError:
            return []

        if not self._initialized:
            self._initialized = True
            try:
                with open(self.path) as f:
                    lines = f.readlines()
                self._offset = file_size
                return [l.rstrip() for l in lines[-200:]]
            except OSError:
                return []

        # File truncated (log rotation)
        if file_size < self._offset:
            self._offset = 0

        if file_size <= self._offset:
            return []

        try:
            with open(self.path, "rb") as f:
                f.seek(self._offset)
                new_bytes = f.read()
            self._offset = file_size
            text = new_bytes.decode("utf-8", errors="replace")
            return [l.rstrip() for l in text.splitlines() if l.strip()]
        except OSError:
            return []


class ProjectWatcher:
    """Watch orchestration files for a single project."""

    def __init__(self, project_name: str, project_path: Path):
        self.project_name = project_name
        self.project_path = project_path
        self._last_state: dict | None = None
        self._task: asyncio.Task | None = None
        # Resolve paths (re-resolved dynamically when not found)
        self.state_path = self._find_state()
        self.log_path = self._find_log()
        self.log_tailer = LogTailer(self.log_path)

    def _find_state(self) -> Path:
        # Project-local paths (engine writes here from CWD)
        new = self.project_path / "wt" / "orchestration" / "orchestration-state.json"
        if new.exists():
            return new
        legacy = self.project_path / "orchestration-state.json"
        if legacy.exists():
            return legacy
        # Try shared runtime dir (future: engine may write here)
        try:
            from .paths import SetRuntime
            rt = SetRuntime(str(self.project_path))
            runtime_state = Path(rt.state_file)
            if runtime_state.exists():
                return runtime_state
        except Exception:
            pass
        return new  # default

    def _find_log(self) -> Path:
        # Project-local paths first
        new = self.project_path / "wt" / "orchestration" / "orchestration.log"
        if new.exists():
            return new
        legacy = self.project_path / "orchestration.log"
        if legacy.exists():
            return legacy
        # Try shared runtime dir
        try:
            from .paths import SetRuntime
            rt = SetRuntime(str(self.project_path))
            runtime_log = Path(rt.orchestration_log)
            if runtime_log.exists():
                return runtime_log
        except Exception:
            pass
        return new  # default

    def _refresh_paths(self):
        """Re-discover state/log paths (handles files appearing at runtime)."""
        new_state = self._find_state()
        if new_state != self.state_path:
            self.state_path = new_state
            logger.info(f"State path updated for {self.project_name}: {new_state}")
        new_log = self._find_log()
        if new_log != self.log_path:
            self.log_path = new_log
            self.log_tailer = LogTailer(new_log)
            logger.info(f"Log path updated for {self.project_name}: {new_log}")

    def _read_state(self) -> dict | None:
        """Read state file as dict (lightweight, no dataclass parsing)."""
        if not self.state_path.exists():
            # Maybe it appeared at the other location
            self._refresh_paths()
        if not self.state_path.exists():
            return None
        try:
            with open(self.state_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def get_initial_state(self) -> dict | None:
        """Read and cache the initial state."""
        self._last_state = self._read_state()
        return self._last_state

    async def watch(self, callback):
        """Watch for file changes and invoke callback with events.

        callback(project_name, event_type, data) is called for each change.
        """
        try:
            from watchfiles import awatch, Change
        except ImportError:
            logger.warning("watchfiles not installed, falling back to polling")
            await self._poll_fallback(callback)
            return

        # Collect directories to watch (state and log may be in different dirs)
        watch_dirs: set[Path] = set()
        state_dir = self.state_path.parent
        log_dir = self.log_path.parent
        if state_dir.exists():
            watch_dirs.add(state_dir)
        if log_dir.exists():
            watch_dirs.add(log_dir)
        # Always watch project root for legacy file creation
        if self.project_path.exists():
            watch_dirs.add(self.project_path)

        if not watch_dirs:
            logger.info(f"No orchestration dir for {self.project_name}, polling for creation")
            await self._poll_fallback(callback)
            return

        try:
            async for changes in awatch(*watch_dirs, poll_delay_ms=500):
                for change_type, change_path in changes:
                    path = Path(change_path)
                    if path.name == "orchestration-state.json":
                        await self._handle_state_change(callback)
                    elif path.name == "orchestration.log":
                        await self._handle_log_change(callback)
        except Exception as e:
            logger.error(f"Watcher error for {self.project_name}: {e}")
            # Fall back to polling
            await self._poll_fallback(callback)

    async def _poll_fallback(self, callback):
        """Simple polling fallback when watchfiles is unavailable."""
        while True:
            await asyncio.sleep(3)
            self._refresh_paths()
            await self._handle_state_change(callback)
            await self._handle_log_change(callback)

    async def _handle_state_change(self, callback):
        """Detect state changes and emit events."""
        new_state = self._read_state()
        if new_state is None:
            return

        # Enrich changes with worktree log file lists and session count
        for c in new_state.get("changes", []):
            wt_path = c.get("worktree_path")
            if wt_path:
                logs_dir = Path(wt_path) / ".claude" / "logs"
                if logs_dir.is_dir():
                    try:
                        c["logs"] = sorted(
                            f.name for f in logs_dir.iterdir()
                            if f.is_file() and f.suffix == ".log"
                        )
                    except OSError:
                        pass

            # Count Claude JSONL sessions for this change (only with worktree)
            sessions_dir = None
            if wt_path:
                mangled = wt_path.lstrip("/").replace("/", "-")
                d = Path.home() / ".claude" / "projects" / f"-{mangled}"
                if d.is_dir():
                    sessions_dir = d
                elif c.get("status") in ("done", "merged", "failed", "verify-failed"):
                    mangled = str(self.project_path).lstrip("/").replace("/", "-")
                    d = Path.home() / ".claude" / "projects" / f"-{mangled}"
                    if d.is_dir():
                        sessions_dir = d
            if sessions_dir:
                try:
                    c["session_count"] = sum(
                        1 for f in sessions_dir.iterdir()
                        if f.is_file() and f.suffix == ".jsonl"
                    )
                except OSError:
                    pass

        old_status = self._last_state.get("status") if self._last_state else None
        new_status = new_state.get("status")

        # Emit state update
        await callback(self.project_name, "state_update", new_state)

        # Detect checkpoint transition
        if old_status != "checkpoint" and new_status == "checkpoint":
            checkpoints = new_state.get("checkpoints", [])
            changes = new_state.get("changes", [])
            done = sum(1 for c in changes if c.get("status") in ("done", "merged"))
            last_cp = checkpoints[-1] if checkpoints else {}
            await callback(self.project_name, "checkpoint_pending", {
                "checkpoint_id": len(checkpoints),
                "completed": done,
                "total": len(changes),
                "type": last_cp.get("type", "unknown"),
            })

        # Detect change completion
        if self._last_state:
            old_changes = {c["name"]: c.get("status") for c in self._last_state.get("changes", [])}
            for c in new_state.get("changes", []):
                name = c.get("name", "")
                new_st = c.get("status", "")
                old_st = old_changes.get(name, "")
                if old_st != new_st and new_st in ("done", "merged"):
                    await callback(self.project_name, "change_complete", {
                        "name": name,
                        "status": new_st,
                    })
                elif old_st != new_st and new_st == "failed":
                    await callback(self.project_name, "error", {
                        "message": f"Change failed: {name}",
                        "change": name,
                    })

        self._last_state = new_state

    async def _handle_log_change(self, callback):
        """Read new log lines and emit."""
        new_lines = self.log_tailer.read_new_lines()
        if new_lines:
            await callback(self.project_name, "log_lines", {"lines": new_lines})


class WatcherManager:
    """Manages watchers for all registered projects."""

    def __init__(self):
        self._watchers: dict[str, ProjectWatcher] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._connection_manager = None

    async def start(self, connection_manager):
        """Start watchers for all registered projects."""
        self._connection_manager = connection_manager

        projects_file = Path.home() / ".config" / "set-core" / "projects.json"
        if not projects_file.exists():
            logger.info("No projects.json found, no watchers started")
            return

        try:
            with open(projects_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        # Format: {"projects": {"name": {"path": "...", ...}}}
        projects = {}
        if isinstance(data, dict) and "projects" in data:
            projects = data["projects"]
        elif isinstance(data, list):
            # Legacy list format
            projects = {p.get("name", ""): p for p in data if isinstance(p, dict)}

        for name, info in projects.items():
            if not isinstance(info, dict):
                continue
            path = Path(info.get("path", ""))
            if name and path.is_dir():
                self._start_project_watcher(name, path)

    def _start_project_watcher(self, name: str, path: Path):
        """Start a watcher for a single project."""
        watcher = ProjectWatcher(name, path)
        self._watchers[name] = watcher
        self._tasks[name] = asyncio.create_task(
            watcher.watch(self._on_event),
            name=f"watcher-{name}",
        )
        logger.info(f"Started watcher for project: {name}")

    async def _on_event(self, project_name: str, event_type: str, data):
        """Forward watcher events to WebSocket clients and Discord bot."""
        if self._connection_manager:
            await self._connection_manager.broadcast(
                project_name,
                {"event": event_type, "data": data},
            )

        # Forward to Discord bot
        await self._forward_to_discord(project_name, event_type, data)

    async def _post_change_screenshots(
        self, bot: Any, project_name: str, change_name: str,
        screenshot_dir: str, spoiler: bool = True, caption_prefix: str = "\U0001f4f8 Smoke failed",
    ):
        """Post screenshots from a change's screenshot directory to the active Discord thread."""
        try:
            from .discord.screenshots import post_screenshots, get_active_thread

            # Resolve absolute path from project
            watcher = self._watchers.get(project_name)
            if not watcher:
                return
            abs_dir = watcher.project_path / screenshot_dir
            if not abs_dir.is_dir():
                return

            paths = sorted(abs_dir.rglob("*.png"))
            if not paths:
                return

            thread = get_active_thread()
            if not thread:
                return

            caption = f"{caption_prefix}: **{change_name}** ({len(paths)} screenshots)"
            await post_screenshots(thread, paths, caption=caption, spoiler=spoiler)
        except Exception as e:
            logger.debug("Failed to post screenshots for %s: %s", change_name, e)

    async def _forward_to_discord(self, project_name: str, event_type: str, data):
        """Bridge watcher events to Discord bot."""
        try:
            from .discord import get_bot
        except ImportError:
            return

        bot = get_bot()
        if not bot or not bot.is_connected:
            return

        try:
            # Resolve project-specific channel
            channel = await bot.get_channel_for_project(project_name)
            if not channel:
                return

            from .discord.events import _handle_event
            config = getattr(bot, "_discord_config", {})
            member_name = getattr(bot, "_member_name", "unknown")

            # Map watcher events to orchestration event bus format
            if event_type == "state_update":
                # Full state — detect orchestration-level status
                status = data.get("status", "")
                changes = data.get("changes", [])

                # Check for run start/complete
                if not hasattr(self, "_discord_last_status"):
                    self._discord_last_status = {}
                last = self._discord_last_status.get(project_name)

                if last != status:
                    self._discord_last_status[project_name] = status
                    await _handle_event(bot, config, member_name, {
                        "type": "STATE_CHANGE",
                        "change": "",
                        "data": {
                            "to": status,
                            "run_id": str(abs(hash(project_name)) % 10000),
                            "change_count": len(changes),
                        },
                    }, channel=channel)

                # Per-change status updates
                if not hasattr(self, "_discord_screenshots_posted"):
                    self._discord_screenshots_posted = set()

                for c in changes:
                    change_key = f"{project_name}:{c.get('name', '')}"
                    c_status = c.get("status", "")
                    last_c = self._discord_last_status.get(change_key)
                    if last_c != c_status:
                        self._discord_last_status[change_key] = c_status
                        await _handle_event(bot, config, member_name, {
                            "type": "STATE_CHANGE",
                            "change": c.get("name", ""),
                            "data": {"to": c_status},
                        }, channel=channel)

                        # Post smoke screenshots on verify-failed
                        if c_status == "verify-failed" and change_key not in self._discord_screenshots_posted:
                            sc_count = c.get("smoke_screenshot_count", 0)
                            sc_dir = c.get("smoke_screenshot_dir", "")
                            if sc_count and sc_dir:
                                await self._post_change_screenshots(
                                    bot, project_name, c.get("name", ""), sc_dir, spoiler=True
                                )
                                self._discord_screenshots_posted.add(change_key)

                        # Post E2E screenshots when count changes from 0
                        e2e_count = c.get("e2e_screenshot_count", 0)
                        e2e_dir = c.get("e2e_screenshot_dir", "")
                        e2e_key = f"{change_key}:e2e"
                        if e2e_count and e2e_dir and e2e_key not in self._discord_screenshots_posted:
                            await self._post_change_screenshots(
                                bot, project_name, c.get("name", ""), e2e_dir,
                                caption_prefix="\U0001f4f8 E2E", spoiler=False
                            )
                            self._discord_screenshots_posted.add(e2e_key)

            elif event_type == "change_complete":
                await _handle_event(bot, config, member_name, {
                    "type": "MERGE_ATTEMPT",
                    "change": data.get("name", ""),
                    "data": {"result": "success"},
                }, channel=channel)

            elif event_type == "error":
                await _handle_event(bot, config, member_name, {
                    "type": "ERROR",
                    "change": data.get("change", ""),
                    "data": {"message": data.get("message", "")},
                }, channel=channel)

        except Exception as e:
            logger.debug("Discord forward error: %s", e)

    async def stop(self):
        """Stop all watchers."""
        for name, task in self._tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        self._watchers.clear()
        logger.info("All watchers stopped")

    def get_watcher(self, project_name: str) -> ProjectWatcher | None:
        """Get watcher for a project (for initial state on WS connect)."""
        return self._watchers.get(project_name)
