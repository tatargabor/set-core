"""Issue management routes — ported from manager/api.py (aiohttp → FastAPI).

Routes:
    GET    /api/{project}/issues
    GET    /api/{project}/issues/stats
    GET    /api/{project}/issues/audit
    POST   /api/{project}/issues
    GET    /api/{project}/issues/{iid}
    POST   /api/{project}/issues/{iid}/{action}
    GET    /api/{project}/issues/groups
    POST   /api/{project}/issues/groups
    POST   /api/{project}/issues/groups/{gid}/fix
    GET    /api/{project}/issues/mutes
    POST   /api/{project}/issues/mutes
    DELETE /api/{project}/issues/mutes/{mid}
    GET    /api/issues (cross-project)
    GET    /api/issues/stats (cross-project)
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()

# Service reference — set by lifecycle.py at startup
_service = None


def set_service(service):
    """Called by lifecycle.py to inject the service manager."""
    global _service
    _service = service


def _get_issue_manager(project: str):
    if not _service:
        raise HTTPException(503, "Service not initialized")
    mgr = _service.issue_managers.get(project)
    if not mgr:
        raise HTTPException(404, f"Project '{project}' not found or no issue manager")
    return mgr


# --- Issues CRUD ---

@router.get("/api/{project}/issues")
async def list_issues(project: str, state: str = "", severity: str = ""):
    mgr = _get_issue_manager(project)
    issues = mgr.registry.all_issues()
    if state:
        from ..issues.models import IssueState
        try:
            issues = [i for i in issues if i.state == IssueState(state)]
        except ValueError:
            pass
    if severity:
        issues = [i for i in issues if i.severity == severity]
    issues.sort(key=lambda i: i.detected_at, reverse=True)
    return [i.to_dict() for i in issues]


@router.get("/api/{project}/issues/stats")
async def issue_stats(project: str):
    mgr = _get_issue_manager(project)
    return mgr.registry.stats()


@router.get("/api/{project}/issues/audit")
async def issue_audit(project: str, since: str = "", limit: int = 200, issue_id: str = ""):
    mgr = _get_issue_manager(project)
    entries = mgr.audit.read(
        since=float(since) if since else None,
        limit=limit,
        issue_id=issue_id or None,
    )
    return entries


@router.post("/api/{project}/issues")
async def create_issue(project: str, body: dict):
    mgr = _get_issue_manager(project)
    sup = _service.supervisors.get(project) if _service else None
    issue = mgr.register(
        source="user",
        error_summary=body.get("error_summary", ""),
        error_detail=body.get("error_detail", ""),
        environment=project,
        environment_path=str(sup.config.path) if sup else "",
    )
    if not issue:
        return {"status": "duplicate"}
    return issue.to_dict()


@router.get("/api/{project}/issues/{iid}")
async def get_issue(project: str, iid: str):
    mgr = _get_issue_manager(project)
    issue = mgr.registry.get(iid)
    if not issue:
        raise HTTPException(404, f"Issue {iid} not found")
    return issue.to_dict()


# --- Issue actions ---

@router.post("/api/{project}/issues/{iid}/investigate")
async def action_investigate(project: str, iid: str):
    return _do_action(project, iid, "investigate")


@router.post("/api/{project}/issues/{iid}/fix")
async def action_fix(project: str, iid: str):
    return _do_action(project, iid, "fix")


@router.post("/api/{project}/issues/{iid}/dismiss")
async def action_dismiss(project: str, iid: str):
    return _do_action(project, iid, "dismiss")


@router.post("/api/{project}/issues/{iid}/cancel")
async def action_cancel(project: str, iid: str):
    return _do_action(project, iid, "cancel")


@router.post("/api/{project}/issues/{iid}/skip")
async def action_skip(project: str, iid: str, body: dict = {}):
    mgr = _get_issue_manager(project)
    try:
        mgr.action_skip(iid, reason=body.get("reason", ""))
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        if "Cannot transition" in str(e):
            raise HTTPException(409, str(e))
        raise


@router.post("/api/{project}/issues/{iid}/mute")
async def action_mute(project: str, iid: str, body: dict = {}):
    mgr = _get_issue_manager(project)
    try:
        mgr.action_mute(iid, pattern=body.get("pattern"))
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        if "Cannot transition" in str(e):
            raise HTTPException(409, str(e))
        raise


@router.post("/api/{project}/issues/{iid}/extend-timeout")
async def action_extend_timeout(project: str, iid: str, body: dict):
    mgr = _get_issue_manager(project)
    try:
        mgr.action_extend_timeout(iid, extra_seconds=int(body.get("seconds", 300)))
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        if "Cannot transition" in str(e) or "only extend" in str(e).lower():
            raise HTTPException(409, str(e))
        raise


@router.post("/api/{project}/issues/{iid}/message")
async def issue_message(project: str, iid: str, body: dict):
    mgr = _get_issue_manager(project)
    message = body.get("message", "")
    mgr.audit.log(iid, "user_message", content=message)
    return {"status": "ok"}


@router.post("/api/{project}/issues/{iid}/resolve")
async def action_resolve(project: str, iid: str, body: dict = {}):
    """Operator escape hatch — mark an issue RESOLVED via the state machine.

    Used when a diagnosed issue blocks the merge queue and automatic
    resolution has not fired yet. Routes through `IssueManager.action_resolve`
    so any active investigator/fixer is killed, the state-machine
    transition is validated, and an audit entry is written.

    Body: {"reason": str}.
    """
    mgr = _get_issue_manager(project)
    reason = body.get("reason", "manual_resolve_via_api")
    try:
        mgr.action_resolve(iid, reason=reason)
    except ValueError as e:
        raise HTTPException(404, f"issue_not_found: {iid}") from e
    except Exception as e:
        if "Cannot transition" in str(e):
            raise HTTPException(409, str(e)) from e
        raise
    return {"status": "ok", "iss_id": iid, "new_state": "resolved"}


def _do_action(project: str, iid: str, action_name: str):
    mgr = _get_issue_manager(project)
    try:
        method = getattr(mgr, f"action_{action_name}")
        method(iid)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        if "Cannot transition" in str(e):
            raise HTTPException(409, str(e))
        raise


# --- Groups ---

@router.get("/api/{project}/issues/groups")
async def list_groups(project: str):
    mgr = _get_issue_manager(project)
    return [g.to_dict() for g in mgr.registry.all_groups()]


@router.post("/api/{project}/issues/groups")
async def create_group(project: str, body: dict):
    mgr = _get_issue_manager(project)
    group = mgr.action_group(
        issue_ids=body["issue_ids"],
        name=body["name"],
        reason=body.get("reason", ""),
    )
    return group.to_dict()


@router.post("/api/{project}/issues/groups/{gid}/fix")
async def group_fix(project: str, gid: str):
    mgr = _get_issue_manager(project)
    group = mgr.registry.get_group(gid)
    if not group:
        raise HTTPException(404, f"Group {gid} not found")
    mgr.action_fix(group.primary_issue)
    return {"status": "ok"}


# --- Mutes ---

@router.get("/api/{project}/issues/mutes")
async def list_mutes(project: str):
    mgr = _get_issue_manager(project)
    return [m.to_dict() for m in mgr.registry.all_mutes()]


@router.post("/api/{project}/issues/mutes")
async def add_mute(project: str, body: dict):
    mgr = _get_issue_manager(project)
    mute = mgr.registry.add_mute(
        pattern=body["pattern"],
        reason=body.get("reason", ""),
        expires_at=body.get("expires_at"),
    )
    return mute.to_dict()


@router.delete("/api/{project}/issues/mutes/{mid}")
async def delete_mute(project: str, mid: str):
    mgr = _get_issue_manager(project)
    mgr.registry.remove_mute(mid)
    return {"status": "ok"}


# --- Cross-project ---

@router.get("/api/issues")
async def all_issues():
    if not _service:
        return []
    all_issues = []
    for name, mgr in _service.issue_managers.items():
        for issue in mgr.registry.all_issues():
            all_issues.append(issue.to_dict())
    all_issues.sort(key=lambda i: i["detected_at"], reverse=True)
    return all_issues


@router.get("/api/issues/stats")
async def all_stats():
    if not _service:
        return {}
    return {
        name: mgr.registry.stats()
        for name, mgr in _service.issue_managers.items()
    }
