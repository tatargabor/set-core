"""Question-relay Details and Teach (fleet-relay-teach).

`GET  /api/fleet/question-relay/{call_id}/detail` — what a waiting call asks and what it waits for.
`POST /api/fleet/question-relay/{call_id}/teach`  — answer it now and record a project rule.

The question's text comes only from the auto-answer decider's private pending record: the
relay's own waiting record deliberately carries no question text (three relay tests hold that),
so a call the decider never saw can be read in outline but not taught. Logs carry the call id
and outcomes, never a question, an answer or a rule.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class TeachBody(BaseModel):
    answer: str
    explanation: str = ""


def _detail(call_id: str) -> Dict[str, Any]:
    from ..fleet import auto_answer_worker as aw
    from ..fleet import question_relay as qr
    from ..fleet import relay_teach as rt

    waiting = rt.find_waiting(call_id)
    if waiting is None:
        raise HTTPException(status_code=404, detail="no question with that id is waiting on the relay")
    now = time.time()
    started = waiting.get("started")
    pending = aw.read_pending(qr.state_dir(), call_id)
    cwd = str(waiting.get("cwd") or (pending or {}).get("cwd") or "")
    decider: Optional[Dict[str, Any]] = None
    if pending is not None:
        decider = {
            "state": "cancelled" if pending.get("cancelled") else pending.get("state"),
            "method": pending.get("method"),
            "seconds_left": (max(0.0, pending["write_at"] - now)
                             if pending.get("state") == "proposed" and not pending.get("cancelled")
                             and isinstance(pending.get("write_at"), (int, float)) else None),
            "questions": [{
                "key": q.get("key"), "question": q.get("question") or "", "options": q.get("options") or [],
                "outcome": q.get("outcome"), "reason": q.get("reason") or "",
                "choice": q.get("choice"), "tier": q.get("tier"), "confidence": q.get("confidence"),
                "references": [{"kind": r.get("kind"), "quote": r.get("quote"),
                                "path": aw._shown_path(str(r["path"]), cwd) if r.get("path") else None}
                               for r in q.get("references") or [] if r.get("checked")],
            } for q in pending.get("questions") or []],
        }
    why_not = rt.teachable(waiting)
    if why_not is None and (decider is None or len(decider["questions"]) != 1):
        why_not = ("the decider has no record of this call, so its text is not kept here — "
                   "answer it on the channel or in the terminal")
    if waiting.get("release_requested"):
        waits_for = "release"
    elif decider and decider["seconds_left"] is not None:
        waits_for = "countdown"
    else:
        waits_for = "answer"
    first = (decider or {}).get("questions") or [{}]
    return {
        "id": call_id, "session_id": waiting.get("session_id"), "project": waiting.get("project"),
        "kind": waiting.get("kind") or "question", "questions": waiting.get("questions"),
        "seconds": (now - started) if isinstance(started, (int, float)) else None,
        "release_requested": bool(waiting.get("release_requested")),
        "waits_for": waits_for,
        "decider": decider,
        "teach": {"allowed": why_not is None, "reason": why_not or "",
                  "prefill": first[0].get("choice") or ""},
    }


@router.get("/api/fleet/question-relay/{call_id}/detail")
def question_relay_detail(call_id: str) -> Dict[str, Any]:
    return _detail(call_id)


@router.post("/api/fleet/question-relay/{call_id}/teach")
def question_relay_teach(call_id: str, body: TeachBody) -> Dict[str, Any]:
    """Answer the call now as the operator, then append the rule to the project's taught-rules
    file in its main worktree and commit that file alone (design D2–D4)."""
    from ..fleet import auto_answer_worker as aw
    from ..fleet import question_relay as qr
    from ..fleet import relay_teach as rt

    detail = _detail(call_id)
    if not detail["teach"]["allowed"]:
        raise HTTPException(status_code=409, detail=detail["teach"]["reason"])
    if not body.answer.strip():
        raise HTTPException(status_code=422, detail="the answer is empty")
    pending = aw.read_pending(qr.state_dir(), call_id) or {}
    question = (detail["decider"]["questions"][0].get("question") or "") if detail["decider"] else ""
    waiting = rt.find_waiting(call_id)
    res = rt.teach(call_id, body.answer, body.explanation, question=question,
                   cwd=str((waiting or {}).get("cwd") or pending.get("cwd") or ""), waiting=waiting)
    logger.info("fleet api: relay teach %s — answered=%s written=%s commit=%s",
                qr._safe_id(call_id)[-12:], res.answered, res.written, res.commit.sha or "none")
    return res.as_dict()
