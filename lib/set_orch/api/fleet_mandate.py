"""Fleet routes for mandates, desks, engagements and the relation map.

    POST /api/fleet/mandates                    — declare a mandate for an agent that has none
    POST /api/fleet/desks/resolve               — find or start a project's desk for a request
    POST /api/fleet/engagements/{id}/sent       — the asker reports where its request is on the bus
    POST /api/fleet/engagements/{id}/failed     — the asker reports that the send did not happen
    POST /api/fleet/engagements/{id}/withdraw   — the asker takes a request back
    GET  /api/fleet/engagements                 — engagements, by asker / project / state
    GET  /api/fleet/map                         — projects, agents, and the relations between them

Kept out of `api/fleet.py` on purpose: that module is the inventory and the terminal, and it
is edited by several sessions at once. This one only reads it — the live rows, the registry,
the start-location verdict — and adds the routes that join the mandate, desk and engagement
records to them.

**Every text field here is display-only.** A goal, a subject, a role and a flow are the
operator's or an agent's own words. They pass through to the response and are never logged:
log lines carry ids, kinds, states and reason classes only.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from ..fleet import desk as fleet_desk
from ..fleet import engagement as fleet_engagement
from ..fleet import mandate as fleet_mandate
from ..fleet.owner_client import OwnerClient, OwnerClientError, OwnerUnavailable
from . import fleet as fleet_api

logger = logging.getLogger(__name__)

router = APIRouter()

#: An engagement that failed is shown on the map for this long, then drops off it.
FAILED_VISIBLE_SECONDS = 3600.0


# --------------------------------------------------------------------------- #
# Shared reads
# --------------------------------------------------------------------------- #

def _live_rows() -> Optional[List[Dict[str, Any]]]:
    """Every live agent row of the inventory, flat — or None when it cannot be built."""
    try:
        listing = fleet_api.fleet_agents(include_oneshot=False)
    except Exception as exc:  # noqa: BLE001 — the caller reports `unmeasured`
        logger.warning("fleet mandate api: the inventory could not be read (%s)", type(exc).__name__)
        return None
    return [row for group in listing.get("projects") or [] for row in group.get("agents") or []]


def _registry() -> List[Dict[str, Any]]:
    return [{"name": p.get("name"), "root": p.get("path"), "archived": p.get("archived") is True}
            for p in fleet_api._safe_registry() if p.get("name")]


def _start_location_ok(root: str) -> bool:
    try:
        allowed, _why = fleet_api._start_location_verdict(os.path.realpath(os.path.expanduser(root)))
    except Exception as exc:  # noqa: BLE001
        logger.warning("fleet mandate api: start-location could not be decided (%s)", type(exc).__name__)
        return False
    return bool(allowed)


# --------------------------------------------------------------------------- #
# Declaring a mandate after the fact
# --------------------------------------------------------------------------- #

class DeclareBody(BaseModel):
    """A mandate for an agent that has none. Name the agent by label or by session id."""

    model_config = ConfigDict(extra="forbid")

    goal: str
    label: Optional[str] = None
    session_id: Optional[str] = None
    paths: List[str] = []
    change: Optional[str] = None
    done_when: Optional[str] = None
    requested_by: Optional[str] = None


@router.post("/api/fleet/mandates")
def fleet_declare_mandate(body: DeclareBody) -> Dict[str, Any]:
    """Record a mandate for a running agent that has none, and say whether it will be told.

    An agent the framework started carries a mandate id in its environment even when it was
    given no goal; the declaration takes that id, so the agent's own session-start hook finds
    it at the next start, clear or compaction. An agent the framework did not start has no
    such id and no hook: the record is for the screen, and the answer says so.
    """
    if not body.goal.strip():
        raise HTTPException(status_code=400, detail="a mandate needs a goal")
    if not body.label and not body.session_id:
        raise HTTPException(status_code=400, detail="name the agent: `label` or `session_id`")
    rows = _live_rows()
    if rows is None:
        raise HTTPException(status_code=503, detail="the fleet inventory could not be read")
    row = next((r for r in rows
                if (body.label and r.get("terminal_label") == body.label)
                or (body.session_id and r.get("session_id") == body.session_id)), None)
    if row is None:
        raise HTTPException(status_code=404, detail="no live agent matches that label or session id")
    if row.get("mandate"):
        raise HTTPException(status_code=409,
                            detail=f"this agent already has mandate {row['mandate']['id']}")
    if (row.get("mandate_absent") or {}).get("reason") == fleet_mandate.ABSENT_UNMEASURED:
        raise HTTPException(status_code=503, detail="the mandate store could not be read")

    carried = fleet_mandate.mandate_id_of_pid(int(row["pid"])) if row.get("pid") else None
    try:
        record = fleet_mandate.MandateStore().create(
            mandate_id=carried, kind="work", goal=body.goal,
            scope={"paths": list(body.paths), "change": body.change},
            done_when=body.done_when, requested_by=body.requested_by,
            project=row.get("project"), cwd=row.get("cwd"),
            label=row.get("terminal_label"), source="declared",
            carrier=bool(carried), session_id=row.get("session_id"),
        )
    except fleet_mandate.MandateError as exc:
        raise HTTPException(status_code=409 if exc.kind == "id-taken" else 400, detail=str(exc)) from exc
    except (fleet_mandate.MandateStoreUnreadable, OSError) as exc:
        raise HTTPException(status_code=503,
                            detail=f"the mandate store could not be written ({type(exc).__name__})") from exc
    logger.info("fleet mandate api: declared %s for pid %s (carrier=%s)",
                record["id"], row.get("pid"), bool(carried))
    # From the RECORD, not from the local variable: what is reported as "will be told" must
    # be what was written down.
    return {**fleet_mandate.public(record), "carrier": record["carrier"]}


# --------------------------------------------------------------------------- #
# The desk
# --------------------------------------------------------------------------- #

class ResolveBody(BaseModel):
    """A request for a project. The text of the request is NOT part of this body.

    The asker sends it on the bus itself, as itself; this route only finds — or starts — the
    session that will receive it, and records that an engagement exists.
    """

    model_config = ConfigDict(extra="forbid")

    project: str
    #: The asker's own bus seat. Recorded as a claim, like every requester.
    requested_by: Optional[str] = None
    kind: str = "REQUEST"
    #: A short label for the map. Never the request itself.
    subject: Optional[str] = None


def _start_desk(*, label: str, cwd: str, project: str, mandate_id: str,
                mandate_kind: str, requested_by: Optional[str]) -> Dict[str, Any]:
    """Start a desk through the owner, mapping its answers onto the resolver's two errors."""
    try:
        return OwnerClient().start(
            label=label, cwd=cwd, project=project, requested_by=requested_by,
            mandate_id=mandate_id, mandate_kind=mandate_kind,
        )
    except OwnerUnavailable as exc:
        raise fleet_desk.StartFailed("owner-unavailable", str(exc)) from exc
    except OwnerClientError as exc:
        if getattr(exc, "kind", None) == "owner-too-old":
            # Not "unavailable": the owner answers, it just predates the parameter. The
            # message names the restart that fixes it.
            raise fleet_desk.StartFailed("start-refused", str(exc)) from exc
        # The owner refuses a held label and a scope that is still running. Which of the
        # two it was is not read from its sentence: the resolver looks again, and a desk
        # that is there settles it.
        raise fleet_desk.LabelHeld(str(exc)) from exc


