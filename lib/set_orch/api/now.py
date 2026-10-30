"""The Now card's API — `GET /api/fleet/now`, `POST /api/fleet/now/act`, `POST /api/fleet/now/focus`.

A separate router from `api/fleet.py`, registered BEFORE the `/api/{project}/...`
families for the same reason the fleet router is (CB-16).

Sources, all read at request time:

- the owner queue: the declared `owner-queue` command of the one publishing project,
  read through the status contract's cached, single-flight reader;
- the framework sources (agent questions, run state, bus-to-owner) through the
  `fleet-waiting-on-you` aggregator, `fleet.waiting.build_queue`. Imported lazily:
  while that module is absent the framework sources are reported UNMEASURED with
  the reason, never as empty;
- the owner's last input per agent, from the fleet's own state reader — the input
  to the breakpoint detector.

**What is logged:** item id, action kind, delivery status, error class. Never a
sentence, an option label, an answer, a reason or an outcome — the response
carries those to the card and nothing else keeps them.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..fleet import now as now_mod
from ..fleet import owner_queue as oq
from ..fleet import question_relay as qr
from ..project_status import write as contract_write
from . import project_status as api_status
from .helpers import _load_projects

logger = logging.getLogger(__name__)

router = APIRouter()

#: Load → modify → save of the card state is one critical section: the page polls,
#: and an action may land between a poll's load and its save.
_STATE_LOCK = threading.Lock()

TOMORROW_KEY = "*tomorrow*"
FRAMEWORK_SOURCE_FALLBACK = "framework"


# --------------------------------------------------------------------------- #
# sources
# --------------------------------------------------------------------------- #

def _framework_queue() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """(sources, items) from the waiting-on-you aggregator, or one unmeasured source."""
    try:
        from ..fleet import waiting  # noqa: WPS433 — lazy on purpose, see module docstring
        build = getattr(waiting, "build_queue")
    except (ImportError, AttributeError):
        return ([{"name": FRAMEWORK_SOURCE_FALLBACK, "measured": False,
                  "reason": "aggregator not available", "count": None}], [])
    try:
        answer = build()
    except Exception as exc:
        logger.warning("now api: waiting aggregator failed (%s)", type(exc).__name__)
        return ([{"name": FRAMEWORK_SOURCE_FALLBACK, "measured": False,
                  "reason": f"aggregator failed ({type(exc).__name__})", "count": None}], [])
    if not isinstance(answer, dict):
        return ([{"name": FRAMEWORK_SOURCE_FALLBACK, "measured": False,
                  "reason": "aggregator answered in an unexpected shape", "count": None}], [])
    sources = [s for s in answer.get("sources") or [] if isinstance(s, dict)]
    items = [i for i in answer.get("items") or [] if isinstance(i, dict) and i.get("id") is not None]
    return sources, items


def _owner_inputs() -> List[Tuple[Optional[str], Optional[float]]]:
    """(project, seconds since the owner last typed into it) for every live agent."""
    try:
        from ..fleet import discover_agents, read_state
        agents = discover_agents()
        return [(a.project_name, read_state(a.session_log, record=a.record).last_human_input_age)
                for a in agents]
    except Exception as exc:
        logger.warning("now api: last-input read failed (%s); no breakpoint this poll",
                       type(exc).__name__)
        return []


def _relay_waiting() -> Dict[str, Dict[str, Any]]:
    try:
        return {str(r.get("session_id")): r for r in qr.list_waiting()}
    except Exception as exc:
        logger.warning("now api: relay records unreadable (%s)", type(exc).__name__)
        return {}


def _go_there(item: Dict[str, Any], registered: set) -> Optional[Dict[str, str]]:
    """Where Go there leads: an agent tile, a supplied link, or the project's status page."""
    if item.get("sessionId"):
        return {"kind": "agent", "href": f"/?agent={item['sessionId']}"}
    if item.get("link"):
        link = str(item["link"])
        # An absolute file path is a local document: the card hands it to the desktop
        # (POST /api/desktop/open, with that route's own refusals). Opened as a URL it
        # would land on a dashboard 404.
        if link.startswith("/") and not link.startswith(("/?", "/p/")):
            return {"kind": "file", "href": link}
        return {"kind": "link", "href": link}
    # The project's status page is a real place only for the framework's own items (a run
    # state lives there). For a ranked item it is a page that says nothing about the task —
    # the owner, 2026-10-30: "itt a go there is értelmetlen" — so a ranked item without a
    # link of its own offers no Go there at all.
    if item.get("project") in registered and item.get("source") != oq.READ_COMMAND:
        return {"kind": "project", "href": f"/p/{item['project']}/status"}
    return None


