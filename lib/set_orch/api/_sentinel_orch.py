"""Sentinel orchestration endpoints (events, findings, status) — from old api.py."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .helpers import _resolve_project, _sentinel_dir, _state_path

router = APIRouter()

@router.get("/api/{project}/sentinel/events")
async def sentinel_events(project: str, since: Optional[float] = None):
    """Read sentinel events from .set/sentinel/events.jsonl.

    Returns [] when file does not exist.
    """
    pp = _resolve_project(project)
    events_file = _sentinel_dir(pp) / "events.jsonl"
    if not events_file.exists():
        return []

    events = []
    with open(events_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since and event.get("epoch", 0) <= since:
                continue
            events.append(event)

    # Return last 500 events max
    if len(events) > 500:
        events = events[-500:]
    return events


@router.get("/api/{project}/sentinel/findings")
async def sentinel_findings(project: str):
    """Read sentinel findings from .set/sentinel/findings.json.

    Returns {findings:[], assessments:[]} when file does not exist.
    """
    pp = _resolve_project(project)
    findings_file = _sentinel_dir(pp) / "findings.json"
    if not findings_file.exists():
        return {"findings": [], "assessments": []}

    try:
        with open(findings_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"findings": [], "assessments": []}


@router.get("/api/{project}/sentinel/status")
async def sentinel_status(project: str):
    """Read sentinel status from .set/sentinel/status.json.

    Returns {active: false} when file does not exist.
    Adds computed is_active field (true if active and last_event_at within 60s).
    Surfaces `permanent_error` from the supervisor daemon when the daemon
    halted due to a deterministic failure (spec typo, missing binary, etc.).
    """
    pp = _resolve_project(project)
    status_file = _sentinel_dir(pp) / "status.json"
    if not status_file.exists():
        data: dict = {"active": False, "is_active": False}
    else:
        try:
            with open(status_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {"active": False, "is_active": False}

        # Compute is_active: active + recent heartbeat
        is_active = False
        if data.get("active"):
            last = data.get("last_event_at", "")
            if last:
                try:
                    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - last_dt).total_seconds()
                    is_active = age < 60
                except (ValueError, TypeError):
                    pass
        data["is_active"] = is_active

    # Read supervisor status for permanent_error surfacing. Only surface
    # the machine-readable reason code — the raw stderr tail contains
    # tracebacks, environment variables, and CLI args that may leak
    # internal paths or secrets to unauthenticated clients.
    sup_status_file = pp / ".set" / "supervisor" / "status.json"
    if sup_status_file.is_file():
        try:
            with open(sup_status_file) as f:
                sup_data = json.load(f)
            perm = sup_data.get("permanent_error")
            if isinstance(perm, dict) and perm.get("code"):
                data["permanent_error"] = {"code": perm["code"]}
            if sup_data.get("stop_reason", "").startswith("permanent_error:"):
                data.setdefault("stop_reason", sup_data["stop_reason"])
        except (json.JSONDecodeError, OSError):
            pass
    return data


from pydantic import BaseModel


class SentinelMessageBody(BaseModel):
    message: str


@router.post("/api/{project}/sentinel/message")
async def send_sentinel_message(project: str, body: SentinelMessageBody):
    """Send a message to the sentinel via its local inbox file."""
    pp = _resolve_project(project)
    sentinel_dir = _sentinel_dir(pp)
    sentinel_dir.mkdir(parents=True, exist_ok=True)

    inbox_file = sentinel_dir / "inbox.jsonl"
    msg = {
        "from": "set-web",
        "content": body.message,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    with open(inbox_file, "a") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    return {"status": "sent"}


@router.post("/api/{project}/completion")
async def completion_action(project: str, body: dict):
    """Send a completion action to the sentinel via inbox.

    Body: {"action": "accept|rerun|newspec", "spec": "docs/v2.md"}
    """
    action = body.get("action", "accept")
    if action not in ("accept", "rerun", "newspec"):
        return JSONResponse({"error": "Invalid action"}, status_code=400)

    pp = _resolve_project(project)
    sentinel_dir = _sentinel_dir(pp)
    sentinel_dir.mkdir(parents=True, exist_ok=True)

    inbox_file = sentinel_dir / "inbox.jsonl"
    msg = {
        "type": "completion_action",
        "action": action,
        "spec": body.get("spec", ""),
        "from": "set-web",
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    with open(inbox_file, "a") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    # Accept action: transition state to 'accepted' so the UI stops showing the banner
    if action == "accept":
        state_file = pp / "orchestration-state.json"
        if state_file.exists():
            import fcntl
            try:
                with open(state_file, "r+") as sf:
                    fcntl.flock(sf, fcntl.LOCK_EX)
                    state = json.load(sf)
                    if state.get("status") == "done":
                        state["status"] = "accepted"
                        sf.seek(0)
                        sf.truncate()
                        json.dump(state, sf, ensure_ascii=False, indent=2)
                    fcntl.flock(sf, fcntl.LOCK_UN)
            except Exception:
                pass  # non-critical — banner just stays visible

    return {"status": "sent", "action": action}


