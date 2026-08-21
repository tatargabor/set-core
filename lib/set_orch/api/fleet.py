"""Fleet API — the agent sessions running on this machine.

    GET  /api/fleet/agents             — every live agent, its project, and its measured state
    GET  /api/fleet/agents/{pid}/state — one agent's measured state, without the fleet
    GET  /api/fleet/agents/{pid}/log   — the raw conversation of one agent (design §5.8)
    GET  /api/fleet/owner              — whether an agent can be started at all
    POST /api/fleet/agents             — start one BARE session, through the agent owner (5.8)
    POST /api/fleet/units              — start a WORK UNIT, through the engine's one command (5.10)
    POST /api/fleet/agents/{label}/stop — stop one this framework started
    POST /api/fleet/agents/{pid}/instruct — address one instruction, and say what became of it
    GET  /api/fleet/waiters            — waiter processes, and which of them are orphaned
    POST /api/fleet/waiters/{pid}/remove — stop ONE named orphan; no bulk form exists
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
from ..fleet.awaiting import awaiting_for
from ..fleet.discovery import (
    discover_agent, live_session_ids, parent_seat, read_messaging_projects,
)
from ..fleet import scopes as fleet_scopes
from ..fleet import instruct as fleet_instruct
from ..fleet import purpose as fleet_purpose
from ..fleet import capabilities as fleet_caps
from ..fleet.conversation import read_conversation
from ..fleet import layout as fleet_layout
from ..fleet import roster
from ..fleet import restore as fleet_restore
from ..fleet.discovery import live_session_ids as fleet_live_session_ids
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


def _descendants_index(agents, owned) -> Dict[str, List[int]]:
    """seat → the pids started BY that seat, from what was recorded at start time.

    Built from `requested_by`, which the owner records in the act of starting —
    the only moment the relation exists. The process tree cannot answer it:
    measured, **0 of 23** live agents had an agent ancestor, and an agent this
    surface starts has the OWNER (a plain python process) as its parent with
    systemd above it, so no walk will ever find which agent asked for it.
    """
    index: Dict[str, List[int]] = {}
    for a in agents:
        who = (owned or {}).get(a.pid, {}).get("requested_by")
        if who:
            index.setdefault(str(who), []).append(a.pid)
    return index


def _agent_payload(agent, state, owned: Optional[Dict[int, Dict[str, Any]]] = None,
                   seats: Optional[Dict[str, Any]] = None,
                   purposes: Optional[List[Any]] = None,
                   descendants: Optional[Dict[str, List[int]]] = None) -> Dict[str, Any]:
    # Three values, not two, and the third is why this is not a boolean. A
    # terminal exists only for a process the framework started and still holds
    # (task 5.2), so:
    #   started-here  the owner holds this pty; it can be typed into
    #   foreign       nobody here holds it; there is no terminal and cannot be
    #   unknown       the owner could not be asked, so we do not know which
    # Collapsing `unknown` into `foreign` would let the screen say "no terminal"
    # about an agent that has one, whenever the owner is merely restarting.
    if owned is None:
        population, terminal_label, scope = "unknown", None, None
    elif agent.pid in owned:
        population, terminal_label = "started-here", owned[agent.pid].get("label")
        scope = None
    else:
        # FOUR values, and the fourth is task 5.5. Measured: a pty-attached
        # agent dies with its pty holder, so an agent this framework started
        # cannot outlive its owner — but the OWNER can be restarted while a
        # scope it started is still there, and after that the agent is no longer
        # in `owned`. Reporting it `foreign` then is a false value: it says the
        # framework did not start it, when the framework did and merely lost the
        # handle. A pty master cannot be reacquired from outside, so the
        # terminal is genuinely gone — but recovery (5.11) is possible, and this
        # is exactly where it is offered.
        #
        # Asked of the PROCESS's own cgroup rather than of anything we wrote
        # down: a record of what we started is a record of our intent, and after
        # a crash the two differ precisely when it matters.
        scope = fleet_scopes.scope_of(agent.pid)
        population = "orphaned" if scope else "foreign"
        terminal_label = None

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
        # The scope this agent runs in, when the framework started it and no
        # longer holds it. Present ONLY for `orphaned`: it is what `recover`
        # must stop before resuming, and that ordering is load-bearing —
        # resuming first reproduces the design §6.1 silent fork.
        "scope": scope,
        # ⚠ What the framework may CLAIM about survival, carried in the
        # payload rather than left to the surface to remember. The transient
        # scope protects against a **cgroup kill** — a restart of the web
        # service — and NOT against losing a tty: measured both ways, and
        # pty-attached with the owner killed leaves the scope inactive and the
        # process gone. A surface that promises more than this word is
        # promising something that was measured not to happen.
        "survives": "web-service-restart",
        # Who started this agent, and WHICH KIND of answer it is. The recorded
        # one wins when present because it is the only one that can answer for a
        # framework-started agent at all — measured: those have the owner, a
        # plain python process, as their parent. `source` is carried so the
        # surface can mark the recorded one as a claim and the ancestry one as
        # measured; they answer different questions and can disagree.
        "parent": parent,
        # Task 4.4 — whether this agent can be addressed at all, and WHY NOT
        # when it cannot. The reason travels with the row so the surface can put
        # it where the input would be, rather than dropping the agent (which
        # hides running work) or showing an input that silently goes nowhere
        # (which is worse). Three distinct reasons, and only one is about the
        # agent: no bus on the machine, a bus that could not be asked, or a bus
        # that was asked and does not know this session.
        **fleet_instruct.instructability(agent.session_id, seats).as_dict(),
        # Tasks 3.4 and 3.5 — what the agent SAID, kept apart from what was
        # measured. Three rules are load-bearing here and each is a defect this
        # repository has already paid for:
        #
        #  · `phase` is null unless the agent declared one. None is not a phase;
        #    a guessed one is wrong exactly when the situation is unusual, which
        #    is when somebody opened this screen.
        #  · `blocked` does NOT contradict `state`. An agent can be measured
        #    working and declare itself blocked at the same moment — working a
        #    detour while an answer is outstanding — and that pair is the case
        #    worth surfacing. Folding them into one field makes it unsayable.
        #  · `declared_at` travels with it, because a declaration does not
        #    expire on its own and its AGE is what lets a reader weigh it.
        #
        # ⚠ CONFIDENTIALITY. `focus` is a sentence an agent wrote about work that
        # may be a consumer's — measured on the live roster, one named a partner
        # company and an unpaid invoice, and `focus_files` are that project's own
        # paths. Read at request time, shown, and never written down.
        # Task 7.18 — the same relation as `parent`, downwards. A COUNT and the
        # pids, so the surface can offer a way in rather than only a number.
        #
        # ⚠ It counts only what it can see, and says so rather than letting the
        # number imply completeness. An agent started with `claude -p` that has
        # already exited leaves no process and no session record, so it is
        # absent from this count — the same false-absence class as 7.14, and the
        # reason `live_only` travels with the figure instead of a bare integer.
        "descendants": _descendants_payload(agent, seats, descendants),
        "declared": _declared_payload(agent.session_id, seats),
        # Task 3.9 — what this agent is working TOWARDS, read from the engine's
        # own record and joined on the pid the engine wrote. `None` where there
        # is no record: on a machine with no engine that is every agent, and the
        # surface states the absence rather than drawing an empty field.
        "purpose": (purposes and
                    (lambda p: p.as_dict() if p else None)(
                        fleet_purpose.purpose_for_pid(purposes, agent.pid))) or None,
    }


#: What the framework installs, read once per process. It is derived from THIS
#: checkout's own template sources, so it changes only when the deployed code
#: changes — re-deriving it per project per poll would walk the manifests 41
#: times for an answer that cannot differ between them.
_FRAMEWORK_CAPS: List[Any] = []


def _framework_caps() -> List[Any]:
    if not _FRAMEWORK_CAPS:
        _FRAMEWORK_CAPS.extend(fleet_caps.framework_capabilities())
    return _FRAMEWORK_CAPS


def _descendants_payload(agent, seats, index) -> Dict[str, Any]:
    """Who runs under this agent, and what this answer cannot see.

    `known` is false when the roster could not be read: without a seat there is
    no key to look this agent up by, and a `0` in that state would say *nothing
    runs under it* about an agent that may have started five.
    """
    seat = seats.get(str(agent.session_id)) if (seats and agent.session_id) else None
    if seat is None or index is None:
        return {"known": False, "live": 0, "pids": [], "live_only": True,
                "reason": "this agent has no seat, so nothing can be looked up by it"}
    pids = sorted(index.get(seat.seat, []))
    return {
        "known": True,
        "live": len(pids),
        "pids": pids,
        # Stated with the number, always — including when it is zero, which is
        # exactly when a reader is most likely to take it for completeness.
        "live_only": True,
        "reason": "counted from RECORDED starts that are still running; a child "
                  "that has already exited is not here",
    }


def _declared_payload(session_id, seats) -> Dict[str, Any]:
    """What the agent declared about itself, or a stated absence.

    `known` is false when the bus could not be asked at all. That is not the
    same as an agent that declared nothing, and the two must not render alike:
    one is "this agent says nothing about itself", the other is "we could not
    find out", and only the first is a fact about the agent.
    """
    if seats is None:
        return {"known": False, "focus": None, "phase": None,
                "blocked": False, "files": [], "declared_at": None}
    seat = seats.get(str(session_id)) if session_id else None
    if seat is None:
        return {"known": True, "focus": None, "phase": None,
                "blocked": False, "files": [], "declared_at": None}
    return {
        "known": True,
        "focus": seat.focus_text,
        "phase": seat.phase,
        "blocked": seat.declared_blocked,
        "files": list(seat.focus_files),
        "declared_at": seat.focus_at,
    }


#: Every state the envelope counts. A LIST rather than a chain of `elif`s,
#: because the defect this replaced was structural: the counters were an
#: if/else-if with no final branch, so a state nobody had thought of was
#: counted nowhere while `agents` still included it. Adding to this tuple is
#: how a new state joins; forgetting to shows up as `unbucketed`, not as
#: silence. `tests/unit/test_fleet_state_tally.py` holds the arithmetic.
STATE_BUCKETS = ("working", "unknown", "waiting", "asking", "quiet")


def _state_tally(states: Dict[Any, Any]) -> Dict[str, int]:
    """How many agents are in each state, plus how many are in none of them.

    Counted from the DATA. `unbucketed` is the whole reason this is a function:
    it is the number that makes a missing bucket visible instead of turning an
    agent into a gap in the header — false absence, failing toward a calm
    screen, which is the direction this codebase treats as expensive.
    """
    counts = {name: 0 for name in STATE_BUCKETS}
    unbucketed = 0
    for st in states.values():
        if st.state in counts:
            counts[st.state] += 1
        else:
            unbucketed += 1
    counts["unbucketed"] = unbucketed
    return counts


def _record_roster(agents, owned: Optional[Dict[int, Dict[str, Any]]]) -> None:
    """Write what discovery just saw into the durable roster.

    **Here rather than inside `discovery`,** which is a read of process state:
    making it write to disk would give a query a side effect and fire on every
    internal call, tests included. This route is the one place a full discovery
    answer already exists per request.

    **And the failure is swallowed with respect to discovery's answer.** The
    screen must not go blank because a record could not be saved — a roster is
    for the next boot, the agent list is for now, and the second must not be
    lost to protect the first. `roster.record` raises on purpose so this
    decision lives at the call site rather than being made for every caller.
    """
    labels = (
        None if owned is None
        else {pid: str(a["label"]) for pid, a in owned.items() if a.get("label")}
    )
    if labels is None:
        # NOT flattened to an empty mapping. "The holder could not be asked" and
        # "the holder holds nothing" are different facts, and only the second one
        # means an agent has no framework name. Flattening them would let one
        # unreachable socket erase every recorded label — the names this record
        # exists to keep.
        logger.warning("fleet api: recording the roster without labels; the owner could not be asked")
    try:
        roster.record(agents, labels=labels)
    except Exception as exc:
        logger.warning("fleet api: roster not recorded (%s); the agent list is unaffected", exc)


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
    projects = discover_projects(agents, registered=registered,
                                 messaging=_safe_messaging())

    states = {agent.pid: read_state(agent.session_log, record=agent.record) for agent in agents}
    by_pid = {agent.pid: agent for agent in agents}
    # Asked once for the whole listing, not once per agent: it is one socket
    # round trip and the answer is the same for every row.
    owned = _owned_by_pid()
    # After `owned`, and deliberately: the record stores the name the FRAMEWORK
    # holds, so it cannot be written before the framework has been asked what it
    # holds. The same answer serves both, rather than a second round trip.
    _record_roster(agents, owned)
    # Asked once for the whole listing, like `owned`, and reused for a few
    # seconds beyond that — `sac agents --json` starts a node process, measured
    # at 0.07 s against 0.098 s for this whole listing, and this endpoint is
    # polled. The window is stated in `instruct.SEATS_MAX_AGE`: a session that
    # enrols during it reads as not-instructable for up to ten seconds, which is
    # a bounded false absence in the direction that offers no control rather
    # than one that fails. A SEND never uses this cache.
    seats = fleet_instruct.seats_cached()
    # Built ONCE for the whole fleet: a descendant may sit in another project,
    # so a per-project index would report a lineage that stops at the project
    # boundary — which is not where lineage stops.
    descendants = _descendants_index(agents, owned)

    grouped: List[Dict[str, Any]] = []
    for project in projects:
        members = [by_pid[pid] for pid in project.agent_pids if pid in by_pid]
        # Every entry here came from a source that named it, so the question is
        # not whether to trust it — it is whether the entry is a leftover with no
        # source at all, which would be a bug upstream. Naming ONE source here
        # was safe while there were two and every entry had a live agent or a
        # registration; the third source broke that silently. Measured
        # 2026-08-19: this line discarded **8 projects** the messaging registry
        # had just supplied, and discarded them after they had passed the union
        # — a filter can undo a source, and this one did it without a word.
        if not members and not project.sources:
            continue
        purposes = fleet_purpose.read_purposes(project.root) if project.root else []
        grouped.append({
            "name": project.name,
            "root": project.root,
            "sources": project.sources,
            "archived": project.archived,
            "agents": [_agent_payload(a, states[a.pid], owned, seats, purposes, descendants)
                       for a in members],
            # Task 7.14. What is waiting for a HUMAN here, independent of who is
            # running — the case an agent-centric screen gets wrong by
            # construction. Carried even when its total is zero, because the KEY
            # is what lets the surface tell "nothing awaits" from "this was
            # never measured"; `source_missing` inside it says which.
            "awaiting": awaiting_for(project.name, project_root=project.root).as_dict(),
            # Task 3.9 at the project level. Read once per project rather than
            # once per agent — the records are per project, and a stale one
            # belongs on the screen even when nothing is running under it.
            "runs": [p.as_dict() for p in purposes],
            # Task 2.6 — what this project has wired in. Four states, and
            # `unknown` is one of them: a tree we cannot read must not read as
            # "not connected", which invites installing into it.
            "capabilities": (fleet_caps.report_for_project(
                project.root, capabilities=_framework_caps()).as_dict()
                if project.root else None),
        })

    tally = _state_tally(states)
    working, unknown, waiting = tally["working"], tally["unknown"], tally["waiting"]
    asking, quiet, unbucketed = tally["asking"], tally["quiet"], tally["unbucketed"]
    if unbucketed:
        logger.warning(
            "fleet: %d agent(s) hold a state no bucket counts: %s",
            unbucketed, sorted({s.state for s in states.values()} - set(STATE_BUCKETS)),
        )

    awaiting_total = sum(g["awaiting"]["total"] for g in grouped)
    awaiting_unmeasured = sum(1 for g in grouped if g["awaiting"]["source_missing"])

    return {
        "agents": len(agents),
        "working": working,
        "unknown": unknown,
        "waiting": waiting,
        "asking": asking,
        "quiet": quiet,
        # Zero unless a state exists that no bucket counts. Carried rather than
        # merely logged, because the screen is where somebody would notice.
        "unbucketed": unbucketed,
        "awaiting": awaiting_total,
        # How many projects could not be measured at all. A zero `awaiting`
        # next to a non-zero here means "nothing found where we looked", which
        # is a different sentence from "nothing is waiting".
        "awaiting_unmeasured": awaiting_unmeasured,
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
        # The same sentence for the bus: a screen where NO tile can be
        # instructed has one cause, and naming it once is the difference
        # between "these agents are not enrolled" and "we could not ask".
        # Per CLAUDE.md the answer to the first is enrolment, never a second
        # transport, so the surface must be able to tell them apart.
        "bus_reachable": seats is not None,
        "instructable": sum(
            1 for g in grouped for a in g["agents"] if a.get("instructable")),
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


def _safe_messaging() -> List[Dict[str, Any]]:
    """The messaging registry's projects, or none — the union's third source.

    Measured 2026-08-19: **8 of 49** roots were known only here, every one of them
    a directory that exists. Without this the screen calls itself an inventory
    and silently stops a sixth of the way short.
    """
    try:
        return read_messaging_projects()
    except Exception as exc:                      # never empty the fleet for it
        logger.warning("fleet api: messaging registry unreadable: %s", type(exc).__name__)
        return []


def _known_roots() -> set:
    """Directories the screen can actually see an agent in.

    A start is refused outside this set. Not because a local dashboard is
    exposed, but because *not* choosing here chooses the permissive option
    silently: an endpoint that accepts any existing directory runs an agent
    anywhere on the machine, and nothing on the screen ever offers that.

    ## Built from the SAME union the list is, and that is the whole point

    This used to enumerate its own two sources — the registry, and the roots of
    discovered agents — which was a second definition of *what this screen
    knows*. It was correct while the list had those same two sources, and it
    went wrong silently the moment a third arrived.

    Measured 2026-08-19, on a report that a project visible on screen refused to
    start an agent: **49 projects served, 39 roots known here, 10 refused** — 9
    of them supplied only by the messaging registry, and 1 by a live process
    whose root this enumeration missed. The screen offered a start control on
    every one of them.

    This is the defect the union's own filter already had, thirty lines below,
    and the note there says why it recurs: *a filter can undo a source.* Fixing
    that one and leaving this one is the same class again — **completing a set
    means auditing everything downstream of it**, because any later step that
    re-states the set is a copy that drifted the moment the set changed. So the
    guard now asks the list rather than rebuilding it, and a fourth source
    cannot reintroduce this.

    ⚠ Archived projects are IN, and that is measured rather than reasoned.
    `discover_projects`'s own docstring says an archived project *"is excluded by
    every other surface in this framework, so it is excluded here too"* — and the
    code below it carries the flag without ever filtering on it. Measured
    2026-08-19 on the live server: **19 of the 49 projects served are archived**,
    and the screen shows every one. Believing that sentence and filtering here
    would have re-created the very divergence this function was just repaired
    for, in the other direction: a project on screen, with a start control, that
    the guard refuses. The rule is *what the screen shows*, so the guard follows
    the list wherever it goes and never decides on its own what ought to be in
    it.
    """
    roots = set()
    for project in discover_projects(discover_agents(include_oneshot=True),
                                     registered=_safe_registry(),
                                     messaging=_safe_messaging()):
        if project.root:
            roots.add(os.path.realpath(project.root))
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
    #: Where the draggable dividers sit, or `None` to leave them as they are.
    #:
    #: `None` rather than `{}` because the project column posts groups and says
    #: nothing about dividers, and "I am not mentioning these" must not mean
    #: "delete these". Dividers are normally written through their own route,
    #: which does not bump the version this body's `base_version` guards.
    splits: Optional[Dict[str, Any]] = None
    #: Which views are docked where, keyed by PROJECT (2026-08-20), or `None` to
    #: leave them as they are — the same omission rule as `splits`, and for the
    #: same reason. A flat list is refused rather than accepted and re-keyed:
    #: it is the shape that made docking screen-wide, and silently adopting it
    #: would put a dock in a project nobody chose.
    docks: Optional[Dict[str, List[Dict[str, Any]]]] = None
    base_version: Optional[int] = None


class RenameAgentBody(BaseModel):
    """The new name, and nothing else.

    Deliberately not a general "update the agent" body: a rename is the only
    property of a held agent this framework may change from outside, and a route
    that took a bag of fields would be a different thing wearing this one's name.
    """

    new_label: str


@router.post("/api/fleet/agents/{label}/rename")
def fleet_rename_agent(label: str, body: RenameAgentBody) -> Dict[str, Any]:
    """Give a running agent a different name. It keeps running.

    Addressed by label like `stop`, for the same reason: a pid is reused, a label
    is what the framework named.

    Three writes, and the order is what makes a half-done rename harmless. The
    owner's map first — it is the only one that can refuse, and until it succeeds
    nothing has happened. Then the durable record and the layout, both of which
    are corrections to documents that would otherwise name something that no
    longer exists. Neither of the two is allowed to fail the request: the agent
    HAS been renamed at that point, and answering with an error would tell the
    reader the opposite of what is true. They are reported instead.
    """
    try:
        agent = OwnerClient().rename(label, body.new_label)
    except OwnerUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OwnerClientError as exc:
        # A refusal — not held, name taken, nameless. 409, like every other
        # owner refusal on this surface; the message is the owner's own.
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    new_label = str(agent.get("label") or body.new_label)
    carried: Dict[str, Any] = {"record": 0, "docked": 0, "splits": 0}
    session_id, project = None, None
    try:
        pid = agent.get("pid")
        found = discover_agent(int(pid)) if pid else None
        if found is not None:
            session_id, project = found.session_id, found.project_name
    except Exception as exc:                       # never fail a done rename
        logger.warning("fleet api: rename %s -> %s: cannot resolve the session (%s)",
                       label, new_label, type(exc).__name__)

    if session_id:
        try:
            carried["record"] = roster.relabel(str(session_id), new_label, project=project)
        except Exception as exc:
            logger.warning("fleet api: rename %s -> %s: the record was not updated (%s)",
                           label, new_label, type(exc).__name__)
    else:
        logger.warning(
            "fleet api: rename %s -> %s: no session id, so the record keeps the old name "
            "and a restore would bring it back under it", label, new_label,
        )

    try:
        carried.update(fleet_layout.relabel_dock("agent", label, new_label))
    except Exception as exc:
        logger.warning("fleet api: rename %s -> %s: the layout was not updated (%s)",
                       label, new_label, type(exc).__name__)

    logger.info("fleet api: renamed agent %s to %s (pid %s); carried %s",
                label, new_label, agent.get("pid"), carried)
    return {"agent": agent, "renamed_from": label, "carried": carried}


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
                                               registered=_safe_registry(),
                                               messaging=_safe_messaging())]
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
             "ungrouped_order": body.ungrouped_order, "splits": body.splits,
             "docks": body.docks},
            base_version=body.base_version,
        )
    except LayoutConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OSError as exc:
        logger.error("fleet api: cannot write the arrangement: %s", exc)
        raise HTTPException(status_code=500, detail=f"cannot write the arrangement: {exc}") from exc

    names = [p.name for p in discover_projects(discover_agents(include_oneshot=False),
                                               registered=_safe_registry(),
                                               messaging=_safe_messaging())]
    return fleet_layout.apply_to(saved, names)


# --------------------------------------------------------------------------- #
# the roster — what was here before the machine went down
# --------------------------------------------------------------------------- #

@router.get("/api/fleet/roster")
def fleet_roster_projects() -> Dict[str, Any]:
    """Every project with a recorded list, newest first.

    Its own route rather than a field on the agent listing, because this is what
    the EMPTY screen needs: after a reboot no project holds an agent, so the
    column offers nothing to click and a per-project read would need a name
    nobody can supply.
    """
    live = fleet_live_session_ids()
    listed = roster.projects()
    for item in listed:
        if live is None:
            item["running"] = None
            continue
        entries = roster.read(item["project"])["entries"]
        item["running"] = sum(1 for e in entries if e.get("session_id") in live)
    return {"projects": listed, "liveness_known": live is not None}


@router.get("/api/fleet/roster/{project}")
def fleet_roster(project: str) -> Dict[str, Any]:
    """One project's recorded list, with resumability measured NOW.

    `record_exists` is carried rather than inferred from an empty list: "never
    recorded" and "recorded and empty" are different states, and the screen says
    different things about them.

    **`running` is added HERE and not in `roster.read()`**, which deliberately
    consults nothing a reboot destroys — that is the property the whole module
    exists for. This layer may ask, and must: found by looking at the running
    screen 2026-08-21, the control read "Restore 7 agents" for a project whose
    seven sessions were all alive, so it promised an act that would have skipped
    every one of them. Resumable is about the transcript; restorable is about
    the transcript AND nobody being on it.

    `liveness_known` is false when it could not be asked, and then `running` is
    `None` on every entry rather than `False` — a gap is not a zero, and a zero
    here is the number the surface would subtract.
    """
    answer = roster.read(project)
    live = fleet_live_session_ids()
    for entry in answer["entries"]:
        entry["running"] = None if live is None else (entry.get("session_id") in live)
    answer["liveness_known"] = live is not None
    return answer


@router.post("/api/fleet/roster/{project}/restore")
def fleet_roster_restore(project: str) -> Dict[str, Any]:
    """Bring back the whole recorded list for one project.

    **No body, and that is the design.** No `argv`, for the reason already
    recorded on `StartAgentBody` — an HTTP route running an arbitrary command
    list is a different thing from a button that starts an agent. And no
    per-entry selection: the act asked for is *the list back*, and a subset
    restore is a different act that can be added without changing this one.

    The known-roots guard is passed in from here rather than resolved in the
    fleet layer, which is domain-free and must not read the project registry.
    Passing it is not optional: `POST /api/fleet/agents` refuses a cwd outside
    that set, and a second route that admits what the first refuses is the guard
    being deleted one caller at a time.
    """
    try:
        return fleet_restore.restore(project, known_roots=_known_roots())
    except OwnerUnavailable as exc:
        # Nothing was attempted, so this is one answer about the request rather
        # than N answers about N entries.
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.delete("/api/fleet/roster/{project}/{key:path}")
def fleet_roster_forget(project: str, key: str) -> Dict[str, Any]:
    """Drop one entry from a project's record.

    A `key:path` because an entry with no session id is keyed on a synthetic
    name containing a slash, and a route that could not address it would leave
    exactly the entries a user most wants gone — the ones the runtime never
    named — unremovable.
    """
    if not roster.forget(project, key):
        raise HTTPException(status_code=404, detail=f"no entry {key} recorded for {project}")
    return {"project": project, "forgotten": key}


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
# Starting a WORK UNIT — through the engine's one command (task 5.10)
# --------------------------------------------------------------------------- #

#: The engine's command entry point, invoked as a command and never imported.
#: `set_orch` may not import `set_workcycle` (engine design D10), and this is the
#: interface that exists for exactly this purpose: the engine's contract names
#: the framework's surface as a caller and says there is no second mechanism.
ENGINE_COMMAND = "set-work-cycle"

#: The one subcommand that starts a unit. Named here so the argv this route
#: builds is checkable; `tests/unit/test_fleet_api.py` asserts against the
#: engine's own parser, where `run` carries `starts_a_unit=True`.
ENGINE_RUN = "run"


class StartUnitBody(BaseModel):
    """What the screen may ask the ENGINE for.

    Deliberately not a superset of `StartAgentBody`. This route does not take a
    label, an argv or a command: it builds the engine's argv itself, so there is
    no parameter through which a second start path could be smuggled in.
    """

    change: str
    cwd: str
    #: The agent session this unit belongs to. The engine refuses a project name
    #: here, and that refusal is carried through rather than pre-empted — its
    #: wording is the engine's to own.
    seat: str
    limit: Optional[int] = None
    model: Optional[str] = None
    rows: int = 40
    cols: int = 120
    requested_by: Optional[str] = None


@router.post("/api/fleet/units")
def fleet_start_unit(body: StartUnitBody) -> Dict[str, Any]:
    """Start one work unit by RUNNING the engine's command under an owned pty.

    Not by spawning an agent and hoping. A run started outside the engine is
    absent from the engine's recorded state — which is the source the rest of
    this screen reads (task 3.9) — so the surface would have started something
    it then could not describe. That is why the engine's contract says any
    caller uses this entry point and no second mechanism exists, and why this
    route builds the argv rather than accepting one.

    The pty is the framework's, exactly as for a bare session: the difference is
    WHAT runs inside it, not who owns it. The label says which of the two this
    is, because a screen that cannot tell a work unit from a hand-started shell
    cannot report either honestly.
    """
    # The SAME two refusals as the bare start, deliberately reusing the same
    # check rather than a second one: a directory this screen may start a unit
    # in and one it may start a session in are the same set, and two checks that
    # are meant to agree drift.
    root = os.path.realpath(os.path.expanduser(body.cwd))
    if not os.path.isdir(root):
        raise HTTPException(status_code=400, detail=f"no such directory: {body.cwd}")
    if root not in _known_roots():
        raise HTTPException(
            status_code=400,
            detail=f"{root} is not a project this screen knows; register it first",
        )

    argv = [ENGINE_COMMAND, "--tree", root, "--change", body.change, ENGINE_RUN,
            "--seat", body.seat, "--started-by", "fleet-surface"]
    if body.limit is not None:
        argv += ["--limit", str(body.limit)]
    if body.model:
        argv += ["--model", body.model]

    # A label that says what it is. `unit-` is not decoration: the terminal
    # column, the stop action and the recovery path all key on the label, and a
    # unit run and a bare shell need to be distinguishable there without asking
    # anything else.
    label = f"unit-{body.change}-{body.seat}".replace("/", "-").replace("#", "-")
    try:
        result = OwnerClient().start(
            label=label, cwd=root, argv=argv, rows=body.rows, cols=body.cols,
            requested_by=body.requested_by,
        )
    except OwnerUnavailable as exc:
        # 503 and no local fallback, for the same reason as the bare start:
        # starting it in this process rebuilds finding CB-1, where a dashboard
        # restart took every agent it had started with it.
        raise HTTPException(status_code=503, detail=str(exc))
    except OwnerClientError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    result["kind"] = "work-unit"
    result["change"] = body.change
    result["engine_argv"] = argv
    logger.info("fleet api: work unit started for change=%s seat=%s label=%s",
                body.change, body.seat, label)
    return result


# --------------------------------------------------------------------------- #
# Instruction (tasks 6.3, 6.6) — the write half
# --------------------------------------------------------------------------- #


class InstructBody(BaseModel):
    """One instruction, to one session.

    No recipient field: the address is the pid in the path, resolved here to a
    seat. Letting the caller name a seat would make the route a general-purpose
    bus client, and a mistyped seat would then be a message to the wrong agent
    rather than a 404 about a pid that is not running.
    """

    text: str
    #: `REQUEST` by default — see `instruct.send_instruction`. A caller may send
    #: a `QUESTION`; a `FACT` is allowed and will correctly report that it woke
    #: nobody, which is the honest outcome rather than a refusal.
    kind: str = "REQUEST"


@router.post("/api/fleet/agents/{pid}/instruct")
def fleet_instruct_agent(pid: int, body: InstructBody) -> Dict[str, Any]:
    """Send one instruction, and report what the CHANNEL says became of it.

    The outcome is carried verbatim from the bus and is never inferred from the
    fact that this route returned 200. That distinction is the whole point of
    task 6.3: an HTTP 200 here means *the send was made and answered*, which is
    compatible with the message reaching nobody — so the body carries `accepted`
    and `outcome` as two separate fields and `delivered_to_agent` as a third.

    The agent is re-discovered by pid rather than trusted from the caller, for
    the same reason the log route does it: a pid is reused, and instructing
    whatever session a stale pid now maps to would deliver one person's message
    to another's agent.

    A **fresh** roster is read here rather than the cached one the listing uses.
    The cache exists so a poll does not spawn a process per tile; an outcome
    depends on who is live at this instant, and a ten-second-old answer to that
    question is exactly the kind of stale measurement this screen exists to
    avoid.
    """
    agent = discover_agent(pid)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"no live agent with pid {pid}")
    if not (body.text or "").strip():
        raise HTTPException(status_code=400, detail="an empty instruction is not sent")

    seats = fleet_instruct.read_seats()
    can = fleet_instruct.instructability(agent.session_id, seats)
    if not can.instructable:
        # 409 rather than 400 or 503: the request is well formed and the service
        # is up — this agent simply has no address. The reason travels in the
        # body so the surface can put it where the input would be (task 4.4),
        # rather than rendering a generic failure.
        raise HTTPException(status_code=409, detail={
            "error": "not-instructable", "reason": can.reason, "pid": pid,
            "session_id": agent.session_id,
        })

    state = read_state(agent.session_log, record=agent.record)
    waiters = fleet_instruct.live_waiters()
    report = fleet_instruct.send_instruction(
        can.seat, body.text, kind=body.kind, state=state.state, waiters=waiters)

    payload = report.as_dict()
    payload["pid"] = pid
    payload["session_id"] = agent.session_id
    # How many waiters this session has, next to the outcome. Measured: one
    # session owned four at once, so this is a count and not a flag — and a zero
    # here is the remedy the surface offers (task 7.7), not a failure.
    payload["waiters_here"] = report.waiters
    if report.outcome == fleet_instruct.REFUSED:
        # The bus refused. Reported as a 409 with the channel's own words rather
        # than retried without the address: an unresolvable addressee is exactly
        # when a broadcast is most tempting and most wrong.
        raise HTTPException(status_code=409, detail=payload)
    return payload


@router.get("/api/fleet/waiters")
def fleet_waiters() -> Dict[str, Any]:
    """Every waiter process, and which of them have no session left.

    Shown next to the agents reported as having no waiter, because the offer to
    *install* one is exactly the moment somebody is adding to the pile.

    Three values where a boolean would do, and the third is why: `orphaned` is
    what may be removed, `live` is what must not be, and `undeterminable` is a
    waiter whose session cannot be read — treated as live, listed, and never
    offered. Collapsing the third into either of the others is the only way to
    get this wrong, and one direction of that mistake kills a live waiter.
    """
    waiters = fleet_instruct.live_waiters()
    if waiters is None:
        # `/proc` could not be read. Not an empty list: "no waiters" is an
        # invitation to install one, and "we could not look" is not.
        return {"measured": False, "reason": "the process table could not be read",
                "waiters": [], "orphaned": [], "orphaned_count": 0}

    live = live_session_ids()
    orphans = {w.pid for w in fleet_instruct.orphaned_waiters(waiters, live)}
    rows = []
    for w in waiters:
        if not w.session_known:
            status = "undeterminable"
        elif w.pid in orphans:
            status = "orphaned"
        else:
            status = "live"
        rows.append({"pid": w.pid, "session_id": w.session, "cwd": w.cwd,
                     "rooms": list(w.rooms), "status": status,
                     "removable": status == "orphaned"})
    return {
        # False when session liveness could not be determined at all — in which
        # case nothing is orphaned, by rule, and the surface must say why rather
        # than showing a clean list.
        "measured": live is not None,
        "reason": None if live is not None else "session liveness could not be determined",
        "waiters": rows,
        "orphaned": sorted(orphans),
        "orphaned_count": len(orphans),
    }


@router.post("/api/fleet/waiters/{pid}/remove")
def fleet_remove_waiter(pid: int) -> Dict[str, Any]:
    """Stop ONE named waiter. There is deliberately no bulk form of this route.

    A cleanup endpoint that takes a list is one mistaken list away from killing
    live waiters, and a killed live waiter is invisible: the agent it belonged to
    merely looks quiet, and the next instruction sent to it sits unread.

    The pid is re-resolved to a waiter identity inside `remove_waiter` rather
    than trusted from a candidate list the caller read seconds ago — pids are
    recycled, and a stale candidate list is how a cleanup aims at something else.
    Every refusal is a 409 carrying its reason, because "its session is alive" is
    information for the reader, not an error to swallow.
    """
    result = fleet_instruct.remove_waiter(pid, live_sessions=live_session_ids())
    if not result.get("removed"):
        raise HTTPException(status_code=409, detail=result)
    return result


# --------------------------------------------------------------------------- #
# The terminal, both directions (tasks 5.3 and 6.4)
# --------------------------------------------------------------------------- #

class DocksBody(BaseModel):
    """Which view instances ONE PROJECT has docked, and to which edge.

    `project` is required and has no default. Docking used to be screen-wide,
    and a body that can omit the project is the shape that produced that —
    see `fleet_put_docks`.
    """

    project: str
    docks: List[Dict[str, Any]] = []


@router.put("/api/fleet/layout/docks")
def fleet_put_docks(body: DocksBody) -> Dict[str, Any]:
    """Store the docking of views alone, leaving the arrangement untouched.

    Its own route for the same reason the divider positions have one: the
    whole-document PUT is guarded by `base_version`, and docking a view is not
    an edit to the hand-made arrangement that guard protects.

    Note what this route does NOT carry: the SIZE of a docked view. That is a
    divider position and goes through the divider route, because a docked view's
    edge is a divider like any other. Two stores for one edge is how a screen
    ends up rendering a width nobody set.

    **It carries the PROJECT, and refuses a body without one (2026-08-20).**
    Docking was stored screen-wide, so a terminal docked in one project occupied
    the same edge in every other project — where nothing could render in it, and
    the band could only report that this project has no such agent. A dock's
    identity is an agent's terminal label, and a label belongs to a project;
    the project was the missing half of the key, not a scoping preference.
    """
    project = (body.project or "").strip()
    if not project:
        raise HTTPException(status_code=400, detail="docking needs the project it belongs to")
    try:
        stored = fleet_layout.save_docks(body.docks, project=project)
    except OSError as exc:
        logger.error("fleet api: cannot write the docking: %s", exc)
        raise HTTPException(status_code=500, detail=f"cannot write the docking: {exc}") from exc
    return {"project": project, "docks": stored}


class SplitsBody(BaseModel):
    """Where the draggable dividers sit, in CSS pixels, keyed by divider."""

    splits: Dict[str, Any] = {}


@router.put("/api/fleet/layout/splits")
def fleet_put_splits(body: SplitsBody) -> Dict[str, Any]:
    """Store the divider positions alone, leaving the arrangement untouched.

    A separate route rather than a field on the whole-document PUT, for a reason
    that is about failure rather than tidiness: that PUT is guarded by
    `base_version`, and a drag of an edge would have to either bump the version —
    making the next group edit in the same tab conflict with the user's own
    dragging — or skip the guard, which would put an unguarded write on the route
    that protects the hand-made arrangement.

    Last-write-wins here is the deliberate choice: what is lost in a race is one
    number, re-dragged in a second.
    """
    try:
        stored = fleet_layout.save_splits(body.splits)
    except OSError as exc:
        logger.error("fleet api: cannot write the divider positions: %s", exc)
        raise HTTPException(status_code=500, detail=f"cannot write the divider positions: {exc}") from exc
    return {"splits": stored}


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


# --------------------------------------------------------------------------- #
# installing a module into a project — task 6.5
#
# The most dangerous action this screen can take. Everything else here reads;
# this WRITES into a repository the framework does not own. What makes it safe
# is not this route: it is the machinery underneath — the hash ledger, the
# `protected` and `once` rules, committed deletions read as intent, tombstones,
# the ownership checks, and a `dry_run` that is honest about its blast radius.
# This route's only jobs are to refuse a target the screen never showed, and to
# hand the installer's report back UNCHANGED.
# --------------------------------------------------------------------------- #

class InstallBody(BaseModel):
    module: str
    dry_run: bool = True


@router.post("/api/fleet/projects/{name}/install")
def fleet_install_module(name: str, body: InstallBody) -> Dict[str, Any]:
    """Install one module into one project, and return what the installer said it did.

    `dry_run` defaults to **True**, and that default is the decision. A preview is
    the documented way to approach every other write into a consumer tree
    (`set-project init --dry-run`), and a route whose default writes would make
    "I clicked it to see what it does" a destructive act.

    The report is returned as the installer produced it — every file written, every
    file skipped with its reason, and `changed_nothing` stated in its own right. This
    route does not summarise, reorder or interpret it. A surface that runs an installer
    and renders "done" has re-created one layer up exactly the silence the installer's
    contract forbids: an install that left six files alone because the project had
    edited them is a *good* outcome and a *misleading* screen unless the screen says it.
    """
    from ..module_install import InstallRefused, install_module, resolve_module

    target = None
    for project in discover_projects(discover_agents(include_oneshot=False),
                                     registered=_safe_registry(),
                                     messaging=_safe_messaging()):
        if project.name == name:
            target = project
            break
    if target is None or not target.root:
        # A project the screen never listed. Refused rather than resolved from the
        # filesystem: accepting any path that exists would let this endpoint write
        # into a directory nothing on the screen ever offered.
        raise HTTPException(status_code=404, detail=f"no project named {name!r} is listed")
    if not os.path.isdir(target.root):
        raise HTTPException(
            status_code=409,
            detail=f"{name} is listed but its directory is not readable; refusing to install",
        )

    try:
        decl = resolve_module(body.module)
        report = install_module(decl, target.root, dry_run=body.dry_run)
    except InstallRefused as exc:
        # 409, not 400: the request is well-formed and the project is real. What is
        # wrong is the state — a missing requirement, an ambiguous name, a module that
        # does not ship here — and that distinction is what tells a reader whether to
        # fix their click or fix their project.
        logger.info("fleet api: install refused (%s into %s): %s", body.module, name, exc)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("fleet api: install of %s failed: %s", body.module, exc)
        raise HTTPException(status_code=500, detail=f"install failed: {exc}") from exc

    return {
        "module": report.module,
        "project": name,
        "dry_run": body.dry_run,
        "written": list(report.written),
        "skipped": [{"path": s.path, "reason": s.reason} for s in report.skipped],
        # Stated as its own field rather than left to be derived from an empty list.
        # A caller that computes it from `written` is a second copy of the rule, and
        # `len(written) == 0` is exactly the check that reads as success.
        "changed_nothing": report.changed_nothing,
        "lines": report.as_lines(),
    }


# --------------------------------------------------------------------------- #
# PM mode — one agent at a time, chosen for the reader
# --------------------------------------------------------------------------- #

@router.get("/api/fleet/pm")
def fleet_pm(seconds_since_input: Optional[float] = Query(None)) -> Dict[str, Any]:
    """What PM mode is presenting, and everything the frame around it shows.

    `seconds_since_input` is supplied by the browser because that is where the
    fact lives — the keystroke went into a terminal the client holds. It decides
    only whether a pending switch may be offered; the decision itself is made
    server-side, so a client that forgets to send it cannot silently disable the
    guard for everyone.

    Running a cycle here rather than on a timer keeps the cost tied to somebody
    actually looking: the mode is off by default, and off means no invocation.
    """
    from ..fleet.pm import session as pm_session

    # Started, never awaited: a cycle makes a model call and the browser polls
    # this. The snapshot returned is whatever the last completed cycle left,
    # and `cycling` says one is in flight — a surface that froze while deciding
    # what to show would be worse than one that shows the previous answer.
    if pm_session.due():
        pm_session.cycle_in_background()
    return pm_session.snapshot(seconds_since_input=seconds_since_input)


class PmToggleBody(BaseModel):
    enabled: bool


@router.post("/api/fleet/pm")
def fleet_pm_toggle(body: PmToggleBody) -> Dict[str, Any]:
    """Turn the mode on or off. Touches NO agent either way.

    It is a way of looking at the fleet, not a way of operating it — a toggle
    that also acted on agents would be one nobody dares press to find out what
    it does.
    """
    from ..fleet.pm import session as pm_session

    if body.enabled:
        pm_session.enable()
        pm_session.cycle_in_background()
    else:
        pm_session.disable()
    return pm_session.snapshot()


@router.post("/api/fleet/pm/advance")
def fleet_pm_advance() -> Dict[str, Any]:
    """Move on IF the presented agent resumed, and report whether it did.

    `advanced: false` is an ordinary answer, not an error: it is what an
    unanswered question, an interrupt, or an unreadable log all produce, and the
    screen stays where it is.
    """
    from ..fleet.pm import session as pm_session

    advanced = pm_session.advance()
    payload = pm_session.snapshot()
    payload["advanced"] = advanced
    return payload


@router.post("/api/fleet/pm/defer")
def fleet_pm_defer() -> Dict[str, Any]:
    """Set the presented item aside. It stays queued, demoted, and counted."""
    from ..fleet.pm import session as pm_session

    pm_session.queue.defer()
    return pm_session.snapshot()


@router.post("/api/fleet/pm/dismiss/{pid}")
def fleet_pm_dismiss(pid: int) -> Dict[str, Any]:
    """Drop an item without answering it. Counted, never silently forgotten."""
    from ..fleet.pm import session as pm_session

    pm_session.queue.dismiss(pid)
    return pm_session.snapshot()


@router.post("/api/fleet/pm/refuse/{pid}")
def fleet_pm_refuse(pid: int) -> Dict[str, Any]:
    """Decline THIS interruption while THIS item is on screen.

    Scoped to the presented item on purpose: refusing once must not silence the
    same offer forever, only while the reader is still on what they were on.
    """
    from ..fleet.pm import session as pm_session

    pm_session.queue.refuse(pid)
    return pm_session.snapshot()


@router.post("/api/fleet/pm/present/{pid}")
def fleet_pm_present(pid: int) -> Dict[str, Any]:
    """Put a specific queued item on screen — the switch a countdown performs."""
    from ..fleet.pm import session as pm_session

    pm_session.queue.present(pid)
    return pm_session.snapshot()


@router.post("/api/fleet/pm/back")
def fleet_pm_back() -> Dict[str, Any]:
    """One step back through what was presented. Marks nothing dealt with."""
    from ..fleet.pm import session as pm_session

    pm_session.queue.back()
    return pm_session.snapshot()


@router.post("/api/fleet/pm/forward")
def fleet_pm_forward() -> Dict[str, Any]:
    """One step forward, bounded by the queue's own position."""
    from ..fleet.pm import session as pm_session

    pm_session.queue.forward()
    return pm_session.snapshot()
