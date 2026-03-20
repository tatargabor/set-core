"""Multi-channel notification dispatch for orchestration engine.

Migrated from: lib/orchestration/state.sh send_notification() L365-399

Supports desktop (notify-send) and email (Resend API) channels.
"""

import json
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def send_notification(
    title: str,
    body: str,
    urgency: str = "normal",
    channels: str = "desktop",
    project_name: str = "",
) -> None:
    """Dispatch notification to configured channels.

    Migrated from: state.sh send_notification() L365-399

    Args:
        title: Notification title.
        body: Notification body.
        urgency: "normal" or "critical".
        channels: Channel string — "desktop", "email", "desktop,email", or "none".
        project_name: Project name for email context.
    """
    if channels == "none":
        logger.info("Notification [%s]: %s — %s", urgency, title, body)
        return

    if not project_name:
        project_name = Path.cwd().name

    # Desktop channel: notify-send
    if "desktop" in channels and shutil.which("notify-send"):
        try:
            subprocess.run(
                ["notify-send", "-u", urgency, title, body],
                capture_output=True,
                timeout=5,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass

    # Email channel: Resend API
    if "email" in channels:
        _send_email(title, body, urgency, project_name)

    # Discord channel
    if "discord" in channels:
        _send_discord_sync(title, body, urgency, project_name)

    logger.info("Notification [%s]: %s — %s", urgency, title, body)


def send_summary_email(
    state_file: str,
    coverage_summary: str = "",
    project_name: str = "",
) -> None:
    """Send HTML summary email with orchestration state and coverage results.

    Args:
        state_file: Path to orchestration state file.
        coverage_summary: Coverage check summary string.
        project_name: Project name for email context.
    """
    api_key = os.environ.get("RESEND_API_KEY")
    to_addr = os.environ.get("RESEND_TO")
    if not api_key or not to_addr:
        return

    from .state import load_state

    state = load_state(state_file)
    if not project_name:
        project_name = Path.cwd().name

    total = len(state.changes)
    merged = sum(1 for c in state.changes if c.status == "merged")
    failed = sum(1 for c in state.changes if c.status == "failed")
    blocked = sum(1 for c in state.changes if c.status == "merge-blocked")
    total_tokens = sum(c.tokens_used for c in state.changes)
    active_secs = state.extras.get("active_seconds", 0)

    status_emoji = "done" if state.status == "done" else state.status
    subject = f"[orch] {project_name} — {status_emoji} ({merged}/{total} merged)"

    # Build HTML body
    rows = ""
    for c in state.changes:
        rows += (
            f"<tr><td>{c.name}</td><td>{c.status}</td>"
            f"<td>{c.tokens_used:,}</td></tr>"
        )

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = (
        f"<h2>Orchestration Summary — {project_name}</h2>"
        f"<p><b>Status:</b> {state.status} | <b>Time:</b> {active_secs // 60}m {active_secs % 60}s | "
        f"<b>Tokens:</b> {total_tokens:,}</p>"
        f"<p><b>Changes:</b> {merged} merged, {failed} failed, {blocked} blocked / {total} total</p>"
        f"<table border='1' cellpadding='4' cellspacing='0'>"
        f"<tr><th>Change</th><th>Status</th><th>Tokens</th></tr>"
        f"{rows}</table>"
    )

    if coverage_summary:
        html += f"<h3>Coverage</h3><pre>{coverage_summary}</pre>"

    html += (
        f'<p style="color:#888;font-size:12px;">'
        f"Generated at {ts} by set-core orchestrator</p>"
    )

    _send_email(subject, html, "normal", project_name, html_body=html)
    logger.info("Summary email sent for %s", project_name)


def _send_email(
    title: str, body: str, urgency: str, project_name: str,
    html_body: str = "",
) -> None:
    """Send email via Resend API. Requires RESEND_API_KEY and RESEND_TO in env.

    Migrated from: lib/orchestration/email.sh send_email()
    """
    api_key = os.environ.get("RESEND_API_KEY")
    to_addr = os.environ.get("RESEND_TO")
    from_addr = os.environ.get("RESEND_FROM", "set-core@resend.dev")

    if not api_key or not to_addr:
        return

    prefix = "[CRITICAL]" if urgency == "critical" else "[info]"
    subject = f"{prefix} {title} — {project_name}"
    if not html_body:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        html_body = (
            f"<h3>{title}</h3>"
            f"<p>{body}</p>"
            f'<p style="color:#888;font-size:12px;">'
            f"{ts} | {project_name} | {urgency}</p>"
        )

    try:
        # Use curl subprocess to avoid requests dependency
        subprocess.run(
            [
                "curl", "-s", "-X", "POST",
                "https://api.resend.com/emails",
                "-H", f"Authorization: Bearer {api_key}",
                "-H", "Content-Type: application/json",
                "-d", json.dumps({
                    "from": from_addr,
                    "to": [to_addr],
                    "subject": subject,
                    "html": html_body,
                }),
            ],
            capture_output=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.warning("Email notification failed: %s", e)


def _send_discord_sync(
    title: str, body: str, urgency: str, project_name: str,
) -> None:
    """Send notification via Discord bot. Bridges sync caller to async bot."""
    try:
        from .discord import get_bot
    except ImportError:
        logger.debug("Discord module not available")
        return

    bot = get_bot()
    if not bot or not bot.is_connected or not bot.channel:
        logger.debug("Discord bot not connected — skipping notification")
        return

    import asyncio

    async def _send():
        try:
            import discord
            color = 0x2ECC71 if urgency == "normal" else 0xE74C3C
            embed = discord.Embed(
                title=title,
                description=body[:2000],
                color=color,
            )
            embed.set_footer(text=project_name)

            mention = ""
            if urgency == "critical" and hasattr(bot, "_discord_config"):
                from .discord.events import _get_mention
                mention = _get_mention(bot._discord_config, getattr(bot, "_member_name", ""))

            content = f"{mention} " if mention else None
            await bot.channel.send(content=content, embed=embed)
        except Exception as e:
            logger.debug("Discord notification failed: %s", e)

    try:
        loop = asyncio.get_running_loop()
        asyncio.run_coroutine_threadsafe(_send(), loop)
    except RuntimeError:
        # No running loop — can't send
        logger.debug("No asyncio loop — Discord notification skipped")
