"""Thread management — one thread per orchestration run."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Module-level thread registry (run_id → thread)
_threads: dict[str, Any] = {}


async def get_or_create_thread(
    channel: Any,
    run_id: str,
    member_name: str,
    change_count: int,
) -> Any | None:
    """Get existing thread for run_id or create a new one.

    Thread name format: "Run #N — member — X changes"
    """
    import discord

    # Check cache first
    if run_id in _threads:
        thread = _threads[run_id]
        if not thread.archived:
            return thread
        # Thread was archived, try to unarchive
        try:
            await thread.edit(archived=False)
            return thread
        except discord.HTTPException:
            pass

    # Search existing threads (for restart recovery)
    thread_name_prefix = f"Run #{run_id}"
    try:
        # Check active threads
        for thread in channel.threads:
            if thread.name.startswith(thread_name_prefix):
                _threads[run_id] = thread
                return thread

        # Check archived threads
        async for thread in channel.archived_threads(limit=50):
            if thread.name.startswith(thread_name_prefix):
                await thread.edit(archived=False)
                _threads[run_id] = thread
                return thread
    except discord.HTTPException:
        pass

    # Create new thread
    thread_name = f"Run #{run_id} — {member_name} — {change_count} changes"
    # Discord thread name max 100 chars
    if len(thread_name) > 100:
        thread_name = thread_name[:97] + "..."

    try:
        thread = await channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.public_thread,
            auto_archive_duration=1440,  # 24 hours
        )
        _threads[run_id] = thread
        logger.info("Created Discord thread: %s", thread_name)
        return thread
    except discord.HTTPException as e:
        logger.error("Failed to create Discord thread: %s", e)
        return None


async def archive_thread(run_id: str) -> None:
    """Archive a run's thread (set auto-archive to 1 hour)."""
    import discord

    thread = _threads.get(run_id)
    if not thread:
        return
    try:
        await thread.edit(
            auto_archive_duration=60,  # 1 hour
            archived=False,  # let Discord auto-archive
        )
    except discord.HTTPException:
        pass


def get_thread(run_id: str) -> Any | None:
    """Get cached thread for a run_id."""
    return _threads.get(run_id)


def clear_threads() -> None:
    """Clear thread cache (for testing or shutdown)."""
    _threads.clear()
