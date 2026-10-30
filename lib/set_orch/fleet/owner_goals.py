"""The owner's goals — what the big pieces of work are, and advice on what they should be.

Layer 1 (abstract). Like the owner queue (`owner_queue.py`), the goals are an ordinary
declared status-contract command: `owner-goals` to read, `owner-goals-act` to hand a
verdict back (spec `owner-goals-contract`). The publisher is found by the same
`find_publisher`, under the same `now.publisher` override, and the write goes through the
same one-`--json`-argument shape and the same delivered/refused interpretation.

How the publisher finds or judges goals is the project's business; set-core shows what it
is given and sends the owner's verdicts back.

**Every text field is display-only.** A goal's title, why, serves, progress text, evidence
labels, an advice sentence and its why are the publisher's words. They pass through to the
card and are never logged or stored — log lines here carry ids, counts and classes only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..project_status import StatusResult
from .now import to_epoch
from .owner_queue import ActResult, interpret_write, unread_sources, write_args

logger = logging.getLogger(__name__)

READ_COMMAND = "owner-goals"
WRITE_COMMAND = "owner-goals-act"

#: Verdicts on a goal, and on an advice entry (spec owner-goals-contract).
GOAL_ACTIONS = ("keep", "drop", "rename")
ADVICE_ACTIONS = ("accept", "decline")
ACTIONS = GOAL_ACTIONS + ADVICE_ACTIONS

GOAL_STATUSES = ("proposed", "confirmed")
ADVICE_KINDS = ("add", "drop", "merge", "reorder", "neglected", "other")

__all__ = [
    "READ_COMMAND", "WRITE_COMMAND", "ACTIONS", "GOAL_ACTIONS", "ADVICE_ACTIONS",
    "GoalsRead", "parse_goal", "parse_advice", "parse_goals", "act_payload",
    "write_args", "interpret_write", "ActResult",
]


@dataclass
class GoalsRead:
    measured: bool
    reason: Optional[str] = None
    goals: List[Dict[str, Any]] = field(default_factory=list)
    advice: List[Dict[str, Any]] = field(default_factory=list)
    malformed_goals: int = 0
    malformed_advice: int = 0
    complete: Optional[bool] = None
    synthesized_at: Optional[str] = None
    age_s: Optional[float] = None
    #: The publisher's own sources it could not read this round — display-only names.
    unread_sources: List[str] = field(default_factory=list)


def _text(value: Any) -> Optional[str]:
    """A non-empty display string, or None. Ids may arrive as numbers."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (str, int)) and str(value).strip():
        return str(value)
    return None


