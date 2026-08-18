"""Fleet API — the agent sessions running on this machine.

    GET /api/fleet/agents            — every live agent, its project, and its measured state
    GET /api/fleet/agents/{pid}/log  — the raw conversation of one agent (design §5.8)

⚠ Route ordering matters and is not cosmetic (finding CB-16). The dashboard
already serves a large `/api/{project}/...` family, and FastAPI resolves routes
in registration order, so a wildcard registered first would swallow
`/api/fleet/...` and answer it as a project named "fleet". This router is
therefore included **before** the project routers in `api/__init__.py`, and the
unit test `test_fleet_api.py` fails if that ordering is lost.

Nothing derived from a session's *content* is returned or logged — only its
identity, its project, and a state derived from structure (which tool is
outstanding, how long the log has been quiet). The confidentiality boundary in
CLAUDE.md is a persistence boundary, and this endpoint persists nothing at all.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from ..fleet import discover_agents, discover_projects, read_state
from ..fleet.conversation import read_conversation
from .helpers import _load_projects

logger = logging.getLogger(__name__)

router = APIRouter()


def _agent_payload(agent, state) -> Dict[str, Any]:
    return {
        "pid": agent.pid,
        "name": agent.name,
        "project": agent.project_name,
        "project_root": agent.project_root,
        "cwd": agent.cwd,
        "branch": agent.branch,
        "session_id": agent.session_id,
        # A binding that came from a record, not a guess. The surface shows an
        # unconfirmed binding as a guess; there is currently no guessing path.
        "binding_confirmed": agent.binding_confirmed,
        "sources": agent.sources,
        "kind": agent.kind,
        "state": state.state,
        "tool": state.tool,
        "tool_elapsed_seconds": state.tool_elapsed,
        "other_tools": state.other_tools,
        "last_movement_seconds": state.last_movement_age,
        # Present only when the state could not be determined. Its absence is
        # meaningful: it means the state IS determined.
        "unknown_reason": state.reason,
    }


@router.get("/api/fleet/agents")
def fleet_agents(include_oneshot: bool = Query(False)) -> Dict[str, Any]:
    """Every live agent session, grouped by project.

    `include_oneshot` surfaces the framework's own short-lived subprocesses,
    which are excluded by default: they run with a project as their working
    directory and would otherwise appear as sessions that finished their turn
    (finding CB-8).
    """
    try:
        registered = _load_projects()
    except Exception as exc:  # a missing registry must not empty the fleet
        logger.warning("fleet api: project registry unreadable: %s", exc)
        registered = []

    agents = discover_agents(include_oneshot=include_oneshot)
    projects = discover_projects(agents, registered=registered)

    states = {agent.pid: read_state(agent.session_log) for agent in agents}
    by_pid = {agent.pid: agent for agent in agents}

    grouped: List[Dict[str, Any]] = []
    for project in projects:
        members = [by_pid[pid] for pid in project.agent_pids if pid in by_pid]
        if not members and "registry" not in project.sources:
            continue
        grouped.append({
            "name": project.name,
            "root": project.root,
            "sources": project.sources,
            "archived": project.archived,
            "agents": [_agent_payload(a, states[a.pid]) for a in members],
        })

    # Counted from the data, never from a declaration — a "hidden" tally taken
    # from what we *meant* to filter is the false-absence class.
    working = sum(1 for s in states.values() if s.state == "working")
    unknown = sum(1 for s in states.values() if s.state == "unknown")

    return {
        "agents": len(agents),
        "working": working,
        "unknown": unknown,
        "projects": grouped,
        # Why a quiet agent may in fact be mid-turn. Measured 2026-08-18: the
        # runtime flushes a turn's entries to the session log in batches, and a
        # log was observed ~25s stale while its session was actively working.
        # The surface must not present `quiet` as "nothing is happening".
        "quiet_means": "no outstanding tool call as of the session log's last flush",
    }


@router.get("/api/fleet/agents/{pid}/log")
def fleet_agent_log(pid: int, limit: int = Query(60, ge=1, le=500)) -> Dict[str, Any]:
    """The raw conversation of one agent — design §5.8.

    The full parse lives here rather than in the listing path, and runs only
    because someone opened a tile (task 6.2). The agent is re-discovered by pid
    rather than trusted from the caller: a pid is reused, and answering with
    whatever log a stale pid maps to would serve one session's conversation
    under another's name.
    """
    agents = {a.pid: a for a in discover_agents(include_oneshot=True)}
    agent = agents.get(pid)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"no live agent with pid {pid}")

    payload = read_conversation(agent.session_log, limit=limit)
    payload["pid"] = agent.pid
    payload["name"] = agent.name
    payload["project"] = agent.project_name
    payload["binding_confirmed"] = agent.binding_confirmed
    return payload
