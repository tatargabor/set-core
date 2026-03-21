"""Discord embed builders for orchestration status, summaries, and errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Status icons for change states
STATUS_ICONS = {
    "pending": "\u23f3",       # hourglass
    "queued": "\u23f3",
    "running": "\U0001f527",   # wrench
    "implementing": "\U0001f527",
    "verifying": "\U0001f50d", # magnifying glass
    "merging": "\U0001f500",   # shuffle
    "merged": "\u2705",        # checkmark
    "done": "\u2705",
    "completed": "\u2705",
    "skip_merged": "\u2705",
    "failed": "\u274c",        # cross
    "verify-failed": "\u274c",
    "merge-blocked": "\U0001f6ab",  # no entry
    "blocked": "\U0001f6ab",
    "stalled": "\u26a0\ufe0f",      # warning
    "stopped": "\u23f9\ufe0f",      # stop
    "skipped": "\u23ed\ufe0f",      # skip
}

# Embed colors
COLOR_ACTIVE = 0x3498DB   # blue
COLOR_SUCCESS = 0x2ECC71  # green
COLOR_ERROR = 0xE74C3C    # red
COLOR_WARNING = 0xF39C12  # orange


def _progress_bar(done: int, total: int, width: int = 8) -> str:
    """Generate a text progress bar like '████░░░░ 4/8'."""
    if total == 0:
        return f"{'░' * width} 0/0"
    filled = round(done / total * width)
    bar = "\u2588" * filled + "\u2591" * (width - filled)
    return f"{bar} {done}/{total}"


async def build_status_embed(
    run_id: str,
    member_name: str,
    changes: list[dict[str, Any]],
    start_time: datetime | None = None,
    total_tokens: int = 0,
    agent_count: int = 0,
    status: str = "running",
) -> Any:
    """Build the live-updating status embed for a run thread.

    Shows per-change rows with status icons and progress bars.
    """
    import discord

    now = datetime.now(timezone.utc)
    elapsed = ""
    if start_time:
        delta = now - start_time
        mins = int(delta.total_seconds() // 60)
        elapsed = f"{mins}min"

    # Determine embed color
    if status in ("done", "completed"):
        color = COLOR_SUCCESS
    elif status in ("failed", "stopped"):
        color = COLOR_ERROR
    else:
        color = COLOR_ACTIVE

    embed = discord.Embed(
        title=f"[SET] Run #{run_id} — {member_name}",
        color=color,
        timestamp=now,
    )

    # Per-change rows
    lines = []
    merged_count = 0
    total_count = len(changes)

    for c in changes:
        name = c.get("name", "?")
        c_status = c.get("status", "pending")
        icon = STATUS_ICONS.get(c_status, "\u2753")  # question mark fallback

        if c_status in ("merged", "done", "completed", "skip_merged"):
            merged_count += 1

        # Task progress if available
        tasks_done = c.get("tasks_done", 0)
        tasks_total = c.get("tasks_total", 0)
        if tasks_total > 0 and c_status in ("running", "implementing", "verifying"):
            progress = _progress_bar(tasks_done, tasks_total)
            lines.append(f"{icon} **{name}** {progress}")
        else:
            lines.append(f"{icon} **{name}** — {c_status}")

    if lines:
        # Discord embed field value max 1024 chars
        value = "\n".join(lines)
        if len(value) > 1024:
            value = value[:1020] + "\n..."
        embed.add_field(name="Changes", value=value, inline=False)

    # Footer with stats
    footer_parts = []
    if agent_count:
        footer_parts.append(f"Agents: {agent_count}")
    if total_tokens:
        if total_tokens >= 1_000_000:
            footer_parts.append(f"Tokens: {total_tokens / 1_000_000:.1f}M")
        else:
            footer_parts.append(f"Tokens: {total_tokens:,}")
    if elapsed:
        footer_parts.append(f"Elapsed: {elapsed}")
    footer_parts.append(f"{merged_count}/{total_count} merged")

    embed.set_footer(text=" | ".join(footer_parts))

    return embed


async def build_summary_embed(
    run_id: str,
    member_name: str,
    changes: list[dict[str, Any]],
    start_time: datetime | None = None,
    total_tokens: int = 0,
    duration_seconds: int = 0,
) -> Any:
    """Build the final summary embed when a run completes."""
    import discord

    merged = sum(1 for c in changes if c.get("status") in ("merged", "done", "completed", "skip_merged"))
    failed = sum(1 for c in changes if c.get("status") in ("failed", "verify-failed"))
    blocked = sum(1 for c in changes if c.get("status") in ("merge-blocked", "blocked"))
    total = len(changes)

    color = COLOR_SUCCESS if failed == 0 and blocked == 0 else COLOR_WARNING

    embed = discord.Embed(
        title=f"[SET] Run #{run_id} Complete — {member_name}",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )

    embed.add_field(
        name="Results",
        value=(
            f"\u2705 **{merged}** merged\n"
            f"\u274c **{failed}** failed\n"
            f"\U0001f6ab **{blocked}** blocked\n"
            f"**{total}** total"
        ),
        inline=True,
    )

    # Duration and tokens
    stats_lines = []
    if duration_seconds:
        mins = duration_seconds // 60
        stats_lines.append(f"\u23f1\ufe0f {mins}min")
    if total_tokens:
        if total_tokens >= 1_000_000:
            stats_lines.append(f"\U0001f4b0 {total_tokens / 1_000_000:.1f}M tokens")
        else:
            stats_lines.append(f"\U0001f4b0 {total_tokens:,} tokens")

    if stats_lines:
        embed.add_field(name="Stats", value="\n".join(stats_lines), inline=True)

    return embed


async def build_completion_confirmation_embed(
    run_id: str,
    member_name: str,
    changes: list[dict[str, Any]],
    start_time: datetime | None = None,
    total_tokens: int = 0,
) -> Any:
    """Build completion confirmation embed with reaction instructions."""
    import discord

    merged = sum(1 for c in changes if c.get("status") in ("merged", "done"))
    failed = sum(1 for c in changes if c.get("status") in ("failed", "verify-failed"))
    total = len(changes)

    color = COLOR_SUCCESS if failed == 0 else COLOR_WARNING
    duration_str = ""
    if start_time:
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        duration_str = f" | {int(elapsed // 60)}min"

    token_str = ""
    if total_tokens >= 1_000_000:
        token_str = f" | {total_tokens / 1_000_000:.1f}M tokens"
    elif total_tokens:
        token_str = f" | {total_tokens:,} tokens"

    embed = discord.Embed(
        title=f"\U0001f3c1 Orchestration Complete — {member_name}",
        description=(
            f"**{merged}/{total}** merged"
            f"{' | **' + str(failed) + '** failed' if failed else ''}"
            f"{duration_str}{token_str}\n\n"
            "React to choose:\n"
            "\u2705 Accept & Stop\n"
            "\U0001f504 Re-run same spec\n"
            "\U0001f4cb New spec"
        ),
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text="Auto-stop in 5 min if no response")
    return embed


async def build_error_embed(
    change_name: str,
    member_name: str,
    reason: str,
    mention: str = "",
) -> Any:
    """Build an error/alert embed for stuck or crashed agents."""
    import discord

    embed = discord.Embed(
        title=f"[SET] \u274c {change_name}",
        description=reason[:2000],
        color=COLOR_ERROR,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=member_name)

    return embed
