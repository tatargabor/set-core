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

    logger.info("Notification [%s]: %s — %s", urgency, title, body)


def _send_email(
    title: str, body: str, urgency: str, project_name: str
) -> None:
    """Send email via Resend API. Requires RESEND_API_KEY and RESEND_TO in env.

    Migrated from: lib/orchestration/email.sh send_email()
    """
    api_key = os.environ.get("RESEND_API_KEY")
    to_addr = os.environ.get("RESEND_TO")
    from_addr = os.environ.get("RESEND_FROM", "wt-tools@resend.dev")

    if not api_key or not to_addr:
        return

    prefix = "[CRITICAL]" if urgency == "critical" else "[info]"
    subject = f"{prefix} {title} — {project_name}"
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
