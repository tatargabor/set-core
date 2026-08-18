"""Fleet API — the agent sessions running on this machine.

    GET  /api/fleet/agents             — every live agent, its project, and its measured state
    GET  /api/fleet/agents/{pid}/log   — the raw conversation of one agent (design §5.8)
    GET  /api/fleet/owner              — whether an agent can be started at all
    POST /api/fleet/agents             — start one, through the agent owner (task 5.8)
    POST /api/fleet/agents/{label}/stop — stop one this framework started

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
import os
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..fleet import discover_agents, discover_projects, read_state
from ..fleet.conversation import read_conversation
from ..fleet.owner_client import OwnerClient, OwnerClientError, OwnerUnavailable
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


# --------------------------------------------------------------------------- #
# Starting and stopping — through the owner, never from this process (task 5.8)
# --------------------------------------------------------------------------- #

class StartAgentBody(BaseModel):
    """What the screen may ask for.

    Narrower than what the owner's socket accepts, on purpose. The socket takes
    an `argv`; this endpoint does not, because an HTTP route that runs an
    arbitrary command list is a different thing from a button that starts an
    agent, and only the second one was asked for. Task 5.10 will add the engine's
    entry point as its own, separately-labelled act — that is where a second kind
    of start belongs, not in a free-form parameter here.
    """

    label: str
    cwd: str
    rows: int = 40
    cols: int = 120


def _known_roots() -> set:
    """Directories the screen can actually see an agent in.

    A start is refused outside this set. Not because a local dashboard is
    exposed, but because *not* choosing here chooses the permissive option
    silently: an endpoint that accepts any existing directory runs an agent
    anywhere on the machine, and nothing on the screen ever offers that.
    """
    roots = set()
    try:
        for entry in _load_projects():
            root = entry.get("path") or entry.get("root")
            if root:
                roots.add(os.path.realpath(root))
    except Exception as exc:
        logger.warning("fleet api: project registry unreadable while validating cwd: %s", exc)
    for agent in discover_agents(include_oneshot=True):
        if agent.project_root:
            roots.add(os.path.realpath(agent.project_root))
    return roots


@router.get("/api/fleet/owner")
def fleet_owner() -> Dict[str, Any]:
    """Whether an agent can be started at all, and if not, what to run.

    The screen asks this before it offers a start. A button that is present and
    fails is worse than one that is absent with a reason next to it — and the
    reason here is always the same repair, so withholding it would be a choice
    to make the reader guess.
    """
    try:
        health = OwnerClient().health()
    except OwnerUnavailable as exc:
        return {"available": False, "reason": str(exc)}
    except OwnerClientError as exc:
        return {"available": False, "reason": str(exc)}
    return {"available": True, **health}


@router.post("/api/fleet/agents")
def fleet_start_agent(body: StartAgentBody) -> Dict[str, Any]:
    """Start an agent through the owner service.

    This process never forks the agent itself. The dashboard runs with
    `KillMode=control-group` and restarts on every deploy, so an agent started
    here would join its control group and die with it (finding CB-1) — the
    defect the owner service exists to remove. A `503` when the owner is down is
    therefore the correct answer and not a degraded one: there is no local
    fallback that would not reintroduce the bug.
    """
    cwd = os.path.realpath(os.path.expanduser(body.cwd))
    if not os.path.isdir(cwd):
        raise HTTPException(status_code=400, detail=f"no such directory: {body.cwd}")
    if cwd not in _known_roots():
        raise HTTPException(
            status_code=400,
            detail=f"{cwd} is not a project this screen knows; register it first",
        )
    try:
        agent = OwnerClient().start(label=body.label, cwd=cwd, rows=body.rows, cols=body.cols)
    except OwnerUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OwnerClientError as exc:
        # The owner refused — a label already held, a scope already running. A
        # refusal is the caller's answer, not a server fault.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    logger.info("fleet api: started agent %s in %s (pid %s)", agent["label"], cwd, agent.get("pid"))
    return agent


@router.post("/api/fleet/agents/{label}/stop")
def fleet_stop_agent(label: str) -> Dict[str, Any]:
    """Stop an agent the framework started. Never a consequence of closing a view.

    Addressed by label rather than by pid: the pid is what the *scope* currently
    holds and a pid is reused, while the label is what the framework named. The
    owner refuses anything it does not hold, so a foreign session cannot be
    stopped through this route at all.
    """
    try:
        result = OwnerClient().stop(label)
    except OwnerUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OwnerClientError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    logger.info("fleet api: stopped agent %s (gone=%s)", label, result.get("gone"))
    return result
