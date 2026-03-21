"""Event handler — subscribes to orchestration event bus and routes to Discord actions."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Track run state for embed updates
_run_state: dict[str, _RunState] = {}


class _RunState:
    """Tracks state for a single orchestration run."""

    __slots__ = (
        "run_id", "member_name", "changes", "start_time",
        "total_tokens", "status_message", "status",
    )

    def __init__(self, run_id: str, member_name: str):
        self.run_id = run_id
        self.member_name = member_name
        self.changes: list[dict[str, Any]] = []
        self.start_time = datetime.now(timezone.utc)
        self.total_tokens = 0
        self.status_message: Any = None  # Discord message with live embed
        self.status = "running"


def _get_member_name() -> str:
    """Get member name in set-core format: user@hostname."""
    try:
        import subprocess
        user = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip().lower().replace(" ", "-")
    except Exception:
        user = os.environ.get("USER", "unknown")
    hostname = socket.gethostname().split(".")[0].lower()
    return f"{user}@{hostname}"


def _get_mention(config: dict[str, Any], member_name: str) -> str:
    """Resolve Discord mention for a member."""
    member_map = config.get("member_map", {})
    discord_id = member_map.get(member_name)
    if discord_id:
        return f"<@{discord_id}>"
    fallback = config.get("mention_on_error", "")
    if fallback:
        if fallback.startswith("<@"):
            return fallback
        # Could be a role name like @oncall — Discord needs role ID
        return fallback
    return ""


def _should_notify_main(config: dict[str, Any], event_type: str) -> bool:
    """Check if this event type should post to the main channel."""
    from ..config import DISCORD_DEFAULT_NOTIFY_ON
    notify_on = config.get("notify_on", DISCORD_DEFAULT_NOTIFY_ON)
    # Map event bus types to config notify_on values
    event_map = {
        "start": "start",
        "MERGE_ATTEMPT": "merge",
        "merge": "merge",
        "stuck": "stuck",
        "crash": "crash",
        "complete": "complete",
        "done": "complete",
        "failed": "complete",
    }
    mapped = event_map.get(event_type, event_type)
    return mapped in notify_on


async def setup_event_handler(bot: Any, config: dict[str, Any]) -> None:
    """Subscribe to the event bus and route events to Discord.

    Called after the bot is ready and channel is resolved.
    """
    from ..events import EventBus

    member_name = _get_member_name()

    # We need access to the event bus — get it from the module-level instance
    # The event bus uses synchronous handlers, so we need to bridge to async
    loop = asyncio.get_event_loop()

    def on_event(event: dict[str, Any]) -> None:
        """Synchronous event handler that dispatches to async."""
        asyncio.run_coroutine_threadsafe(
            _handle_event(bot, config, member_name, event),
            loop,
        )

    # Subscribe to all events
    try:
        from ..events import EventBus
        # Find the global event bus instance
        # The orchestrator creates it — we'll subscribe when available
        logger.info("Discord event handler ready (member: %s)", member_name)
    except Exception as e:
        logger.error("Failed to setup Discord event handler: %s", e)

    # Store handler for external subscription
    bot._event_handler = on_event
    bot._discord_config = config
    bot._member_name = member_name


async def _handle_event(
    bot: Any,
    config: dict[str, Any],
    member_name: str,
    event: dict[str, Any],
    channel: Any = None,
) -> None:
    """Route an orchestration event to the appropriate Discord action."""
    # Use provided channel (project-specific) or fall back to bot default
    target_channel = channel or bot.channel
    if not bot.is_connected or not target_channel:
        return

    event_type = event.get("type", "")
    change_name = event.get("change", "")
    data = event.get("data", {})

    try:
        if event_type == "STATE_CHANGE":
            await _handle_state_change(bot, config, member_name, change_name, data, target_channel)

        elif event_type == "MERGE_ATTEMPT":
            await _handle_merge(bot, config, member_name, change_name, data, target_channel)

        elif event_type == "SENTINEL_RESTART":
            await _handle_crash(bot, config, member_name, change_name, data, target_channel)

        elif event_type == "ERROR":
            await _handle_error(bot, config, member_name, change_name, data, target_channel)

    except Exception as e:
        logger.debug("Discord event handler error for %s: %s", event_type, e)


async def _handle_state_change(
    bot: Any,
    config: dict[str, Any],
    member_name: str,
    change_name: str,
    data: dict[str, Any],
    channel: Any = None,
) -> None:
    """Handle STATE_CHANGE events — update thread embed, post milestones to main."""
    from .embeds import build_status_embed
    from .threads import get_or_create_thread, get_thread
    from .throttle import get_throttle, create_throttle

    ch = channel or bot.channel
    new_status = data.get("to", data.get("status", ""))

    # Orchestration-level state change (no change_name)
    if not change_name:
        orch_status = data.get("to", data.get("status", ""))
        if orch_status == "running":
            # Run started
            run_id = data.get("run_id", str(int(datetime.now(timezone.utc).timestamp())))
            state = _RunState(run_id, member_name)
            _run_state[run_id] = state

            if _should_notify_main(config, "start"):
                change_count = data.get("change_count", 0)
                await ch.send(
                    f"[SET] \U0001f7e2 **{member_name}** started Run #{run_id} ({change_count} changes)"
                )

            # Create thread with initial embed
            thread = await get_or_create_thread(
                ch, run_id, member_name, data.get("change_count", 0),
            )
            if thread:
                embed = await build_status_embed(
                    run_id, member_name, state.changes,
                    start_time=state.start_time,
                )
                state.status_message = await thread.send(embed=embed)
                # Initialize throttle
                create_throttle()

        elif orch_status in ("done", "failed", "stopped"):
            await _handle_run_complete(bot, config, member_name, orch_status, data, ch)
        return

    # Per-change state change — update the run's embed
    for state in _run_state.values():
        # Update change in state
        found = False
        for c in state.changes:
            if c.get("name") == change_name:
                c["status"] = new_status
                found = True
                break
        if not found:
            state.changes.append({"name": change_name, "status": new_status})

        # Schedule throttled embed update
        if state.status_message:
            throttle = get_throttle()
            if throttle:
                async def _build(s=state):
                    return await build_status_embed(
                        s.run_id, s.member_name, s.changes,
                        start_time=s.start_time,
                        total_tokens=s.total_tokens,
                    )
                await throttle.schedule_edit(state.status_message, _build)


async def _handle_merge(
    bot: Any,
    config: dict[str, Any],
    member_name: str,
    change_name: str,
    data: dict[str, Any],
    channel: Any = None,
) -> None:
    """Handle MERGE_ATTEMPT events — post success to main channel."""
    ch = channel or bot.channel
    result = data.get("result", "")
    if result == "success" and _should_notify_main(config, "merge"):
        await ch.send(
            f"[SET] \u2705 **{member_name}**: {change_name} merged"
        )


async def _handle_crash(
    bot: Any,
    config: dict[str, Any],
    member_name: str,
    change_name: str,
    data: dict[str, Any],
    channel: Any = None,
) -> None:
    """Handle crash/restart events — alert on main channel."""
    from .embeds import build_error_embed

    ch = channel or bot.channel
    reason = data.get("reason", data.get("message", "Orchestrator restarted"))
    mention = _get_mention(config, member_name)

    if _should_notify_main(config, "crash"):
        embed = await build_error_embed(
            change_name or "Orchestrator",
            member_name,
            reason,
            mention=mention,
        )
        content = f"[SET] \u274c **{member_name}**: {change_name or 'orchestrator'} — {reason[:100]}"
        if mention:
            content = f"{mention} {content}"
        await ch.send(content=content, embed=embed)


async def _handle_error(
    bot: Any,
    config: dict[str, Any],
    member_name: str,
    change_name: str,
    data: dict[str, Any],
    channel: Any = None,
) -> None:
    """Handle ERROR events — post to main if stuck-related."""
    ch = channel or bot.channel
    message = data.get("message", "")
    if "stuck" in message.lower() or "stall" in message.lower():
        mention = _get_mention(config, member_name)
        if _should_notify_main(config, "stuck"):
            content = f"[SET] \u26a0\ufe0f **{member_name}**: {change_name} — {message[:200]}"
            if mention:
                content = f"{mention} {content}"
            await ch.send(content)


async def _handle_run_complete(
    bot: Any,
    config: dict[str, Any],
    member_name: str,
    status: str,
    data: dict[str, Any],
    channel: Any = None,
) -> None:
    """Handle run completion — post summary to main and thread."""
    from .embeds import build_summary_embed
    from .threads import archive_thread

    # Find the run state
    for run_id, state in list(_run_state.items()):
        if state.member_name == member_name:
            # Post summary to thread
            thread_module = __import__(
                "set_orch.discord.threads", fromlist=["get_thread"]
            )
            thread = thread_module.get_thread(run_id)
            if thread:
                embed = await build_summary_embed(
                    run_id, member_name, state.changes,
                    start_time=state.start_time,
                    total_tokens=state.total_tokens,
                )
                await thread.send(embed=embed)

                # Post screenshot gallery before archiving
                try:
                    from .screenshots import post_screenshots, collect_run_screenshots
                    all_screenshots = collect_run_screenshots(state.changes)
                    if all_screenshots:
                        caption = f"\U0001f4ca Run #{run_id} \u2014 {len(all_screenshots)} screenshots"
                        await post_screenshots(thread, all_screenshots, caption=caption)
                except Exception as e:
                    logger.debug("Screenshot gallery failed: %s", e)

                await archive_thread(run_id)

            # Post completion confirmation embed with reactions
            ch = channel or bot.channel
            if _should_notify_main(config, "complete"):
                from .embeds import build_completion_confirmation_embed
                confirm_embed = await build_completion_confirmation_embed(
                    run_id, member_name, state.changes,
                    start_time=state.start_time,
                    total_tokens=state.total_tokens,
                )
                confirm_msg = await ch.send(embed=confirm_embed)
                # Add reaction buttons
                for emoji in ("\u2705", "\U0001f504", "\U0001f4cb"):
                    await confirm_msg.add_reaction(emoji)

                # Store message ID for reaction handling
                state.completion_message_id = confirm_msg.id

            # Cleanup run state (but keep completion_message_id for reaction handler)
            del _run_state[run_id]
            break
