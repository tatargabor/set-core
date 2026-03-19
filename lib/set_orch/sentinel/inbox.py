"""Lightweight inbox for sentinel — local file-based, no git operations.

Messages are written to the shared sentinel directory by set-web or MCP tools.
The sentinel reads and processes them during its poll loop.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

from set_orch.sentinel.set_dir import ensure_set_dir

INBOX_FILE = "inbox.jsonl"
INBOX_CURSOR_FILE = "inbox.cursor"


def inbox_path(project_path: str) -> str:
    """Return the inbox file path, ensuring directory exists."""
    sentinel_dir = ensure_set_dir(project_path)
    return os.path.join(sentinel_dir, INBOX_FILE)


def check_inbox(project_path: str) -> list[dict]:
    """Read new messages from inbox since last cursor.

    Returns list of message dicts: [{from, content, timestamp}, ...]
    Fast: single file read + cursor comparison, <5ms.
    """
    sentinel_dir = ensure_set_dir(project_path)
    ipath = os.path.join(sentinel_dir, INBOX_FILE)
    cursor_path = os.path.join(sentinel_dir, INBOX_CURSOR_FILE)

    if not os.path.exists(ipath):
        return []

    # Read cursor (byte offset of last read position)
    cursor = 0
    if os.path.exists(cursor_path):
        try:
            with open(cursor_path, "r") as f:
                cursor = int(f.read().strip())
        except (ValueError, OSError):
            cursor = 0

    # Check if there's new data
    file_size = os.path.getsize(ipath)
    if file_size <= cursor:
        return []

    # Read new messages from cursor position
    messages = []
    with open(ipath, "r") as f:
        f.seek(cursor)
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        new_cursor = f.tell()

    # Update cursor
    with open(cursor_path, "w") as f:
        f.write(str(new_cursor))

    return messages


def write_to_inbox(project_path: str, sender: str, content: str) -> dict:
    """Write a message to the sentinel's inbox.

    Used by set-web backend to send messages to the sentinel.
    """
    sentinel_dir = ensure_set_dir(project_path)
    ipath = os.path.join(sentinel_dir, INBOX_FILE)

    msg = {
        "from": sender,
        "content": content,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    line = json.dumps(msg, ensure_ascii=False) + "\n"
    with open(ipath, "a") as f:
        f.write(line)
    return msg
