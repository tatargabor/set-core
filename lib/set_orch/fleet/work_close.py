"""When a forgotten WORK agent is closed — fleet-work-agent-done, the safety net.

An agent another agent started for one piece of work is meant to end itself with
`set-fleet-mandate done`. This module decides when one that did not is closed
anyway: its mandate is an open `work` mandate with a requester, the operator has
not typed into it since its start, it is not in the middle of something, and its
last movement is measured and older than the work bound (default 2 hours, local
config `fleet_idle_close_work_hours`).

Every input that is not measured keeps the agent. A forgotten agent left running
costs a seat and the context re-reads of each wake; an agent stopped mid-work
costs the work.

Pure: the decision takes a listing row and the clock. The sweep that acts on it
lives with the desk sweep in `api/fleet_work.py`.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple

from .. import local_config

logger = logging.getLogger(__name__)

CONFIG_WORK_HOURS = "fleet_idle_close_work_hours"
DEFAULT_WORK_HOURS = 2.0

#: Human input this long after the mandate was recorded is the OPERATOR, not the
#: brief: the brief is the first turn and lands within seconds of the start.
BRIEF_GRACE_SECONDS = 120.0

STOP = "stop"
KEEP = "keep"

#: Attention classes in which the agent is doing something or asking a person.
_ACTIVE_ATTENTION = ("working", "prompt", "unmeasured")


def work_bound_seconds() -> float:
    raw = local_config.get(CONFIG_WORK_HOURS)
    if raw is None:
        return DEFAULT_WORK_HOURS * 3600.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"local config {CONFIG_WORK_HOURS}={raw!r} is not a number of hours")
    if value <= 0:
        raise ValueError(f"local config {CONFIG_WORK_HOURS}={raw!r} must be positive")
    return value * 3600.0


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def is_work_agent(row: Dict[str, Any]) -> bool:
    """An open `work` mandate with a requester, on an agent the framework holds."""
    held = row.get("mandate") or {}
    return (
        held.get("kind") == "work"
        and bool(held.get("requested_by"))
        and not held.get("ended")
        and row.get("population") == "started-here"
        and bool(row.get("terminal_label"))
    )


def decision(row: Dict[str, Any], *, bound: float, now: Optional[float] = None) -> Tuple[str, str]:
    """(STOP|KEEP, why) for one listing row. Only a work agent can be stopped here."""
    if not is_work_agent(row):
        return KEEP, "not-a-work-agent"
    now = time.time() if now is None else now
    held = row["mandate"]
    declared_at = _number(held.get("declared_at"))
    if declared_at is None:
        return KEEP, "start-unmeasured"
    human_age = _number(row.get("last_human_input_seconds"))
    if human_age is not None and (now - human_age) > declared_at + BRIEF_GRACE_SECONDS:
        # The operator typed into it after the brief: it is their window now.
        return KEEP, "operator-took-over"
    if row.get("tool") or row.get("runtime_status") == "busy":
        return KEEP, "busy"
    # Only a QUIET agent can be forgotten. `asking` has a question in front of a
    # person (an AskUserQuestion nobody answered is not idleness), `working` and
    # `waiting` are mid-something, and `unknown` is unmeasured.
    state = row.get("state")
    if state != "quiet":
        return KEEP, f"state-{state or 'unmeasured'}"
    attention = row.get("attention")
    if attention is None or attention in _ACTIVE_ATTENTION:
        return KEEP, f"attention-{attention or 'unmeasured'}"
    moved = _number(row.get("last_movement_seconds"))
    if moved is None:
        return KEEP, "movement-unmeasured"
    if moved <= bound:
        return KEEP, "recent-movement"
    return STOP, "work-idle"
