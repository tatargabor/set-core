"""What an agent is doing — read from its session log, never from a status field.

Tasks 3.1/3.2/3.3/3.6 of the `fleet-view` change.

Why the log and not the record: the runtime writes a `status` into each session
record, and it looks authoritative. Measured 2026-08-18 across 23 live sessions,
the age of that field had a **median of 11 hours and a maximum of 83**, with 7
sessions over a day stale. It is a declaration about a moment that has passed.
The log's mtime is the moment itself.

Working is defined structurally rather than by a label: a `tool_use` block in
the tail with no matching `tool_result` means a call is outstanding, so the
session is mid-turn. Everything else is *unknown*, never *idle* — an agent whose
state cannot be determined must not be reported as resting, because that is the
reading someone acts on by leaving it alone.

The list path costs one `stat` plus a bounded tail per agent. No full parse.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

#: How much of the log's end to read for the outstanding-call scan. A turn's
#: worth of entries is far smaller than this; the bound is what keeps listing
#: every agent from reading every log in full (task 3.6).
TAIL_BYTES = 256 * 1024

#: Sentinel for "this state could not be determined". Never "idle".
UNKNOWN = "unknown"
WORKING = "working"
QUIET = "quiet"


@dataclass
class AgentState:
    """The measured state of one agent.

    `quiet` means the log was read and no call is outstanding — the agent
    finished its turn. It is deliberately not called *idle*: idle claims the
    agent has nothing to do, which this cannot know.
    """

    state: str = UNKNOWN
    #: Seconds since the session log last changed, or None when unmeasurable.
    last_movement_age: Optional[float] = None
    #: The tool whose call is outstanding, when the state is `working`.
    tool: Optional[str] = None
    #: How long that call has been outstanding, in seconds.
    tool_elapsed: Optional[float] = None
    #: Why the state is unknown, when it is. Present for exactly that case.
    reason: Optional[str] = None
    #: Tools outstanding beyond the first, if any.
    other_tools: List[str] = field(default_factory=list)


def _tail(path: str, limit: int = TAIL_BYTES) -> Optional[List[str]]:
    """The last `limit` bytes of a file, as whole lines.

    Returns None when the file cannot be read at all — which is a different
    answer from "the file is empty", and the caller must not collapse the two.
    """
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > limit:
                fh.seek(size - limit)
                fh.readline()  # discard the partial line the seek landed inside
            raw = fh.read()
    except OSError as exc:
        logger.debug("fleet state: cannot tail %s: %s", path, exc)
        return None
    text = raw.decode("utf-8", errors="replace")
    return text.splitlines()


def _outstanding_calls(lines: List[str]) -> tuple[Dict[str, dict], bool]:
    """Tool calls in the tail with no matching result.

    Returns (outstanding by tool_use id, saw_any_entry).

    Sidechain entries are skipped: a session's own task children are out of this
    capability's scope, and counting their calls would report the parent as
    working on a tool it never invoked.
    """
    opened: Dict[str, dict] = {}
    closed: Set[str] = set()
    saw = False

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
        saw = True
        if entry.get("isSidechain"):
            continue
        content = (entry.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "tool_use":
                call_id = block.get("id")
                if call_id:
                    opened[call_id] = {
                        "name": block.get("name"),
                        "timestamp": entry.get("timestamp"),
                    }
            elif kind == "tool_result":
                result_for = block.get("tool_use_id")
                if result_for:
                    closed.add(result_for)

    return {cid: meta for cid, meta in opened.items() if cid not in closed}, saw


def _age_seconds(iso_timestamp: Optional[str], now: Optional[float] = None) -> Optional[float]:
    if not iso_timestamp:
        return None
    try:
        from datetime import datetime

        parsed = datetime.fromisoformat(str(iso_timestamp).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    reference = now if now is not None else time.time()
    return max(0.0, reference - parsed.timestamp())


def read_state(session_log: Optional[str], *, now: Optional[float] = None) -> AgentState:
    """Measure one agent's state from its session log.

    Every path that cannot reach an answer returns `unknown` **with a reason**.
    A missing key and an empty value are distinguished deliberately: a log that
    exists and holds no parsable entry is not the same as a log that is absent,
    and neither is the same as an agent that has finished its turn.
    """
    if session_log is None:
        return AgentState(state=UNKNOWN, reason="no session log is bound to this agent")
    if not os.path.exists(session_log):
        return AgentState(state=UNKNOWN, reason="the bound session log does not exist")

    reference = now if now is not None else time.time()
    try:
        movement = max(0.0, reference - os.path.getmtime(session_log))
    except OSError as exc:
        logger.warning("fleet state: cannot stat %s: %s", session_log, exc)
        return AgentState(state=UNKNOWN, reason="the session log could not be stat'ed")

    lines = _tail(session_log)
    if lines is None:
        return AgentState(
            state=UNKNOWN,
            last_movement_age=movement,
            reason="the session log could not be read",
        )

    outstanding, saw_entry = _outstanding_calls(lines)
    if not saw_entry:
        return AgentState(
            state=UNKNOWN,
            last_movement_age=movement,
            reason="the session log holds no parsable entry",
        )

    if not outstanding:
        return AgentState(state=QUIET, last_movement_age=movement)

    ordered = sorted(
        outstanding.values(),
        key=lambda meta: meta.get("timestamp") or "",
    )
    first = ordered[0]
    return AgentState(
        state=WORKING,
        last_movement_age=movement,
        tool=first.get("name"),
        tool_elapsed=_age_seconds(first.get("timestamp"), reference),
        other_tools=[m.get("name") for m in ordered[1:] if m.get("name")],
    )
