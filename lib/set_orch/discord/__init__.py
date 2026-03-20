"""Discord bot integration for set-core orchestration.

Provides real-time orchestration status updates to Discord channels
with thread-per-run organization and live-updating status embeds.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Singleton bot instance (set during lifespan)
_bot_instance: DiscordBot | None = None


def get_bot() -> DiscordBot | None:
    """Get the active Discord bot instance, or None if not running."""
    return _bot_instance


class DiscordBot:
    """Discord bot that subscribes to orchestration events and posts to Discord.

    Runs as a background task in the same asyncio loop as the FastAPI server.
    """

    def __init__(self, config: dict[str, Any], project_name: str = ""):
        self._config = config
        self._project_name = project_name or "set-core"
        self._client: Any = None  # discord.Client
        self._task: asyncio.Task | None = None
        self._ready = asyncio.Event()
        self._channel: Any = None  # discord.TextChannel
        self._stopping = False

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_ready()

    @property
    def channel(self) -> Any:
        return self._channel

    async def start(self) -> None:
        """Start the Discord bot as a background task."""
        global _bot_instance

        try:
            import discord
        except ImportError:
            logger.warning("discord.py not installed — run: pip install 'set-core[discord]'")
            return

        token = os.environ.get("SET_DISCORD_TOKEN", "")
        if not token:
            logger.warning("SET_DISCORD_TOKEN not set — Discord bot disabled")
            return

        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True

        self._client = discord.Client(intents=intents)
        bot = self

        @self._client.event
        async def on_ready():
            logger.info("Discord bot connected as %s", self._client.user)
            # Resolve channel
            from .channel import resolve_channel
            bot._channel = await resolve_channel(
                self._client,
                guild_id=bot._config.get("guild_id", ""),
                channel_name=bot._config.get("channel_name", "") or bot._project_name,
            )
            if bot._channel:
                logger.info("Discord channel: #%s", bot._channel.name)
            else:
                logger.error("Failed to resolve Discord channel — bot disabled")

            # Set presence
            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name=f"[SET] {bot._project_name}",
            )
            await self._client.change_presence(activity=activity)
            bot._ready.set()

        # Start in background with supervisor wrapper
        self._task = asyncio.create_task(self._supervised_run(token))
        _bot_instance = self
        logger.info("Discord bot starting...")

    async def _supervised_run(self, token: str) -> None:
        """Run the bot with exception isolation — never crash the API server."""
        backoff = [5, 10, 15, 30]
        attempt = 0
        while not self._stopping:
            try:
                await self._client.start(token)
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._stopping:
                    break
                delay = backoff[min(attempt, len(backoff) - 1)]
                logger.error("Discord bot error (retry in %ds): %s", delay, e)
                attempt += 1
                await asyncio.sleep(delay)
            else:
                break  # Clean exit

    async def stop(self) -> None:
        """Stop the Discord bot gracefully."""
        global _bot_instance
        self._stopping = True

        if self._client and not self._client.is_closed():
            # Flush pending throttled edits
            from .throttle import get_throttle
            throttle = get_throttle()
            if throttle:
                await throttle.flush()

            await self._client.close()

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        _bot_instance = None
        logger.info("Discord bot stopped")

    async def wait_ready(self, timeout: float = 30.0) -> bool:
        """Wait for the bot to be ready. Returns False on timeout."""
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
