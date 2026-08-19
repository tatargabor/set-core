"""Fleet API — the agent sessions running on this machine.

    GET  /api/fleet/agents             — every live agent, its project, and its measured state
    GET  /api/fleet/agents/{pid}/state — one agent's measured state, without the fleet
    GET  /api/fleet/agents/{pid}/log   — the raw conversation of one agent (design §5.8)
    GET  /api/fleet/owner              — whether an agent can be started at all
    POST /api/fleet/agents             — start one, through the agent owner (task 5.8)
    POST /api/fleet/agents/{label}/stop — stop one this framework started
    GET  /api/fleet/layout             — the hand-made arrangement, joined to what exists
    PUT  /api/fleet/layout             — replace it, refusing a stale write
    WS   /ws/fleet/agents/{label}/terminal — the terminal, both directions (5.3, 6.4)

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

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..fleet import discover_agents, discover_projects, read_state
from ..fleet.discovery import discover_agent, parent_seat
from ..fleet.conversation import read_conversation
from ..fleet import layout as fleet_layout
from ..fleet.layout import LayoutConflict
from ..fleet.owner_client import (
    OwnerClient, OwnerClientError, OwnerStream, OwnerUnavailable,
)
from .helpers import _load_projects

logger = logging.getLogger(__name__)

router = APIRouter()


def _owned_by_pid() -> Optional[Dict[int, Dict[str, Any]]]:
    """What the owner is holding, keyed by pid — or None when it cannot be asked.

    `None` is the important value and it is not the same as `{}`. An empty
    mapping means the owner answered and holds nothing; `None` means nobody
    answered, and the difference decides what the surface may say. Reporting
    every agent as `foreign` because the owner is down would be true by accident
    and false as a claim — the framework may well have started one.
    """
    try:
        return {a["pid"]: a for a in OwnerClient().list_agents() if a.get("pid")}
    except OwnerClientError as exc:
        logger.debug("fleet api: the owner could not be asked what it holds: %s", exc)
        return None


def _agent_payload(agent, state, owned: Optional[Dict[int, Dict[str, Any]]] = None) -> Dict[str, Any]:
    # Three values, not two, and the third is why this is not a boolean. A
    # terminal exists only for a process the framework started and still holds
    # (task 5.2), so:
    #   started-here  the owner holds this pty; it can be typed into
    #   foreign       nobody here holds it; there is no terminal and cannot be
    #   unknown       the owner could not be asked, so we do not know which
    # Collapsing `unknown` into `foreign` would let the screen say "no terminal"
    # about an agent that has one, whenever the owner is merely restarting.
    if owned is None:
        population, terminal_label = "unknown", None
    elif agent.pid in owned:
        population, terminal_label = "started-here", owned[agent.pid].get("label")
    else:
        population, terminal_label = "foreign", None

    requested_by = (owned or {}).get(agent.pid, {}).get("requested_by")
    parent = (
        {"seat": requested_by, "source": "recorded"} if requested_by
        else parent_seat(agent.pid)
    )
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
        # Which sources were asked and did not know. A shorter `sources` list is
        # only meaningful against the set that was consulted: without this,
        # "known to one source" and "known to one of three" render identically,
        # and the second is the one worth looking at.
        "sources_missing": agent.sources_missing,
        "kind": agent.kind,
        "state": state.state,
        "tool": state.tool,
        "tool_elapsed_seconds": state.tool_elapsed,
        "other_tools": state.other_tools,
        "last_movement_seconds": state.last_movement_age,
        # Present only when the state could not be determined. Its absence is
        # meaningful: it means the state IS determined.
        "unknown_reason": state.reason,
        # What the agent says it is waiting for, verbatim from the runtime's
        # record. Present only for `waiting`; the log cannot produce this.
        "waiting_for": state.waiting_for,
        # Set when the record declared a state the log contradicts. Carried
        # rather than dropped: a contradiction the surface cannot see is one
        # nobody will ever fix.
        "declaration_ignored": state.declaration_ignored,
        # The last thing said in this session — task 7.3, so the tile answers
        # "what is going on" without being opened.
        #
        # ⚠ Read at request time and never written down: this is verbatim
        # content from a session that may be running in a consumer project, and
        # CLAUDE.md's boundary is persistence, not display. It must not reach a
        # log line, a cache, a memory or a committed artifact.
        "excerpt": state.excerpt,
        "excerpt_from": state.excerpt_from,
        # Which population this agent belongs to, as a CARRIED fact rather than
        # something the surface infers (task 5.1). A terminal is attachable only
        # for `started-here`, and only under the label named here.
        "population": population,
        "terminal_label": terminal_label,
        # Who started this agent, and WHICH KIND of answer it is. The recorded
        # one wins when present because it is the only one that can answer for a
        # framework-started agent at all — measured: those have the owner, a
        # plain python process, as their parent. `source` is carried so the
        # surface can mark the recorded one as a claim and the ancestry one as
        # measured; they answer different questions and can disagree.
        "parent": parent,
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

    states = {agent.pid: read_state(agent.session_log, record=agent.record) for agent in agents}
    by_pid = {agent.pid: agent for agent in agents}
    # Asked once for the whole listing, not once per agent: it is one socket
    # round trip and the answer is the same for every row.
    owned = _owned_by_pid()

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
            "agents": [_agent_payload(a, states[a.pid], owned) for a in members],
        })

    # Counted from the data, never from a declaration — a "hidden" tally taken
    # from what we *meant* to filter is the false-absence class.
    working = sum(1 for s in states.values() if s.state == "working")
    unknown = sum(1 for s in states.values() if s.state == "unknown")
    # Counted from the data. Present even when zero, and that is the point:
    # the KEY is what tells the surface the state is reported at all. Without
    # it a screen cannot distinguish "nobody is waiting" from "waiting is not
    # measured here", and it would have to render one as the other.
    waiting = sum(1 for s in states.values() if s.state == "waiting")

    return {
        "agents": len(agents),
        "working": working,
        "unknown": unknown,
        "waiting": waiting,
        "projects": grouped,
        # Why a quiet agent may in fact be mid-turn. Measured 2026-08-18: the
        # runtime flushes a turn's entries to the session log in batches, and a
        # log was observed ~25s stale while its session was actively working.
        # The surface must not present `quiet` as "nothing is happening".
        "quiet_means": "no outstanding tool call as of the session log's last flush",
        # Said once at the top rather than repeated as a reason on every row: a
        # screen that cannot offer a terminal ANYWHERE has one cause, and naming
        # it once is the difference between "no terminals" and "we could not ask".
        "owner_reachable": owned is not None,
    }


@router.get("/api/fleet/agents/{pid}/log")
def fleet_agent_log(pid: int, limit: int = Query(60, ge=1, le=500)) -> Dict[str, Any]:
    """The raw conversation of one agent — design §5.8.

    The full parse lives here rather than in the listing path, and runs only
    because someone opened a tile (task 6.2). The agent is re-discovered by pid
    rather than trusted from the caller: a pid is reused, and answering with
    whatever log a stale pid maps to would serve one session's conversation
    under another's name.

    ⚠ It used to re-discover the WHOLE FLEET to find one pid, and the surface
    polls an open log every 5 seconds. `discover_agents()` asks git for the
    project root and the branch of every agent — two subprocesses each — so one
    log view cost ~44 of them. Measured 2026-08-19: **202 ms for the fleet
    against 3.5 ms for one agent, 58x**. Task 6.2's rule read the other way
    round: reading one log must not list every agent.
    """
    agent = discover_agent(pid)
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
    #: Who asked, as a seat identity. Optional and recorded verbatim — the
    #: framework does not verify it, and the surface must present it as a claim
    #: rather than as a measured relation.
    requested_by: Optional[str] = None


def _safe_registry() -> List[Dict[str, Any]]:
    """The registered projects, or none. A missing registry must not empty the fleet."""
    try:
        return _load_projects()
    except Exception as exc:
        logger.warning("fleet api: project registry unreadable: %s", exc)
        return []


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
        agent = OwnerClient().start(
            label=body.label, cwd=cwd, rows=body.rows, cols=body.cols,
            requested_by=body.requested_by,
        )
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
    holds and a pid is reused, while the label is what the framework named.

    The owner answers with what it actually FOUND, and the three cases are
    different acts rather than shades of one: an agent it holds, an **orphan**
    (a framework scope whose terminal died with a previous owner — stopping that
    is the first half of recovery), and nothing at all, which is a 404. A session
    the framework never started has no scope of this name, so it cannot be
    reached through this route in any of the three.

    ⚠ An earlier version of this docstring said the owner "refuses anything it
    does not hold". It did not — measured 2026-08-18, stopping a label that had
    never existed answered `{"gone": true}` with a 200. The prose was the only
    place the guarantee existed, which is the same defect this module's route
    ordering had.
    """
    try:
        result = OwnerClient().stop(label)
    except OwnerUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OwnerClientError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    # A stop that stopped nothing is a 404, never a success: the screen would
    # otherwise confirm that an agent had been stopped when there had never
    # been one.
    if not result.get("found"):
        raise HTTPException(status_code=404, detail=f"no agent named {label} is running")

    logger.info(
        "fleet api: stopped agent %s (%s, gone=%s)",
        label, result.get("population"), result.get("gone"),
    )
    return result


