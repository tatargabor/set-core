from __future__ import annotations

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

    # Discord channel — auto-enable when webhook is configured
    webhook_url = _resolve_webhook_url()
    if "discord" in channels or webhook_url:
        if webhook_url:
            _send_discord_webhook(webhook_url, title, body, urgency, project_name)
        else:
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


_webhook_url_cache: str | None = None
_webhook_url_resolved: bool = False


def _resolve_webhook_url() -> str:
    """Resolve Discord webhook URL from config sources (cached per process).

    Priority: DISCORD_WEBHOOK_URL env var → ~/.config/set-core/discord.json → empty.
    Project-level config (directives) is checked separately in send_notification().
    """
    global _webhook_url_cache, _webhook_url_resolved
    if _webhook_url_resolved:
        return _webhook_url_cache or ""
    _webhook_url_resolved = True

    # 1. Environment variable
    url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if url:
        _webhook_url_cache = url
        return url

    # 2. Global discord.json
    try:
        config_path = Path.home() / ".config" / "set-core" / "discord.json"
        if config_path.is_file():
            data = json.loads(config_path.read_text())
            url = data.get("webhook_url", "")
            if url:
                _webhook_url_cache = url
                return url
    except (OSError, json.JSONDecodeError):
        pass

    _webhook_url_cache = ""
    return ""


def _send_discord_webhook(
    url: str, title: str, body: str, urgency: str, project_name: str,
) -> None:
    """Send Discord notification via webhook POST with embed."""
    colors = {"normal": 0x2ECC71, "critical": 0xE74C3C, "info": 0x3498DB}
    color = colors.get(urgency, 0x2ECC71)

    payload = json.dumps({
        "embeds": [{
            "title": title[:256],
            "description": body[:2000],
            "color": color,
            "footer": {"text": project_name},
        }],
    })

    try:
        subprocess.run(
            [
                "curl", "-s", "-X", "POST", url,
                "-H", "Content-Type: application/json",
                "-d", payload,
            ],
            capture_output=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.warning("Discord webhook failed: %s", e)


def _send_discord_sync(
    title: str, body: str, urgency: str, project_name: str,
) -> None:
    """Send notification via Discord bot (legacy fallback).

    Used when no webhook URL is configured but set-web bot is running.
    """
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
            await bot.channel.send(embed=embed)
        except Exception as e:
            logger.debug("Discord notification failed: %s", e)

    try:
        loop = asyncio.get_running_loop()
        asyncio.run_coroutine_threadsafe(_send(), loop)
    except RuntimeError:
        logger.debug("No asyncio loop — Discord notification skipped")
