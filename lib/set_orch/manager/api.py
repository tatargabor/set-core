"""Manager REST API — consumed by set-web."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from .service import ServiceManager

logger = logging.getLogger(__name__)


def create_api(service: ServiceManager) -> web.Application:
    """Create aiohttp application with all manager API routes."""
    app = web.Application()
    app["service"] = service

    # Service health
    app.router.add_get("/api/manager/status", handle_manager_status)

    # Projects
    app.router.add_get("/api/projects", handle_list_projects)
    app.router.add_post("/api/projects", handle_add_project)
    app.router.add_delete("/api/projects/{name}", handle_remove_project)
    app.router.add_get("/api/projects/{name}/status", handle_project_status)

    # Sentinel control
    app.router.add_post("/api/projects/{name}/sentinel/start", handle_sentinel_start)
    app.router.add_post("/api/projects/{name}/sentinel/stop", handle_sentinel_stop)
    app.router.add_post("/api/projects/{name}/sentinel/restart", handle_sentinel_restart)

    # Orchestration control
    app.router.add_post("/api/projects/{name}/orchestration/start", handle_orch_start)
    app.router.add_post("/api/projects/{name}/orchestration/stop", handle_orch_stop)

    # Issues
    app.router.add_get("/api/projects/{name}/issues", handle_list_issues)
    app.router.add_get("/api/projects/{name}/issues/stats", handle_issue_stats)
    app.router.add_get("/api/projects/{name}/issues/audit", handle_issue_audit)
    app.router.add_post("/api/projects/{name}/issues", handle_create_issue)
    app.router.add_get("/api/projects/{name}/issues/{iid}", handle_get_issue)

    # Issue actions
    app.router.add_post("/api/projects/{name}/issues/{iid}/investigate", handle_action("investigate"))
    app.router.add_post("/api/projects/{name}/issues/{iid}/fix", handle_action("fix"))
    app.router.add_post("/api/projects/{name}/issues/{iid}/dismiss", handle_action("dismiss"))
    app.router.add_post("/api/projects/{name}/issues/{iid}/cancel", handle_action("cancel"))
    app.router.add_post("/api/projects/{name}/issues/{iid}/skip", handle_action("skip"))
    app.router.add_post("/api/projects/{name}/issues/{iid}/mute", handle_mute_action)
    app.router.add_post("/api/projects/{name}/issues/{iid}/extend-timeout", handle_extend_timeout)
    app.router.add_post("/api/projects/{name}/issues/{iid}/message", handle_issue_message)

    # Groups
    app.router.add_get("/api/projects/{name}/issues/groups", handle_list_groups)
    app.router.add_post("/api/projects/{name}/issues/groups", handle_create_group)
    app.router.add_post("/api/projects/{name}/issues/groups/{gid}/fix", handle_group_fix)

    # Mutes
    app.router.add_get("/api/projects/{name}/issues/mutes", handle_list_mutes)
    app.router.add_post("/api/projects/{name}/issues/mutes", handle_add_mute)
    app.router.add_delete("/api/projects/{name}/issues/mutes/{mid}", handle_delete_mute)

    # Cross-project
    app.router.add_get("/api/issues", handle_all_issues)
    app.router.add_get("/api/issues/stats", handle_all_stats)

    return app


# --- Helpers ---

def _get_service(request: web.Request) -> ServiceManager:
    return request.app["service"]


def _get_issue_manager(request: web.Request):
    service = _get_service(request)
    name = request.match_info["name"]
    mgr = service.issue_managers.get(name)
    if not mgr:
        raise web.HTTPNotFound(text=f"Project '{name}' not found")
    return mgr, name


def _json(data, status=200):
    return web.json_response(data, status=status)


# --- Service ---

async def handle_manager_status(request: web.Request):
    return _json(_get_service(request).status())


# --- Projects ---

async def handle_list_projects(request: web.Request):
    service = _get_service(request)
    projects = []
    for name, sup in service.supervisors.items():
        s = sup.status()
        mgr = service.issue_managers.get(name)
        if mgr:
            s["issue_stats"] = mgr.registry.stats()
        projects.append(s)
    return _json(projects)


async def handle_add_project(request: web.Request):
    data = await request.json()
    service = _get_service(request)
    service.add_project(
        name=data["name"],
        path=Path(data["path"]),
        mode=data.get("mode", "e2e"),
    )
    return _json({"status": "ok", "name": data["name"]}, status=201)


async def handle_remove_project(request: web.Request):
    name = request.match_info["name"]
    _get_service(request).remove_project(name)
    return _json({"status": "ok"})


async def handle_project_status(request: web.Request):
    name = request.match_info["name"]
    status = _get_service(request).project_status(name)
    if not status:
        raise web.HTTPNotFound(text=f"Project '{name}' not found")
    return _json(status)


# --- Sentinel/Orchestration control ---

async def handle_sentinel_start(request: web.Request):
    name = request.match_info["name"]
    sup = _get_service(request).supervisors.get(name)
    if not sup:
        raise web.HTTPNotFound()
    pid = sup.start_sentinel()
    return _json({"status": "ok", "pid": pid})


async def handle_sentinel_stop(request: web.Request):
    name = request.match_info["name"]
    sup = _get_service(request).supervisors.get(name)
    if not sup:
        raise web.HTTPNotFound()
    sup.stop_sentinel()
    return _json({"status": "ok"})


async def handle_sentinel_restart(request: web.Request):
    name = request.match_info["name"]
    sup = _get_service(request).supervisors.get(name)
    if not sup:
        raise web.HTTPNotFound()
    sup.stop_sentinel()
    pid = sup.start_sentinel()
    return _json({"status": "ok", "pid": pid})


async def handle_orch_start(request: web.Request):
    name = request.match_info["name"]
    sup = _get_service(request).supervisors.get(name)
    if not sup:
        raise web.HTTPNotFound()
    data = await request.json() if request.can_read_body else {}
    pid = sup.start_orchestration(plan_file=data.get("plan_file"))
    return _json({"status": "ok", "pid": pid})


async def handle_orch_stop(request: web.Request):
    name = request.match_info["name"]
    sup = _get_service(request).supervisors.get(name)
    if not sup:
        raise web.HTTPNotFound()
    sup.stop_orchestration()
    return _json({"status": "ok"})


# --- Issues ---

async def handle_list_issues(request: web.Request):
    mgr, name = _get_issue_manager(request)
    state = request.query.get("state")
    severity = request.query.get("severity")

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
    return _json([i.to_dict() for i in issues])


async def handle_get_issue(request: web.Request):
    mgr, name = _get_issue_manager(request)
    iid = request.match_info["iid"]
    issue = mgr.registry.get(iid)
    if not issue:
        raise web.HTTPNotFound(text=f"Issue {iid} not found")
    return _json(issue.to_dict())


async def handle_create_issue(request: web.Request):
    mgr, name = _get_issue_manager(request)
    data = await request.json()
    sup = _get_service(request).supervisors.get(name)
    issue = mgr.register(
        source="user",
        error_summary=data.get("error_summary", ""),
        error_detail=data.get("error_detail", ""),
        environment=name,
        environment_path=str(sup.config.path) if sup else "",
    )
    if not issue:
        return _json({"status": "duplicate"}, status=200)
    return _json(issue.to_dict(), status=201)


async def handle_issue_stats(request: web.Request):
    mgr, name = _get_issue_manager(request)
    return _json(mgr.registry.stats())


async def handle_issue_audit(request: web.Request):
    mgr, name = _get_issue_manager(request)
    since = request.query.get("since")
    limit = int(request.query.get("limit", "200"))
    issue_id = request.query.get("issue_id")
    entries = mgr.audit.read(
        since=float(since) if since else None,
        limit=limit,
        issue_id=issue_id,
    )
    return _json(entries)


# --- Issue actions ---

def handle_action(action_name: str):
    async def handler(request: web.Request):
        mgr, name = _get_issue_manager(request)
        iid = request.match_info["iid"]
        try:
            method = getattr(mgr, f"action_{action_name}")
            data = await request.json() if request.can_read_body else {}
            if action_name == "skip":
                method(iid, reason=data.get("reason", ""))
            else:
                method(iid)
            return _json({"status": "ok"})
        except ValueError as e:
            raise web.HTTPNotFound(text=str(e))
        except Exception as e:
            if "Cannot transition" in str(e):
                raise web.HTTPConflict(text=str(e))
            raise
    return handler


async def handle_mute_action(request: web.Request):
    mgr, name = _get_issue_manager(request)
    iid = request.match_info["iid"]
    data = await request.json() if request.can_read_body else {}
    try:
        mgr.action_mute(iid, pattern=data.get("pattern"))
        return _json({"status": "ok"})
    except ValueError as e:
        raise web.HTTPNotFound(text=str(e))
    except Exception as e:
        if "Cannot transition" in str(e):
            raise web.HTTPConflict(text=str(e))
        raise


async def handle_extend_timeout(request: web.Request):
    mgr, name = _get_issue_manager(request)
    iid = request.match_info["iid"]
    data = await request.json()
    try:
        mgr.action_extend_timeout(iid, extra_seconds=int(data.get("seconds", 300)))
        return _json({"status": "ok"})
    except ValueError as e:
        raise web.HTTPNotFound(text=str(e))
    except Exception as e:
        if "Cannot transition" in str(e) or "only extend" in str(e).lower():
            raise web.HTTPConflict(text=str(e))
        raise


async def handle_issue_message(request: web.Request):
    mgr, name = _get_issue_manager(request)
    iid = request.match_info["iid"]
    data = await request.json()
    message = data.get("message", "")
    # Message relay — store in audit for timeline
    mgr.audit.log(iid, "user_message", content=message)
    return _json({"status": "ok"})


# --- Groups ---

async def handle_list_groups(request: web.Request):
    mgr, name = _get_issue_manager(request)
    return _json([g.to_dict() for g in mgr.registry.all_groups()])


async def handle_create_group(request: web.Request):
    mgr, name = _get_issue_manager(request)
    data = await request.json()
    group = mgr.action_group(
        issue_ids=data["issue_ids"],
        name=data["name"],
        reason=data.get("reason", ""),
    )
    return _json(group.to_dict(), status=201)


async def handle_group_fix(request: web.Request):
    mgr, name = _get_issue_manager(request)
    gid = request.match_info["gid"]
    group = mgr.registry.get_group(gid)
    if not group:
        raise web.HTTPNotFound(text=f"Group {gid} not found")
    # Trigger fix for the group's primary issue
    mgr.action_fix(group.primary_issue)
    return _json({"status": "ok"})


# --- Mutes ---

async def handle_list_mutes(request: web.Request):
    mgr, name = _get_issue_manager(request)
    return _json([m.to_dict() for m in mgr.registry.all_mutes()])


async def handle_add_mute(request: web.Request):
    mgr, name = _get_issue_manager(request)
    data = await request.json()
    mute = mgr.registry.add_mute(
        pattern=data["pattern"],
        reason=data.get("reason", ""),
        expires_at=data.get("expires_at"),
    )
    return _json(mute.to_dict(), status=201)


async def handle_delete_mute(request: web.Request):
    mgr, name = _get_issue_manager(request)
    mid = request.match_info["mid"]
    mgr.registry.remove_mute(mid)
    return _json({"status": "ok"})


# --- Cross-project ---

async def handle_all_issues(request: web.Request):
    service = _get_service(request)
    all_issues = []
    for name, mgr in service.issue_managers.items():
        for issue in mgr.registry.all_issues():
            all_issues.append(issue.to_dict())
    all_issues.sort(key=lambda i: i["detected_at"], reverse=True)
    return _json(all_issues)


async def handle_all_stats(request: web.Request):
    service = _get_service(request)
    return _json({
        name: mgr.registry.stats()
        for name, mgr in service.issue_managers.items()
    })