# --------------------------------------------------------------------------- #
# The arrangement — groups, order, parked (D-2, decided 2026-08-19)
# --------------------------------------------------------------------------- #

class LayoutBody(BaseModel):
    """A whole arrangement, replaced at once.

    Whole-document rather than per-move, because a drag is not one edit: moving a
    project changes the position of everything after it, and a per-move API would
    have to describe that as a sequence the client could interleave wrongly.
    `base_version` is what makes replacing safe — see the route.
    """

    groups: List[Dict[str, Any]] = []
    parked: List[str] = []
    #: The unassigned block's order. A preference, not a membership: a name here
    #: that later joins a group is dropped rather than tracked in two places.
    ungrouped_order: List[str] = []
    base_version: Optional[int] = None


@router.get("/api/fleet/layout")
def fleet_get_layout() -> Dict[str, Any]:
    """The stored arrangement, JOINED to what discovery actually found.

    The join is the point, and it is what keeps a hand-made arrangement from
    quietly becoming the inventory. A project the user arranged that no longer
    runs anywhere comes back under `missing` rather than simply not rendering; a
    project that exists but was never arranged comes back under `ungrouped`
    rather than falling out of the screen. Neither silence would look like an
    error to anyone.
    """
    stored = fleet_layout.load()
    names = [p.name for p in discover_projects(discover_agents(include_oneshot=False),
                                               registered=_safe_registry())]
    return fleet_layout.apply_to(stored, names)


