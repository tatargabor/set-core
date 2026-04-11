"""Python-native sentinel inbox reader.

The old Claude sentinel used `set-sentinel-inbox check` CLI every poll
to detect user messages. The daemon reads the same inbox.jsonl file
directly — no subprocess cost, same file format, same cursor semantics.

Inbox messages trigger daemon actions:
- "stop" / "ne restartolj" → graceful shutdown
- "status" → daemon writes current status.json to a response file
- other → log + (Phase 2: trigger ephemeral Claude for interpretation)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

INBOX_FILE = "inbox.jsonl"
INBOX_CURSOR_FILE = "inbox.cursor"


@dataclass
class InboxMessage:
    sender: str
    content: str
    timestamp: str


def _inbox_path(project_path: str | Path) -> Path:
    return Path(project_path) / ".set" / "sentinel" / INBOX_FILE


def _cursor_path(project_path: str | Path) -> Path:
    return Path(project_path) / ".set" / "sentinel" / INBOX_CURSOR_FILE


def read_new_messages(project_path: str | Path) -> list[InboxMessage]:
    """Read new messages since last cursor. Returns a list of InboxMessage.

    Updates the cursor file on success so the next call returns only newer
    messages. If the inbox file doesn't exist, returns an empty list.
    """
    ip = _inbox_path(project_path)
    cp = _cursor_path(project_path)
    if not ip.is_file():
        return []

    cursor = 0
    if cp.is_file():
        try:
            cursor = int(cp.read_text().strip() or "0")
        except (ValueError, OSError):
            cursor = 0

    try:
        file_size = ip.stat().st_size
    except OSError:
        return []
    if file_size <= cursor:
        return []

    messages: list[InboxMessage] = []
    new_cursor = cursor
    try:
        with open(ip, "r") as f:
            f.seek(cursor)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    messages.append(InboxMessage(
                        sender=str(obj.get("from", "?")),
                        content=str(obj.get("content", "")),
                        timestamp=str(obj.get("timestamp", "")),
                    ))
                except json.JSONDecodeError:
                    continue
            new_cursor = f.tell()
    except OSError as exc:
        logger.warning("Could not read inbox at %s: %s", ip, exc)
        return []

    try:
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(str(new_cursor))
    except OSError as exc:
        logger.warning("Could not write inbox cursor at %s: %s", cp, exc)

    return messages


def classify_message(msg: InboxMessage) -> str:
    """Classify an inbox message into a daemon action.

    Returns one of:
        "stop"   — graceful shutdown (stop + ne restartolj + halt)
        "status" — status request
        "other"  — unknown (log + defer to Phase 2 classifier)
    """
    text = (msg.content or "").lower().strip()
    if not text:
        return "other"
    stop_patterns = ("stop", "halt", "shutdown", "ne restartolj", "allj le", "állj le")
    if any(p in text for p in stop_patterns):
        return "stop"
    status_patterns = ("status", "állapot", "allapot", "jelents")
    if any(p in text for p in status_patterns):
        return "status"
    return "other"