def _resolver() -> fleet_desk.DeskResolver:
    return fleet_desk.DeskResolver(
        mandates=fleet_mandate.MandateStore(),
        live_agents=_live_rows,
        projects=_registry,
        start=_start_desk,
        start_location_ok=_start_location_ok,
    )


@router.post("/api/fleet/desks/resolve")
def fleet_resolve_desk(body: ResolveBody) -> Dict[str, Any]:
    """Find the project's desk, or start it, and open an engagement for the request.

    Returns the engagement id and the desk's seat. A refusal is a 409 carrying the reason
    class, and the engagement is recorded as failed with that class — a request that could
    not be delivered is still a fact the map shows.
    """
    engagements = fleet_engagement.EngagementStore()
    try:
        record = engagements.open(asker=body.requested_by, project=body.project,
                                  kind=body.kind, subject=body.subject)
    except fleet_engagement.EngagementError as exc:
        status = 429 if exc.kind == "bound" else 400
        raise HTTPException(status_code=status, detail={
            "reason": exc.kind, "detail": str(exc),
            "open": [fleet_engagement.view(r) for r in exc.open],
        }) from exc

    try:
        found = _resolver().resolve(body.project, requested_by=body.requested_by)
    except fleet_desk.DeskRefused as exc:
        reason = exc.reason if exc.reason in fleet_engagement.FAIL_CLASSES else "start-refused"
        engagements.mark_failed(record["id"], reason)
        logger.info("fleet mandate api: engagement %s failed at resolution (%s)", record["id"], reason)
        raise HTTPException(status_code=409, detail={
            "reason": exc.reason, "detail": exc.detail or exc.reason, "engagement_id": record["id"],
        }) from exc
    except Exception as exc:  # noqa: BLE001 — never leave an engagement resolving forever
        engagements.mark_failed(record["id"], "unmeasured")
        logger.warning("fleet mandate api: engagement %s — resolution raised %s",
                       record["id"], type(exc).__name__)
        raise HTTPException(status_code=500, detail={
            "reason": "unmeasured", "detail": type(exc).__name__, "engagement_id": record["id"],
        }) from exc

    engagements.set_desk(record["id"], label=found.label, seat=found.seat, mandate_id=found.mandate_id)
    logger.info("fleet mandate api: engagement %s resolved to a desk (started=%s)",
                record["id"], found.started)
    return {"engagement_id": record["id"], "desk": found.to_dict()}