@router.put("/api/fleet/layout")
def fleet_put_layout(body: LayoutBody) -> Dict[str, Any]:
    """Replace the arrangement, refusing a write based on a version you no longer hold.

    Optimistic concurrency rather than last-write-wins, because what is being
    overwritten is hand-made and two dashboard tabs are ordinary. The loser of a
    silent race would find an arrangement they never made, with no event to
    explain it and no way back — so a stale write is a 409 the client can
    resolve, not a success nobody notices.
    """
    try:
        saved = fleet_layout.save(
            {"groups": body.groups, "parked": body.parked,
             "ungrouped_order": body.ungrouped_order},
            base_version=body.base_version,
        )
    except LayoutConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OSError as exc:
        logger.error("fleet api: cannot write the arrangement: %s", exc)
        raise HTTPException(status_code=500, detail=f"cannot write the arrangement: {exc}") from exc

    names = [p.name for p in discover_projects(discover_agents(include_oneshot=False),
                                               registered=_safe_registry())]
    return fleet_layout.apply_to(saved, names)


@router.get("/api/fleet/agents/{pid}/state")
def fleet_agent_state(pid: int) -> Dict[str, Any]:
    """One agent's measured state, without touching the rest of the fleet (task 6.2).

    The listing endpoint already carries state for every agent, and that is the
    right shape for a list. This exists for the other motion: a tile that is open
    and refreshing, which would otherwise re-measure 22 agents to redraw one.

    `unknown_reason` is present only when the state could NOT be determined, and
    its absence is meaningful — it means the state IS determined. A state field
    that always carries a reason string teaches the reader to ignore it.
    """
    agent = discover_agent(pid)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"no live agent with pid {pid}")

    state = read_state(agent.session_log, record=agent.record)
    return {
        "pid": agent.pid,
        "name": agent.name,
        "session_id": agent.session_id,
        "binding_confirmed": agent.binding_confirmed,
        "sources": agent.sources,
        # Which sources were asked and did not know. A shorter `sources` list is
        # only meaningful against the set that was consulted: without this,
        # "known to one source" and "known to one of three" render identically,
        # and the second is the one worth looking at.
        "sources_missing": agent.sources_missing,
        "state": state.state,
        "tool": state.tool,
        "tool_elapsed_seconds": state.tool_elapsed,
        "other_tools": state.other_tools,
        "last_movement_seconds": state.last_movement_age,
        "unknown_reason": state.reason,
        "waiting_for": state.waiting_for,
        "declaration_ignored": state.declaration_ignored,
        # Repeated from the listing on purpose: a caller polling this endpoint
        # alone would otherwise have no way to learn that a quiet agent may be
        # mid-turn, and would present `quiet` as "nothing is happening".
        "quiet_means": "no outstanding tool call as of the session log's last flush",
    }