def _count(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _progress(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict) or not isinstance(raw.get("text"), str) or not raw["text"].strip():
        return None
    out: Dict[str, Any] = {"text": raw["text"]}
    done, total = _count(raw.get("done")), _count(raw.get("total"))
    if done is not None:
        out["done"] = done
    if total is not None:
        out["total"] = total
    return out


def _evidence(raw: Any) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for ev in raw if isinstance(raw, list) else []:
        if not isinstance(ev, dict) or not isinstance(ev.get("label"), str) or not ev["label"].strip():
            continue
        entry = {"label": ev["label"]}
        if isinstance(ev.get("link"), str) and ev["link"].strip():
            entry["link"] = ev["link"]
        out.append(entry)
    return out


def parse_goal(raw: Any) -> Optional[Dict[str, Any]]:
    """One goal in the card's shape, or None when a required field is missing or invalid.

    A malformed OPTIONAL field is dropped, never the goal: the spec's "never shown half"
    is about the required fields — a goal without a usable progress is still the goal.
    """
    if not isinstance(raw, dict):
        return None
    gid, title = _text(raw.get("id")), _text(raw.get("title"))
    status = raw.get("status")
    if gid is None or title is None or status not in GOAL_STATUSES:
        return None
    goal: Dict[str, Any] = {"id": gid, "title": title, "status": status}
    for key in ("why", "serves", "deadline"):
        if isinstance(raw.get(key), str) and raw[key].strip():
            goal[key] = raw[key]
    progress = _progress(raw.get("progress"))
    if progress is not None:
        goal["progress"] = progress
    projects = raw.get("projects")
    goal["projects"] = [str(p) for p in projects
                        if isinstance(p, str) and p.strip()] if isinstance(projects, list) else []
    goal["evidence"] = _evidence(raw.get("evidence"))
    open_items = raw.get("openItems")
    if isinstance(open_items, int) and not isinstance(open_items, bool) and open_items >= 0:
        goal["openItems"] = open_items
    return goal


def parse_advice(raw: Any) -> Optional[Dict[str, Any]]:
    """One advice entry, or None when a required field is missing or `kind` is unknown."""
    if not isinstance(raw, dict):
        return None
    aid, sentence, why = _text(raw.get("id")), _text(raw.get("sentence")), _text(raw.get("why"))
    kind = raw.get("kind")
    if aid is None or sentence is None or why is None or kind not in ADVICE_KINDS:
        return None
    entry: Dict[str, Any] = {"id": aid, "kind": kind, "sentence": sentence, "why": why}
    goal_id = _text(raw.get("goalId"))
    if goal_id is not None:
        entry["goalId"] = goal_id
    return entry


def _parse_list(raw: List[Any], parse) -> tuple:
    """(entries in order, malformed count) — a repeated id counts as malformed."""
    out: List[Dict[str, Any]] = []
    seen = set()
    malformed = 0
    for entry_raw in raw:
        entry = parse(entry_raw)
        if entry is None or entry["id"] in seen:
            malformed += 1
            continue
        seen.add(entry["id"])
        out.append(entry)
    return out, malformed


def parse_goals(result: StatusResult, now: float) -> GoalsRead:
    """The publisher's answer as goals and advice in its order, with its markers."""
    if not result.ok:
        return GoalsRead(measured=False,
                         reason=result.error or f"the '{READ_COMMAND}' command failed")
    data = result.data
    if not isinstance(data, dict) or not isinstance(data.get("goals"), list):
        return GoalsRead(measured=False,
                         reason=f"the '{READ_COMMAND}' answer carries no 'goals' list")
    goals, bad_goals = _parse_list(data["goals"], parse_goal)
    raw_advice = data.get("advice")
    if raw_advice is None:
        raw_advice = []
    elif not isinstance(raw_advice, list):
        # Present but unusable: counted, so it is not shown as "no suggestions".
        logger.warning("owner goals: 'advice' is a %s, not a list; counted as malformed",
                       type(raw_advice).__name__)
        raw_advice = [raw_advice]
    advice, bad_advice = _parse_list(raw_advice, parse_advice)
    if bad_goals or bad_advice:
        logger.warning("owner goals: skipped %d goal(s) and %d advice entr(ies) missing a "
                       "required field or duplicated", bad_goals, bad_advice)
    complete = data.get("complete") if isinstance(data.get("complete"), bool) else None
    synthesized_at = data.get("synthesizedAt") if isinstance(data.get("synthesizedAt"), str) else None
    epoch = to_epoch(synthesized_at)
    return GoalsRead(
        measured=True, goals=goals, advice=advice,
        malformed_goals=bad_goals, malformed_advice=bad_advice,
        complete=complete, synthesized_at=synthesized_at,
        age_s=(max(0.0, now - epoch) if epoch is not None else None),
        unread_sources=unread_sources(data.get("unreadSources")),
    )


def act_payload(target_id: str, action: str, *, text: Optional[str] = None) -> Dict[str, Any]:
    """`{ id, action, text? }` — `rename` requires text; other actions carry it only if given."""
    if action not in ACTIONS:
        raise ValueError(f"not an owner-goals action: {action!r}")
    clean = text.strip() if isinstance(text, str) else None
    if action == "rename" and not clean:
        raise ValueError("rename needs the new title as text")
    payload: Dict[str, Any] = {"id": target_id, "action": action}
    if clean:
        payload["text"] = clean
    return payload
