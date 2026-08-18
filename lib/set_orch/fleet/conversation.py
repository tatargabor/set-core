"""The raw conversation — what is being said inside a session.

Task 6.2 (a log-tail endpoint, and the full parse that only happens when a log
is opened) and design §5.8, which chose the raw conversation over the activity
timeline: the timeline answers where the time went, which is not the question
someone opens a tile to ask.

⚠ **Nothing here is persisted, cached or logged.** The confidentiality boundary
in CLAUDE.md is a persistence boundary, not a reading one — the framework may
display a project's data at runtime, and must write none of it down. So this
module reads on request and returns; diagnostics name the file and the failure
kind, never a line of content.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: How far back to read when a log is opened. Larger than the listing tail in
#: `state.py` — this path runs once, for one agent, because someone asked.
OPEN_TAIL_BYTES = 2 * 1024 * 1024

#: Entry kinds that carry no conversation and would only add noise.
SKIPPED_TYPES = {"file-history-snapshot", "queue-operation", "last-prompt", "ai-title", "mode"}


@dataclass
class Turn:
    """One entry of the conversation, flattened for display."""

    role: str
    timestamp: Optional[str] = None
    text: str = ""
    thinking: str = ""
    tools: List[Dict[str, Any]] = field(default_factory=list)
    results: int = 0
    #: True for entries produced by a sub-agent this session spawned.
    sidechain: bool = False


def _blocks(entry: dict) -> List[dict]:
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def _tail_lines(path: str, limit: int) -> Optional[List[str]]:
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > limit:
                fh.seek(size - limit)
                fh.readline()
            raw = fh.read()
    except OSError as exc:
        logger.warning("fleet conversation: cannot read %s: %s", os.path.basename(path), exc)
        return None
    return raw.decode("utf-8", errors="replace").splitlines()


def read_conversation(
    session_log: Optional[str],
    *,
    limit: int = 60,
    include_sidechain: bool = False,
) -> Dict[str, Any]:
    """The last `limit` conversational turns of a session.

    Returns a dict with `turns` and, when something prevented an answer, a
    `problem` naming what. An empty `turns` with no `problem` means the log was
    read and holds no conversation — which is a different fact from a log that
    could not be read, and the surface must be able to tell them apart.
    """
    if not session_log:
        return {"turns": [], "problem": "no session log is bound to this agent"}
    if not os.path.exists(session_log):
        return {"turns": [], "problem": "the bound session log does not exist"}

    lines = _tail_lines(session_log, OPEN_TAIL_BYTES)
    if lines is None:
        return {"turns": [], "problem": "the session log could not be read"}

    turns: List[Turn] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        kind = entry.get("type")
        if kind in SKIPPED_TYPES:
            continue
        sidechain = bool(entry.get("isSidechain"))
        if sidechain and not include_sidechain:
            continue

        text_parts, thinking_parts, tools, results = [], [], [], 0
        for block in _blocks(entry):
            btype = block.get("type")
            if btype == "text":
                value = block.get("text")
                if value:
                    text_parts.append(str(value))
            elif btype == "thinking":
                # ⚠ This branch is correct and will produce nothing today, and the
                # note exists so the next reader does not "fix" a parser that is
                # already right. MEASURED 2026-08-18 over the six most recent
                # session logs: 400 thinking blocks, ALL with `thinking` set to
                # the empty string, every one carrying exactly
                # ('signature', 'thinking', 'type') — the runtime persists the
                # signature and not the text. So a surface that counts thinking
                # from the DATA correctly shows none; one that counts from the
                # block's presence would announce content that is not there,
                # which is the false-value class. If this is ever to mean
                # something, it changes at the producer, not here.
                value = block.get("thinking") or block.get("text")
                if value:
                    thinking_parts.append(str(value))
            elif btype == "tool_use":
                tools.append({"name": block.get("name"), "id": block.get("id")})
            elif btype == "tool_result":
                results += 1

        if not (text_parts or thinking_parts or tools or results):
            continue

        turns.append(Turn(
            role=str(kind or "unknown"),
            timestamp=entry.get("timestamp"),
            text="\n".join(text_parts),
            thinking="\n".join(thinking_parts),
            tools=tools,
            results=results,
            sidechain=sidechain,
        ))

    tail = turns[-limit:] if limit and limit > 0 else turns
    return {
        "turns": [t.__dict__ for t in tail],
        # Counted from what was read, never from what we expected to read.
        "total_read": len(turns),
        "truncated": len(turns) > len(tail),
    }
