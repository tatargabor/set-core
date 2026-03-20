"""Channel resolution — find or create project channel in Discord guild."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _sanitize_channel_name(name: str) -> str:
    """Convert project name to valid Discord channel name (lowercase, hyphens, no spaces)."""
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9-]", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name[:100] or "set-core"


async def resolve_channel(
    client: Any,
    guild_id: str,
    channel_name: str,
) -> Any | None:
    """Find or create the project channel in the configured guild.

    Returns the TextChannel or None if resolution fails.
    """
    import discord

    if not guild_id:
        logger.error("Discord guild_id not configured")
        return None

    try:
        guild_id_int = int(guild_id)
    except ValueError:
        logger.error("Invalid Discord guild_id: %s", guild_id)
        return None

    guild = client.get_guild(guild_id_int)
    if not guild:
        logger.error("Discord guild not found: %s (bot may not be a member)", guild_id)
        return None

    sanitized = _sanitize_channel_name(channel_name)

    # Search for existing channel
    for ch in guild.text_channels:
        if ch.name == sanitized:
            return ch

    # Try to create channel
    try:
        channel = await guild.create_text_channel(
            name=sanitized,
            topic=f"set-core orchestration for {channel_name}",
        )
        logger.info("Created Discord channel #%s in guild %s", sanitized, guild.name)
        return channel
    except discord.Forbidden:
        logger.error(
            "Cannot create channel #%s — bot lacks 'Manage Channels' permission. "
            "Create the channel manually or grant the permission.",
            sanitized,
        )
        return None
    except discord.HTTPException as e:
        logger.error("Failed to create Discord channel: %s", e)
        return None