def _fallback_sentence(raw: Dict[str, Any]) -> str:
    who = raw.get("agent") or raw.get("room") or raw.get("project") or "Something"
    kind = raw.get("kind")
    return f"{who} is waiting on you" + (f" ({kind})" if kind else "")


def _framework_item(raw: Dict[str, Any], relay: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    sid = raw.get("session_id")
    waiting = relay.get(str(sid)) if sid else None
    item = {
        "source": str(raw.get("source") or FRAMEWORK_SOURCE_FALLBACK),
        "id": str(raw["id"]),
        "project": raw.get("project"),
        "kind": raw.get("kind"),
        # The aggregator's title is the source's own words and may be absent (an
        # agent waiting with no stated question). The fallback names only shape.
        "sentence": raw.get("title") or _fallback_sentence(raw),
        "why": None,
        "since": raw.get("since"),
        "sessionId": sid,
        "agent": raw.get("agent"),
        "room": raw.get("room"),
        "options": [],
        "delegable": False,
        # A relayed single question can be answered with text from the card.
        "acceptsText": bool(waiting and int(waiting.get("questions") or 0) == 1
                            and not waiting.get("release_requested")),
        "relay": bool(waiting),
    }
    if raw.get("link"):
        item["link"] = raw["link"]
    return item


def _actions(item: Dict[str, Any], publisher: oq.Publisher) -> List[str]:
    if item["source"] == oq.READ_COMMAND:
        if not publisher.accepts_actions:
            return ["goThere", "later"]
        acts = ["goThere", "done", "later"]
        if item.get("options"):
            acts.append("answer")
        if item.get("acceptsText"):
            acts.append("text")
        if item.get("delegable"):
            acts.append("delegate")
        return acts
    acts = ["goThere", "done", "later"]
    if item.get("acceptsText"):
        acts.append("text")
    return acts


def _read_owner_queue(publisher: oq.Publisher, now: float, refresh: bool) -> oq.QueueRead:
    if publisher.state != "ok":
        return oq.QueueRead(measured=False, reason=publisher.reason)
    result = api_status._cached_query(publisher.path, oq.READ_COMMAND, publisher.config, refresh)
    return oq.parse_queue(result, now)


def _drop_read_cache(publisher: oq.Publisher) -> None:
    key_root = str(publisher.path)
    with api_status._CACHE_LOCK:
        for key in [k for k in api_status._CACHE if k[0] == key_root]:
            api_status._CACHE.pop(key, None)


def _registered() -> List[Dict[str, Any]]:
    try:
        return _load_projects()
    except Exception as exc:
        logger.warning("now api: project registry unreadable (%s)", type(exc).__name__)
        return []


# --------------------------------------------------------------------------- #
# GET /api/fleet/now
# --------------------------------------------------------------------------- #

def build_now(*, now: Optional[float] = None, refresh: bool = False,
              inputs: Optional[List[Tuple[Optional[str], Optional[float]]]] = None) -> Dict[str, Any]:
    now = time.time() if now is None else now
    cfg = now_mod.config()
    projects = _registered()
    registered = {p.get("name") for p in projects if p.get("name")}
    publisher = oq.find_publisher(projects, cfg["now.publisher"])
    qread = _read_owner_queue(publisher, now, refresh)

    owner_source: Dict[str, Any] = {"name": oq.READ_COMMAND, "count": len(qread.items) if qread.measured else None}
    if publisher.state == "none":
        # Not declared is not a failure: the card degrades to the framework sources and says so.
        owner_source.update(measured=None, reason=publisher.reason)
    else:
        owner_source.update(measured=qread.measured, reason=qread.reason)

    fw_sources, fw_raw = _framework_queue()
    relay = _relay_waiting()
    fw_items = [_framework_item(r, relay) for r in fw_raw]
    sources = [owner_source] + fw_sources
    unmeasured = sum(1 for s in sources if s.get("measured") is False)

    if inputs is None:
        inputs = _owner_inputs()

    with _STATE_LOCK:
        state = now_mod.load_state(now)
        now_mod.roll_day(state, now)
        merged = now_mod.merge(qread.items, fw_items, state, now)
        muted = list(state.get("mutedProjects") or [])
        tag_groups = now_mod.groups(merged, muted)
        unmuted, muted_hidden = now_mod.apply_mute(merged, muted)
        window = cfg["now.deadline_window_hours"] * 3600
        shown, held = now_mod.apply_focus(unmuted, state.get("focus") or [], now, window)
        first = shown[0] if shown else None
        cue = now_mod.decide_cue(state, inputs=inputs, first=first,
                                 focus=state.get("focus") or [], now=now, cfg=cfg)
        now_mod.save_state(state)

    item = None
    if first is not None:
        item = dict(first)
        item["actions"] = _actions(item, publisher)
        item["goThere"] = _go_there(item, registered)
        note = (state.get("resumeNotes") or {}).get(item.get("project"))
        if note and item.get("project") in (state.get("focus") or []):
            item["resumeNote"] = note.get("text") if isinstance(note, dict) else str(note)

    stale_after = cfg["now.stale_ranking_hours"] * 3600
    wind_down = now_mod.is_wind_down(now, cfg["now.wind_down_hour"])
    tomorrow = (state.get("resumeNotes") or {}).get(TOMORROW_KEY)
    tomorrow_text = (tomorrow.get("text") if isinstance(tomorrow, dict)
                     and tomorrow.get("day") != state.get("day") else None)

    focus_candidates: List[str] = []
    for i in merged:
        p = i.get("project")
        if p and p not in focus_candidates:
            focus_candidates.append(p)

    return {
        "item": item,
        "following": max(0, len(shown) - 1),
        "heldBack": held,
        "sources": sources,
        "unmeasured": unmeasured,
        "publisher": publisher.as_dict(),
        "partial": bool(qread.measured and qread.complete is not True),
        "malformed": qread.malformed,
        # The publisher's own unreadable inputs: the queue it ranked is missing them.
        "unreadSources": list(qread.unread_sources),
        "rankedAt": qread.ranked_at,
        "rankingAgeSeconds": qread.ranking_age_s,
        "stale": bool(qread.ranking_age_s is not None and qread.ranking_age_s > stale_after),
        "closedToday": int(state.get("closedToday") or 0),
        "parkedIdeas": int(state.get("parkedIdeas") or 0),
        "cue": cue,
        "windDown": {
            "active": wind_down,
            "hour": int(cfg["now.wind_down_hour"]),
            "delegableIds": [i["id"] for i in merged
                             if i.get("delegable") and i["source"] == oq.READ_COMMAND],
        },
        "tomorrowNote": None if wind_down else tomorrow_text,
        "focus": list(state.get("focus") or []),
        "focusMax": now_mod.FOCUS_MAX,
        "focusSetToday": state.get("focusDay") == state.get("day"),
        "focusCandidates": focus_candidates,
        "groups": tag_groups,
        "mutedHidden": muted_hidden,
        "generatedAt": now_mod.utc_iso(now),
    }


@router.get("/api/fleet/now")
def get_now(refresh: bool = Query(False)) -> Dict[str, Any]:
    """The one current item, and every marker the card needs around it."""
    payload = build_now(refresh=refresh)
    logger.info("now api: item=%s following=%d held=%d unmeasured=%d cue=%s",
                (payload["item"] or {}).get("id"), payload["following"], payload["heldBack"],
                payload["unmeasured"], payload["cue"].get("reason"))
    return payload


# --------------------------------------------------------------------------- #
# POST /api/fleet/now/act
# --------------------------------------------------------------------------- #

class ActBody(BaseModel):
    id: str
    source: str
    action: str
    option: Optional[str] = None
    text: Optional[str] = None
    reasons: Optional[List[str]] = None
    laterSeconds: Optional[float] = None
    sessionId: Optional[str] = None
    project: Optional[str] = None


LOCAL_ACTIONS = ("later",)
CLOSING_ACTIONS = ("answer", "done", "delegate", "wind-down-handoff")


def _result(delivered: bool, *, outcome: Optional[str] = None, reason: Optional[str] = None,
            sent: bool, state: Optional[Dict[str, Any]] = None,
            error_class: Optional[str] = None) -> Dict[str, Any]:
    return {
        "delivered": delivered, "sent": sent, "outcome": outcome, "reason": reason,
        "errorClass": error_class,
        "closedToday": int((state or {}).get("closedToday") or 0),
        "parkedIdeas": int((state or {}).get("parkedIdeas") or 0),
    }


def _log_act(body: ActBody, status: str, error_class: Optional[str] = None) -> None:
    logger.info("now api: act id=%s action=%s source=%s status=%s class=%s",
                body.id, body.action, body.source, status, error_class)


def _clean_reasons(reasons: Optional[List[str]]) -> List[str]:
    out = [r.strip() for r in (reasons or []) if isinstance(r, str) and r.strip()]
    if len(out) > 2:
        raise HTTPException(400, "at most two reasons")
    return out


def _send(publisher: oq.Publisher, payload: Dict[str, Any]) -> oq.ActResult:
    result = contract_write(publisher.path, oq.WRITE_COMMAND, oq.write_args(payload),
                            config=publisher.config)
    act = oq.interpret_write(result)
    if act.delivered:
        _drop_read_cache(publisher)
    return act


def _finish(body: ActBody, act: oq.ActResult, now: float, *, closes: bool,
            parked: bool = False, project: Optional[str] = None) -> Dict[str, Any]:
    with _STATE_LOCK:
        state = now_mod.load_state(now)
        now_mod.roll_day(state, now)
        if act.delivered:
            now_mod.mark_action(state)
            if closes:
                now_mod.count_closed(state)
            if parked:
                state["parkedIdeas"] = int(state.get("parkedIdeas") or 0) + 1
            if project:
                (state.get("resumeNotes") or {}).pop(project, None)
            now_mod.save_state(state)
    _log_act(body, "delivered" if act.delivered else "refused", act.error_class)
    return _result(act.delivered, outcome=act.outcome, reason=act.reason, sent=True,
                   state=state, error_class=act.error_class)


@router.post("/api/fleet/now/act")
def post_act(body: ActBody) -> Dict[str, Any]:
    """One owner action on the current item, sent to where the item came from."""
    now = time.time()
    cfg = now_mod.config()
    reasons = _clean_reasons(body.reasons)

    if body.action == "later":
        seconds = body.laterSeconds or 0
        if seconds <= 0:
            raise HTTPException(400, "later needs a positive laterSeconds")
        with _STATE_LOCK:
            state = now_mod.load_state(now)
            now_mod.roll_day(state, now)
            now_mod.snooze(state, body.id, now + seconds)
            now_mod.mark_action(state)
            now_mod.save_state(state)
        _log_act(body, "snoozed")
        # Held by the card, not sent: the source never hears about a Later.
        return _result(True, sent=False, state=state)

    publisher = oq.find_publisher(_registered(), cfg["now.publisher"])

    if body.action == "park-idea" or (body.action == "resume-note"):
        text = (body.text or "").strip()
        if not text:
            raise HTTPException(400, f"{body.action} needs text")
        if publisher.state == "ok" and publisher.accepts_actions:
            act = _send(publisher, oq.act_payload(body.id, body.action, text=text))
            return _finish(body, act, now, closes=False, parked=body.action == "park-idea")
        if body.action == "park-idea":
            _log_act(body, "refused", "no-publisher")
            return _result(False, sent=False, reason=publisher.reason
                           or "the publisher accepts no actions, so an idea has nowhere to go")
        # Resume note with no publisher: kept locally — the one place owner text is
        # stored by the framework, and only because there is no publisher (spec).
        key = TOMORROW_KEY if body.id == "tomorrow" else (body.project or body.id)
        with _STATE_LOCK:
            state = now_mod.load_state(now)
            now_mod.roll_day(state, now)
            state.setdefault("resumeNotes", {})[key] = {"text": text, "day": state["day"]}
            now_mod.save_state(state)
        _log_act(body, "kept-locally")
        return _result(True, sent=False, state=state)

    if body.source == oq.READ_COMMAND:
        if publisher.state != "ok":
            raise HTTPException(409, publisher.reason or "no publisher")
        if not publisher.accepts_actions:
            raise HTTPException(409, f"the publisher declares no '{oq.WRITE_COMMAND}' "
                                     "write command — it accepts no actions")
        if body.action not in oq.ACTIONS:
            raise HTTPException(400, f"not an owner-queue action: {body.action!r}")
        qread = _read_owner_queue(publisher, now, refresh=False)
        item = next((i for i in qread.items if i["id"] == body.id), None)
        if item is None:
            raise HTTPException(409, "that item is no longer in the owner queue")
        if body.action == "answer":
            if body.option is None and not (body.text or "").strip():
                raise HTTPException(400, "an answer needs an option or text")
            if body.option is not None and body.option not in {o["id"] for o in item["options"]}:
                raise HTTPException(400, "that option is not offered on this item")
        # "Not needed: <why>" already is the reason for not handing it over.
        not_needed = body.action == "done" and bool((body.text or "").strip())
        if item.get("delegable") and body.action in ("done", "answer") and not reasons and not not_needed:
            raise HTTPException(400, "keeping a delegable item needs one or two reasons")
        payload = oq.act_payload(body.id, body.action, option=body.option,
                                 text=(body.text or None), reasons=reasons or None)
        act = _send(publisher, payload)
        return _finish(body, act, now, closes=body.action in CLOSING_ACTIONS,
                       project=item.get("project"))

    # A framework item.
    if body.action == "done":
        with _STATE_LOCK:
            state = now_mod.load_state(now)
            now_mod.roll_day(state, now)
            now_mod.dismiss(state, body.id, now)
            now_mod.mark_action(state)
            now_mod.count_closed(state)
            now_mod.save_state(state)
        _log_act(body, "dismissed")
        return _result(True, sent=False, state=state,
                       outcome="Removed from the card — the source itself is unchanged")
    if body.action == "answer":
        if not body.sessionId or not (body.text or "").strip():
            raise HTTPException(400, "answering an agent needs its session and text")
        failure = qr.deliver_answer(body.sessionId, body.text or "")
        act = (oq.ActResult(True, outcome="Handed to the waiting agent")
               if failure is None else oq.ActResult(False, reason=failure, error_class="relay"))
        return _finish(body, act, now, closes=True)
    raise HTTPException(400, f"{body.action!r} is not available on a {body.source} item")


# --------------------------------------------------------------------------- #
# POST /api/fleet/now/groups
# --------------------------------------------------------------------------- #

class GroupsBody(BaseModel):
    #: the projects switched OFF on the tag strip — the whole list, not a delta
    muted: List[str]


@router.post("/api/fleet/now/groups")
def post_groups(body: GroupsBody) -> Dict[str, Any]:
    """Switch projects off (or back on) on the card's tag strip."""
    now = time.time()
    with _STATE_LOCK:
        state = now_mod.load_state(now)
        muted = now_mod.set_muted(state, body.muted)
        now_mod.save_state(state)
    return {"ok": True, "muted": muted}


# POST /api/fleet/now/focus
# --------------------------------------------------------------------------- #

class FocusBody(BaseModel):
    projects: List[str]
    #: project → one-line resume note, for projects leaving the focus
    notes: Optional[Dict[str, str]] = None


@router.post("/api/fleet/now/focus")
def post_focus(body: FocusBody) -> Dict[str, Any]:
    """Set the day's focus projects (at most three); resume notes go to the publisher."""
    now = time.time()
    cfg = now_mod.config()
    with _STATE_LOCK:
        state = now_mod.load_state(now)
        now_mod.roll_day(state, now)
        outcome = now_mod.set_focus(state, body.projects, now)
        if outcome["ok"]:
            now_mod.save_state(state)
    if not outcome["ok"]:
        return outcome

    notes = {k: v.strip() for k, v in (body.notes or {}).items()
             if k in outcome["removed"] and isinstance(v, str) and v.strip()}
    delivered: Dict[str, Any] = {}
    if notes:
        publisher = oq.find_publisher(_registered(), cfg["now.publisher"])
        for project, text in notes.items():
            if publisher.state == "ok" and publisher.accepts_actions:
                act = _send(publisher, oq.act_payload(f"project:{project}", "resume-note", text=text))
                delivered[project] = act.as_dict()
                logger.info("now api: resume note for %s sent; delivered=%s", project, act.delivered)
            else:
                with _STATE_LOCK:
                    state = now_mod.load_state(now)
                    state.setdefault("resumeNotes", {})[project] = {"text": text, "day": state["day"]}
                    now_mod.save_state(state)
                delivered[project] = {"delivered": True, "keptLocally": True}
                logger.info("now api: resume note for %s kept locally (no publisher)", project)
    outcome["notes"] = delivered
    return outcome
