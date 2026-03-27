"""Project list and CRUD routes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

from .helpers import (
    PROJECTS_FILE,
    _load_projects,
    _save_projects,
    _quick_status,
    _resolve_project,
    _state_path,
)

router = APIRouter()


@router.get("/api/projects")
def list_projects():
    """List all registered projects with quick status and last_updated."""
    projects = _load_projects()
    result = []
    for p in projects:
        path = Path(p.get("path", ""))
        entry: dict = {
            "name": p.get("name", path.name),
            "path": str(path),
            "has_orchestration": _state_path(path).exists() if path.is_dir() else False,
            "status": _quick_status(path) if path.is_dir() else "error",
            "last_updated": None,
        }
        # Use state file mtime if it exists, otherwise project dir mtime
        if path.is_dir():
            sp = _state_path(path)
            try:
                if sp.exists():
                    entry["last_updated"] = datetime.fromtimestamp(
                        sp.stat().st_mtime, tz=timezone.utc
                    ).isoformat()
                    # Read summary stats from state
                    try:
                        state_data = json.loads(sp.read_text())
                        changes = state_data.get("changes", [])
                        total = len(changes)
                        merged = sum(1 for c in changes if c.get("status") == "merged")
                        total_tokens = sum(c.get("tokens_used", 0) or 0 for c in changes)
                        active_secs = state_data.get("active_seconds", 0) or 0
                        entry["changes_merged"] = merged
                        entry["changes_total"] = total
                        entry["total_tokens"] = total_tokens
                        entry["active_seconds"] = active_secs
                    except (json.JSONDecodeError, OSError):
                        pass
                else:
                    entry["last_updated"] = datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc
                    ).isoformat()
            except OSError:
                pass
            # Issue stats from registry
            registry_file = path / ".set" / "issues" / "registry.json"
            if registry_file.exists():
                try:
                    reg = json.loads(registry_file.read_text())
                    issues = reg.get("issues", [])
                    open_states = {"new", "investigating", "diagnosed", "awaiting_approval", "fixing", "verifying", "deploying"}
                    open_count = sum(1 for i in issues if i.get("state") in open_states)
                    entry["issues_open"] = open_count
                    entry["issues_total"] = len(issues)
                except (json.JSONDecodeError, OSError):
                    pass
        result.append(entry)
    return result


@router.post("/api/projects")
def add_project(body: dict):
    """Register a new project."""
    name = body.get("name", "")
    path = body.get("path", "")
    if not name or not path:
        from fastapi import HTTPException
        raise HTTPException(400, "name and path required")
    projects = _load_projects()
    # Check duplicate
    if any(p["name"] == name for p in projects):
        return {"status": "exists", "name": name}
    projects.append({
        "name": name,
        "path": path,
        "addedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project_type": body.get("project_type", body.get("mode", "")),
    })
    _save_projects(projects)
    # Register with lifecycle service (supervisor + issue manager)
    from .lifecycle import get_service
    svc = get_service()
    if svc:
        from pathlib import Path as _P
        svc.add_project(name, _P(path), mode=body.get("mode", "e2e"))
    return {"status": "ok", "name": name}


@router.delete("/api/projects/{name}")
def remove_project(name: str):
    """Remove a registered project."""
    projects = _load_projects()
    projects = [p for p in projects if p["name"] != name]
    _save_projects(projects)
    from .lifecycle import get_service
    svc = get_service()
    if svc:
        svc.remove_project(name)
    return {"status": "ok"}


@router.get("/api/projects/{name}/status")
def get_project_status(name: str):
    """Get detailed status for a single project including sentinel/orchestrator info."""
    pp = _resolve_project(name)
    sp = _state_path(pp)
    status = _quick_status(pp)
    result: dict = {"name": name, "path": str(pp), "status": status, "mode": "e2e"}
    if sp.exists():
        try:
            state_data = json.loads(sp.read_text())
            changes = state_data.get("changes", [])
            result["changes_merged"] = sum(1 for c in changes if c.get("status") == "merged")
            result["changes_total"] = len(changes)
            result["active_seconds"] = state_data.get("active_seconds", 0) or 0
            result["orchestrator"] = {
                "pid": state_data.get("orchestrator_pid"),
                "alive": _is_pid_alive(state_data.get("orchestrator_pid")),
            }
        except (json.JSONDecodeError, OSError):
            pass

    # Sentinel info from lifecycle service
    from .lifecycle import get_service
    svc = get_service()
    sup = svc.supervisors.get(name) if svc else None
    if sup:
        sup_status = sup.status()
        result["sentinel"] = sup_status.get("sentinel", {"pid": None, "alive": False, "started_at": None, "spec": None, "crash_count": 0})
    else:
        result["sentinel"] = {"pid": None, "alive": False, "started_at": None, "spec": None, "crash_count": 0}

    if "orchestrator" not in result:
        result["orchestrator"] = {"pid": None, "alive": False}

    # Issue stats
    mgr = svc.issue_managers.get(name) if svc else None
    if mgr:
        result["issue_stats"] = mgr.registry.stats()

    return result


def _is_pid_alive(pid) -> bool:
    if not pid:
        return False
    try:
        import os
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, PermissionError, TypeError, ValueError):
        return False