# --------------------------------------------------------------------------- #
# The terminal, both directions (tasks 5.3 and 6.4)
# --------------------------------------------------------------------------- #

@router.websocket("/ws/fleet/agents/{label}/terminal")
async def fleet_terminal(websocket: WebSocket, label: str) -> None:
    """Relay one framework-owned terminal to a browser, in both directions.

    **Wire shape, and the split is deliberate.** Terminal bytes travel as BINARY
    frames in both directions; control travels as JSON text. Terminal output is
    not text — a read can end mid-UTF-8, which is ordinary on a pty — so carrying
    it as a string would force a lossy decode at the boundary, silently, in the
    direction that looks like data. Control messages are structured and rare, so
    they pay for JSON without anyone noticing.

        server → browser   binary  raw terminal output
                           text    {"event": "attached"|"ended", ...}
        browser → server   binary  keystrokes, verbatim
                           text    {"resize": {"rows": n, "cols": n}}

    **Nothing is persisted** (task 5.3): bytes pass through and are not written
    down, cached, or logged. The diagnostics below name the stream and the
    failure kind only — never a byte of what crossed it.

    **This is not the agent's lifetime.** Closing the view detaches; it never
    stops the agent (task 5.4). The owner keeps holding the pty, and another
    viewer — or the same one, later — attaches to the same terminal and is sent
    the buffered tail so its first screen is the screen as it already is.
    """
    await websocket.accept()
    stream = OwnerStream(label)
    try:
        ack = await stream.open()
    except OwnerUnavailable as exc:
        # Said out loud rather than closed silently: a terminal that opens onto
        # nothing is a black rectangle the reader has no way to interpret.
        await websocket.send_json({"event": "unavailable", "reason": str(exc)})
        await websocket.close(code=1011)
        return
    except OwnerClientError as exc:
        await websocket.send_json({"event": "refused", "reason": str(exc)})
        await websocket.close(code=1008)
        return

    await websocket.send_json({"event": "attached", **ack})
    logger.info(
        "fleet terminal: a browser attached to %s (%s replayed bytes, truncated=%s)",
        label, ack.get("replayed_bytes"), ack.get("replay_truncated"),
    )

    async def to_browser() -> None:
        async for data, replay in stream.frames():
            del replay          # the replay marker was already reported in `attached`
            await websocket.send_bytes(data)

    async def to_agent() -> None:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return
            if (payload := message.get("bytes")) is not None:
                await stream.write(payload)
                continue
            text = message.get("text")
            if not text:
                continue
            try:
                control = json.loads(text)
            except ValueError:
                logger.warning("fleet terminal: unparseable control message on %s", label)
                continue
            if size := control.get("resize"):
                await stream.resize(int(size["rows"]), int(size["cols"]))

    pump_out = asyncio.create_task(to_browser())
    pump_in = asyncio.create_task(to_agent())
    try:
        # Either direction ending ends the session: a terminal that can still
        # type but shows nothing, or shows output but cannot type, is worse than
        # one that closed — it looks like it is working.
        done, pending = await asyncio.wait(
            {pump_out, pump_in}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        for task in done:
            if (exc := task.exception()) is not None and not isinstance(exc, WebSocketDisconnect):
                logger.warning("fleet terminal: %s relay ended: %s", label, type(exc).__name__)
    except WebSocketDisconnect:
        pass
    finally:
        await stream.close()
        logger.info("fleet terminal: a browser detached from %s", label)