# --------------------------------------------------------------------------- #
# Engagements
# --------------------------------------------------------------------------- #

class SentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room: str
    ts: str


class FailedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = "send-failed"


def _known(record: Optional[Dict[str, Any]], engagement_id: str) -> Dict[str, Any]:
    if record is None:
        raise HTTPException(status_code=404, detail=f"no engagement {engagement_id}")
    return record


@router.post("/api/fleet/engagements/{engagement_id}/sent")
def fleet_engagement_sent(engagement_id: str, body: SentBody) -> Dict[str, Any]:
    """The asker's request is on the bus; record where. `resolving` → `open`."""
    store = fleet_engagement.EngagementStore()
    try:
        record = store.mark_sent(engagement_id, room=body.room, ts=body.ts)
    except fleet_engagement.EngagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return fleet_engagement.view(_known(record, engagement_id))


@router.post("/api/fleet/engagements/{engagement_id}/failed")
def fleet_engagement_failed(engagement_id: str, body: Optional[FailedBody] = None) -> Dict[str, Any]:
    store = fleet_engagement.EngagementStore()
    reason = (body.reason if body else "send-failed")
    try:
        record = store.mark_failed(engagement_id, reason)
    except fleet_engagement.EngagementError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return fleet_engagement.view(_known(record, engagement_id))


@router.post("/api/fleet/engagements/{engagement_id}/withdraw")
def fleet_engagement_withdraw(engagement_id: str) -> Dict[str, Any]:
    store = fleet_engagement.EngagementStore()
    return fleet_engagement.view(_known(store.withdraw(engagement_id), engagement_id))


def _engagement_views(*, asker: Optional[str] = None, project: Optional[str] = None,
                      state: Optional[str] = None) -> Dict[str, Any]:
    """Engagements as payloads, after asking the bus which open ones were answered."""
    store = fleet_engagement.EngagementStore()
    try:
        refreshed = fleet_engagement.refresh(store)
        records = store.list(asker=asker, project=project)
    except Exception as exc:  # noqa: BLE001
        logger.warning("fleet mandate api: engagements could not be read (%s)", type(exc).__name__)
        return {"engagements": [], "measured": False, "reason": type(exc).__name__}
    unreadable = set(refreshed["unreadable"])
    views = [fleet_engagement.view(r, unmeasured=r["id"] in unreadable) for r in records]
    if state:
        views = [v for v in views if v["state"] == state]
    return {
        "engagements": views,
        # False when at least one open engagement's room could not be read: those are
        # reported as `unmeasured`, never as open or waiting.
        "measured": refreshed["measured"],
        "reason": None if refreshed["measured"] else "bus-unreadable",
    }


