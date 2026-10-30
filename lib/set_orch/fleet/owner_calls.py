"""The owner's calls — who to phone, and why: a promised callback, a retry, a missed call.

Layer 1 (abstract). Like the owner queue (`owner_queue.py`) and the goals (`owner_goals.py`),
the calls are an ordinary declared status-contract command: `owner-calls` to read,
`owner-calls-act` to hand the owner's answer back (spec `owner-calls-contract`). The publisher
is found by the same `find_publisher`, under the same `now.publisher` override, and the write
goes through the same one-`--json`-argument shape and the same delivered/refused reading.

Where the calls come from is the project's business (its mail, notes, dictations); set-core
shows what it is given and sends the owner's answer back.

**Every text field is display-only.** A call's who, about, phone, evidence labels and the
publisher's outcome are the publisher's words — they name people and numbers. They pass
through to the card and are never logged or stored: log lines here carry ids, counts and
classes only.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..project_status import StatusResult
from .now import to_epoch
from .owner_queue import ActResult, interpret_write, unread_sources, write_args

logger = logging.getLogger(__name__)

READ_COMMAND = "owner-calls"
WRITE_COMMAND = "owner-calls-act"

#: The owner's answers on a call (spec owner-calls-contract).
CALL_ACTIONS = ("called", "no-answer", "later", "not-needed")
ACTIONS = CALL_ACTIONS

#: promised = he said he would call · retry = he called, nobody answered ·
#: missed = they called, he did not pick up · follow-up = a call is a matter's next step.
CALL_KINDS = ("promised", "retry", "missed", "follow-up")

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,79}$")

__all__ = [
    "READ_COMMAND", "WRITE_COMMAND", "ACTIONS", "CALL_ACTIONS", "CALL_KINDS",
    "CallsRead", "parse_call", "parse_calls", "act_payload",
    "write_args", "interpret_write", "ActResult",
]


@dataclass
class CallsRead:
    measured: bool
    reason: Optional[str] = None
    calls: List[Dict[str, Any]] = field(default_factory=list)
    malformed: int = 0
    complete: Optional[bool] = None
    ranked_at: Optional[str] = None
    age_s: Optional[float] = None
    #: The publisher's own sources it could not read this round — display-only names.
    unread_sources: List[str] = field(default_factory=list)


def _text(value: Any, limit: int) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()[:limit]
    return None


def _evidence(raw: Any) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for ev in raw if isinstance(raw, list) else []:
        if not isinstance(ev, dict) or not isinstance(ev.get("label"), str) or not ev["label"].strip():
            continue
        entry = {"label": ev["label"]}
        if isinstance(ev.get("link"), str) and ev["link"].strip():
            entry["link"] = ev["link"]
        out.append(entry)
        if len(out) == 4:
            break
    return out


def parse_call(raw: Any) -> Optional[Dict[str, Any]]:
    """One call in the card's shape, or None when a required field is missing or invalid.

    Required: `id` (the contract's id pattern), `who`, `about`, a known `kind`. A malformed
    OPTIONAL field is dropped, never the call — a call without a usable due date is still
    a call to make.
    """
    if not isinstance(raw, dict):
        return None
    cid = raw.get("id")
    who, about = _text(raw.get("who"), 120), _text(raw.get("about"), 240)
    kind = raw.get("kind")
    if not isinstance(cid, str) or not _ID_RE.match(cid) or who is None or about is None \
            or kind not in CALL_KINDS:
        return None
    call: Dict[str, Any] = {"id": cid, "who": who, "about": about, "kind": kind}
    phone = _text(raw.get("phone"), 40)
    if phone is not None:
        call["phone"] = phone
    due = raw.get("due")
    if isinstance(due, str) and to_epoch(due) is not None:
        call["due"] = due
    project = _text(raw.get("project"), 80)
    if project is not None:
        call["project"] = project
    attempts = raw.get("attempts")
    if isinstance(attempts, int) and not isinstance(attempts, bool) and attempts >= 0:
        call["attempts"] = attempts
    for key in ("lastAttempt", "firstSeen"):
        if isinstance(raw.get(key), str) and to_epoch(raw[key]) is not None:
            call[key] = raw[key]
    call["evidence"] = _evidence(raw.get("evidence"))
    return call


def parse_calls(result: StatusResult, now: float) -> CallsRead:
    """The publisher's answer as calls in its order, with its markers."""
    if not result.ok:
        return CallsRead(measured=False, reason=result.error or f"the '{READ_COMMAND}' command failed")
    data = result.data
    if not isinstance(data, dict) or not isinstance(data.get("calls"), list):
        return CallsRead(measured=False, reason=f"the '{READ_COMMAND}' answer carries no 'calls' list")
    calls: List[Dict[str, Any]] = []
    seen = set()
    malformed = 0
    for raw in data["calls"]:
        call = parse_call(raw)
        if call is None or call["id"] in seen:
            malformed += 1
            continue
        seen.add(call["id"])
        calls.append(call)
    if malformed:
        logger.warning("owner calls: skipped %d call(s) missing a required field or duplicated",
                       malformed)
    complete = data.get("complete") if isinstance(data.get("complete"), bool) else None
    ranked_at = data.get("rankedAt") if isinstance(data.get("rankedAt"), str) else None
    epoch = to_epoch(ranked_at)
    return CallsRead(
        measured=True, calls=calls, malformed=malformed, complete=complete, ranked_at=ranked_at,
        age_s=(max(0.0, now - epoch) if epoch is not None else None),
        unread_sources=unread_sources(data.get("unreadSources")),
    )


def act_payload(call_id: str, action: str, *, text: Optional[str] = None,
                until: Optional[str] = None) -> Dict[str, Any]:
    """`{ id, action, text?, until? }` — `later` requires `until`; text only when given."""
    if action not in CALL_ACTIONS:
        raise ValueError(f"not an owner-calls action: {action!r}")
    if action == "later" and not until:
        raise ValueError("later needs until")
    payload: Dict[str, Any] = {"id": call_id, "action": action}
    clean = text.strip() if isinstance(text, str) else None
    if clean:
        payload["text"] = clean
    if action == "later":
        payload["until"] = until
    return payload
