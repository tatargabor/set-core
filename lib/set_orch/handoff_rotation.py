"""Handoff rotation for resumed `-p` chat sessions (set-claude-handoff, specs/auto-clear).

A ChatSession run is `claude -p --resume <sid>` per message: the live context IS the resumed
transcript, and it grows across messages — at the auto-compact window it gets compacted
silently, which is the loss this prevents. Rotation replaces that unmeasured boundary with a
measured one:

    usage of the last run >= threshold   (a completed run is exactly "turn ended")
      -> one more resumed run writes the handoff (/handoff conventions, project profile)
      -> wait for THIS run's marker: .set/handoff/.written-<session8>
         (dropped by the project's write-time gate — a handoff that failed the content
          gate never arms a rotation; no marker = no rotation, loudly)
      -> drop the resume lineage (new_session) and prepend a load instruction to the
         next message

There are no keystrokes on this plane: a `-p` process takes one prompt per run, so the
"clear" is dropping the resume, and the handoff is what crosses the process boundary.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

THRESHOLD_DEFAULT = 500_000
THRESHOLD_ENV = "SET_HANDOFF_ROTATE_THRESHOLD"
MARKER_WAIT_TIMEOUT_S = 180.0
MARKER_POLL_S = 1.0


def rotate_threshold() -> int:
    """Rotation threshold in tokens; env override for pilots, default is the
    consumer-decided soft limit (500 000)."""
    import os

    raw = os.environ.get(THRESHOLD_ENV, "")
    try:
        return int(raw) if raw else THRESHOLD_DEFAULT
    except ValueError:
        return THRESHOLD_DEFAULT


def usage_total(usage: dict) -> int:
    """Live context size from a stream-json result event's usage — the documented
    identity (input + cache_creation + cache_read; cache_read dominates)."""
    if not usage:
        return 0
    return (
        (usage.get("input_tokens") or 0)
        + (usage.get("cache_creation_input_tokens") or 0)
        + (usage.get("cache_read_input_tokens") or 0)
    )


def session8(session_id: str | None) -> str:
    return "".join(c for c in (session_id or "") if c.isalnum())[:8] or "ismeretlen"


def marker_path(project_path: Path, sid8: str) -> Path:
    return Path(project_path) / ".set" / "handoff" / f".written-{sid8}"


def read_handoff_from_marker(path: Path) -> str | None:
    """The marker's second field: the handoff file name this session armed with."""
    try:
        parts = path.read_text(encoding="utf-8").split()
    except OSError:
        return None
    return parts[1] if len(parts) >= 2 else None


async def wait_for_marker(path: Path, timeout_s: float = MARKER_WAIT_TIMEOUT_S,
                          poll_s: float = MARKER_POLL_S) -> bool:
    """Bounded wait for the armed marker. False = the handoff never arrived: the caller
    must NOT rotate silently — losing the thread is the failure the protocol exists to
    prevent."""
    waited = 0.0
    while waited < timeout_s:
        if path.is_file():
            return True
        await asyncio.sleep(poll_s)
        waited += poll_s
    return False