@router.get("/api/fleet/engagements")
def fleet_engagements(asker: Optional[str] = Query(None), project: Optional[str] = Query(None),
                      state: Optional[str] = Query(None)) -> Dict[str, Any]:
    return _engagement_views(asker=asker, project=project, state=state)


# --------------------------------------------------------------------------- #
# The quiet sweep
# --------------------------------------------------------------------------- #

def sweep_desks() -> Dict[str, Any]:
    """Stop every desk that is measured quiet with nothing open. Returns what it decided.

    Run periodically from the service's lifespan. Any unmeasured input keeps the desk.
    """
    out: Dict[str, Any] = {"stopped": [], "kept": [], "measured": True}
    rows = _live_rows()
    if rows is None:
        out["measured"] = False
        return out
    try:
        quiet_after = fleet_desk.quiet_seconds()
        engagements = fleet_engagement.EngagementStore()
        fleet_engagement.refresh(engagements)
    except Exception as exc:  # noqa: BLE001
        logger.warning("fleet desk sweep: could not be run (%s)", type(exc).__name__)
        out["measured"] = False
        return out
    for row in rows:
        held = row.get("mandate")
        if not held or held.get("kind") != "desk" or row.get("population") != "started-here":
            continue
        label = row.get("terminal_label")
        try:
            live = engagements.live_for_desk(str(held.get("project")))
        except Exception:  # noqa: BLE001
            live = None
        decision, why = fleet_desk.sweep_decision(row, live_engagements=live, quiet_after=quiet_after)
        if decision != fleet_desk.STOP or not label:
            out["kept"].append({"label": label, "why": why})
            continue
        try:
            result = OwnerClient().stop(label)
        except (OwnerUnavailable, OwnerClientError) as exc:
            logger.warning("fleet desk sweep: %s (pid %s) was not stopped (%s)",
                           label, row.get("pid"), type(exc).__name__)
            out["kept"].append({"label": label, "why": "stop-failed"})
            continue
        if result.get("found"):
            fleet_mandate.MandateStore().end(held["id"], "desk-quiet")
            logger.info("fleet desk sweep: stopped %s (pid %s) after %.0f s without movement",
                        label, row.get("pid"), float(row.get("last_movement_seconds") or 0))
            out["stopped"].append(label)
    return out


#: How often the service looks for a quiet desk. Far below the quiet bound itself, so a
#: desk is stopped within a few minutes of becoming eligible.
SWEEP_INTERVAL_SECONDS = 300.0


async def sweep_loop(interval: float = SWEEP_INTERVAL_SECONDS) -> None:
    """The periodic carrier of `sweep_desks`, run from the service's lifespan.

    The sweep itself runs on a thread: it reads the inventory and may stop a scope, and
    neither belongs on the event loop. A failed round is logged and the loop goes on — one
    bad round must not end the sweeping for the life of the service.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(sweep_desks)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("fleet desk sweep: a round failed (%s)", type(exc).__name__)


# --------------------------------------------------------------------------- #
# The map
# --------------------------------------------------------------------------- #

def _flows(sources: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Declared flows between registered projects, from the machine-local role file."""
    from .. import project_roles

    try:
        roles = project_roles.load_roles(project_roles.role_file_path())
    except Exception as exc:  # noqa: BLE001
        logger.warning("fleet map: the role file could not be read (%s)", type(exc).__name__)
        sources["roles"] = "unreadable"
        return []
    if roles is None:
        sources["roles"] = "none"
        return []
    sources["roles"] = "ok"
    registry = {p["name"]: p for p in _registry()}
    out = []
    for name in sorted(roles):
        if name not in registry:
            continue
        for flow in project_roles.flows_of(roles.get(name), registry, self_name=name):
            out.append({"type": "flow", "from_project": name, "to_project": flow["to"],
                        "what": flow["what"], "how": flow["how"]})
    return out


