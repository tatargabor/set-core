"""Embed update throttling — batch edits to respect Discord rate limits.

Discord rate limit: 5 requests / 5 seconds per channel.
Threads count separately from channels.
We throttle to at most 1 edit per 30 seconds per message.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

# Singleton throttle
_throttle: EmbedThrottle | None = None

THROTTLE_INTERVAL = 30.0  # seconds between edits


def get_throttle() -> EmbedThrottle | None:
    return _throttle


def create_throttle() -> EmbedThrottle:
    global _throttle
    _throttle = EmbedThrottle()
    return _throttle


class EmbedThrottle:
    """Batches embed updates and sends at most once per THROTTLE_INTERVAL."""

    def __init__(self, interval: float = THROTTLE_INTERVAL):
        self._interval = interval
        # message_id → (message, latest_embed_builder, last_sent_at, pending_task)
        self._pending: dict[int, _PendingEdit] = {}
        self._running = True

    async def schedule_edit(
        self,
        message: Any,
        build_embed: Callable[[], Coroutine[Any, Any, Any]],
    ) -> None:
        """Schedule an embed edit for a message. Batches rapid updates."""
        msg_id = message.id
        now = time.monotonic()

        if msg_id in self._pending:
            pending = self._pending[msg_id]
            pending.build_embed = build_embed
            # If enough time passed since last send, send now
            if now - pending.last_sent_at >= self._interval:
                await self._do_edit(msg_id)
            # Otherwise the scheduled task will pick it up
            return

        # First time — send immediately, then schedule future edits
        self._pending[msg_id] = _PendingEdit(
            message=message,
            build_embed=build_embed,
            last_sent_at=0,  # force immediate send
        )
        await self._do_edit(msg_id)
        # Schedule recurring check
        self._pending[msg_id].task = asyncio.create_task(
            self._edit_loop(msg_id)
        )

    async def _edit_loop(self, msg_id: int) -> None:
        """Periodically flush pending edits for a message."""
        while self._running and msg_id in self._pending:
            await asyncio.sleep(self._interval)
            if msg_id in self._pending and self._pending[msg_id].dirty:
                await self._do_edit(msg_id)

    async def _do_edit(self, msg_id: int) -> None:
        """Execute the actual Discord message edit."""
        pending = self._pending.get(msg_id)
        if not pending:
            return

        try:
            embed = await pending.build_embed()
            await pending.message.edit(embed=embed)
            pending.last_sent_at = time.monotonic()
            pending.dirty = False
        except Exception as e:
            logger.debug("Discord embed edit failed: %s", e)

    async def flush(self) -> None:
        """Flush all pending edits (called on shutdown)."""
        self._running = False
        for msg_id in list(self._pending.keys()):
            pending = self._pending[msg_id]
            if pending.dirty:
                await self._do_edit(msg_id)
            if pending.task and not pending.task.done():
                pending.task.cancel()
        self._pending.clear()


class _PendingEdit:
    def __init__(self, message: Any, build_embed: Callable, last_sent_at: float):
        self.message = message
        self._build_embed = build_embed
        self.last_sent_at = last_sent_at
        self.dirty = True
        self.task: asyncio.Task | None = None

    @property
    def build_embed(self) -> Callable:
        return self._build_embed

    @build_embed.setter
    def build_embed(self, value: Callable) -> None:
        self._build_embed = value
        self.dirty = True