@router.get("/api/fleet/map")
def fleet_map() -> Dict[str, Any]:
    """Projects, their live agents with mandates, and three kinds of relation.

    - `engagement` — an asker and the desk it asked, with state and age;
    - `started`    — who asked for an agent to be started; a CLAIM, and marked as one;
    - `flow`       — a declared relation between two projects, from the role file.

    `sources` says what could not be read. A relation kind whose source is missing is
    unmeasured, not empty.
    """
    sources: Dict[str, Any] = {"inventory": True, "mandates": True, "bus": True, "roles": "ok"}
    try:
        listing = fleet_api.fleet_agents(include_oneshot=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("fleet map: the inventory could not be read (%s)", type(exc).__name__)
        listing = {"projects": []}
        sources["inventory"] = False

    engaged = _engagement_views()
    if not engaged["measured"]:
        sources["bus"] = False
    import time as _time
    shown = [
        e for e in engaged["engagements"]
        if e["state"] in ("resolving", "open", "unmeasured")
        or (e["state"] == "failed" and (e["age_seconds"] or 0) <= FAILED_VISIBLE_SECONDS)
    ]
    engaged_projects = {e["project"] for e in shown}

    projects: List[Dict[str, Any]] = []
    by_seat: Dict[str, Dict[str, Any]] = {}
    no_mandate = 0
    for group in listing.get("projects") or []:
        agents = []
        for row in group.get("agents") or []:
            absent = row.get("mandate_absent")
            if (absent or {}).get("reason") == fleet_mandate.ABSENT_UNMEASURED:
                sources["mandates"] = False
            if row.get("mandate") is None and (absent or {}).get("reason") != fleet_mandate.ABSENT_UNMEASURED:
                no_mandate += 1
            node = {
                "pid": row.get("pid"),
                "label": row.get("terminal_label") or row.get("name"),
                "seat": row.get("seat"),
                "state": row.get("state"),
                "population": row.get("population"),
                "mandate": row.get("mandate"),
                "mandate_absent": absent,
            }
            agents.append(node)
            if row.get("seat"):
                by_seat[row["seat"]] = {"project": group.get("name"), "pid": row.get("pid")}
        projects.append({
            "name": group.get("name"),
            "archived": bool(group.get("archived")),
            "agents": agents,
            # Expanded only where something is happening: a map of every registered
            # project would bury the few that have an agent or an open request.
            "expanded": bool(agents) or group.get("name") in engaged_projects,
        })

    relations: List[Dict[str, Any]] = []
    waiting = failed = 0
    for e in shown:
        waiting += 1 if e["waiting"] else 0
        failed += 1 if e["state"] == "failed" else 0
        relations.append({
            "type": "engagement", "id": e["id"],
            "from_seat": e["asker"], "from_pid": (by_seat.get(e["asker"] or "") or {}).get("pid"),
            "to_project": e["project"], "to_seat": e["desk_seat"],
            "to_pid": (by_seat.get(e["desk_seat"] or "") or {}).get("pid"),
            "kind": e["kind"], "subject": e["subject"], "state": e["state"],
            "reason": e["reason"], "age_seconds": e["age_seconds"], "waiting": e["waiting"],
        })
    for group in listing.get("projects") or []:
        for row in group.get("agents") or []:
            parent = row.get("parent") or {}
            if parent.get("source") == "recorded" and parent.get("seat"):
                relations.append({
                    "type": "started",
                    "from_seat": parent["seat"],
                    "from_pid": (by_seat.get(parent["seat"]) or {}).get("pid"),
                    "to_pid": row.get("pid"), "to_seat": row.get("seat"),
                    # Nothing verified who asked. The map marks it; it does not draw it as fact.
                    "is_claim": True,
                })
    relations += _flows(sources)

    return {
        "projects": projects,
        "relations": relations,
        "counts": {"no_mandate": no_mandate, "waiting": waiting, "failed": failed},
        "sources": sources,
        "generated_at": _time.time(),
    }
