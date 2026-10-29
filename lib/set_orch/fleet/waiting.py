"""What waits on the owner — one list from four separately measured sources.

Change `fleet-waiting-on-you`, design D1. The owner's open questions live in
four places, and a screen that sums them into one number hides the one fact a
reader needs most: which of the four it could not see. So every source answers
on its own — a count, whether it was measured, and if not, why — and the total
is the sum of the MEASURED sources only, carried beside the number of sources
that were not. A source that could not be read contributes nothing to the total
and says so; it never contributes a zero (the false-absence class).

## The four sources

1. **agent-questions** — live agents whose attention class means a person is
   needed (`state.ATTENTION_WAITING_CLASSES`), plus every question the question
   relay is holding. De-duplicated by SESSION, the relay record winning because
   it carries the moment the wait started (design D2).
2. **run-state** — the framework's own `awaiting` kinds per registered project
   (manual, stalled, orphaned, decision). `unverifiable` is not listed — it is
   an admission, not a finding. A project with no run state counts towards this
   source's `unmeasured_projects`, never towards its items.
3. **project-questions** — a project's declared `questions` read command. The
   shape is NOT agreed yet (design D3), so this source reports itself as
   unmeasured with that reason rather than as an empty list.
4. **bus-owner** — entries the bus itself reports as addressed to the owner and
   still open, read through `sac owner --json` (schema `sac.owner/1`, design D4).
   Never by parsing message text, never by reading the bus's store files: a
   phrasing change would drop items without an error, and a second reader of
   another project's format drifts the day that format changes.

## Confidentiality — the persistence boundary

Item titles are project and conversation content: a change name, a bus entry's
text. They are read at request time and returned, and that is all. Nothing here
logs them, caches them to disk, or writes them anywhere. Logs carry source
names and counts only — and exception TYPES, never exception messages, because
a message can quote the input that failed.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence

from .. import local_config
from . import awaiting as fleet_awaiting
from . import discovery as fleet_discovery
from . import question_relay
from . import state as fleet_state

logger = logging.getLogger(__name__)

SOURCE_AGENT_QUESTIONS = "agent-questions"
SOURCE_RUN_STATE = "run-state"
SOURCE_PROJECT_QUESTIONS = "project-questions"
SOURCE_BUS_OWNER = "bus-owner"

#: Every source, in the order the answer reports them. A tuple rather than
#: whatever the adapters happened to return, so a source that fails to answer
#: at all still appears — by name, as unmeasured.
SOURCES = (
    SOURCE_AGENT_QUESTIONS,
    SOURCE_RUN_STATE,
    SOURCE_PROJECT_QUESTIONS,
    SOURCE_BUS_OWNER,
)

#: The run-state kinds that mean a person can act. `unverifiable` is excluded on
#: purpose — see `awaiting.Awaiting.total`.
RUN_STATE_KINDS = ("manual", "stalled", "orphaned", "decision")

#: The bus view's contract. Anything else is a view this code does not know how
#: to read, and reading it anyway would be guessing.
SAC_OWNER_SCHEMA = "sac.owner/1"
#: Local-config key overriding which `sac` binary is asked. Machine-local by
#: nature (where a tool is installed), so it lives in local config, not here.
KEY_SAC_BIN = "fleet.sac_bin"
DEFAULT_SAC_BIN = "sac"
#: Measured 2026-10-29: `sac owner --json` answers in ~0.1 s. Ten seconds is a
#: ceiling for a stuck store lock, not an expected duration.
SAC_TIMEOUT_S = 10.0

#: A bus entry's title is its first line, cut to this length. The full text is
#: the bus's to show; the queue only needs enough to recognise the entry.
TITLE_MAX = 200

REASON_NOT_AGREED = "not agreed yet"


@dataclass
class SourceResult:
    """One source's answer: its items, or the reason it has none to give."""

    name: str
    measured: bool
    reason: Optional[str] = None
    items: List[Dict[str, Any]] = field(default_factory=list)
    #: Source-specific additions to the source's row in the answer (e.g. the
    #: run-state source's count of projects it could not measure).
    extra: Dict[str, Any] = field(default_factory=dict)


def _item(source: str, id_: str, *, project: Optional[str] = None, kind: str,
          title: Optional[str] = None, since: Optional[float] = None,
          session_id: Optional[str] = None, agent: Optional[str] = None,
          room: Optional[str] = None, link: Optional[str] = None) -> Dict[str, Any]:
    return {
        "source": source, "id": id_, "project": project, "kind": kind,
        "title": title, "since": since, "session_id": session_id,
        "agent": agent, "room": room, "link": link,
    }


# --------------------------------------------------------------------------- #
# 1. agent questions
# --------------------------------------------------------------------------- #

def collect_agent_questions(now: float) -> SourceResult:
    """Waiting agents and relayed questions, one item per session (design D2).

    Discovery is asked fresh, the same way PM mode asks it: there is no live
    in-memory roster to reuse — `fleet/roster.py` is the durable record for the
    next boot, not a cache of who is running now.
    """
    items: Dict[str, Dict[str, Any]] = {}

    # The relay first: its record wins, because it carries the wait's start.
    for rec in question_relay.list_waiting():
        session = str(rec.get("session_id") or "")
        if not session:
            continue
        started = rec.get("started")
        items[session] = _item(
            SOURCE_AGENT_QUESTIONS, f"agent:{session}",
            project=rec.get("project") if isinstance(rec.get("project"), str) else None,
            kind="relayed",
            since=float(started) if isinstance(started, (int, float)) else None,
            session_id=session,
        )

    agents = fleet_discovery.discover_agents()
    for agent in agents:
        st = fleet_state.read_state(agent.session_log, record=agent.record, now=now)
        if st.attention not in fleet_state.ATTENTION_WAITING_CLASSES:
            continue
        agent_name = agent.name or str(agent.pid)
        key = agent.session_id or f"pid:{agent.pid}"
        relayed = items.get(key)
        if relayed is not None:
            # Same question, seen twice. Keep the relay's start; add what only
            # discovery knows — which agent it is and its project.
            relayed["agent"] = agent_name
            if not relayed.get("project"):
                relayed["project"] = agent.project_name
            continue
        wait = st.input_wait_seconds
        items[key] = _item(
            SOURCE_AGENT_QUESTIONS,
            f"agent:{agent.session_id}" if agent.session_id else f"agent:pid:{agent.pid}",
            project=agent.project_name,
            kind=st.attention,
            # Display only. The runtime's own "waiting for" field is usually empty
            # (measured 2026-10-30: 16 of 16 live waiting agents had none), which left
            # a reader — the owner queue's ranker among them — unable to tell what the
            # agent is asking. The agent's last words, when it was the last to speak,
            # are the question; the fleet tile already shows the same excerpt.
            title=st.waiting_for or (st.excerpt if st.excerpt_from == "agent" else None),
            since=(now - wait) if isinstance(wait, (int, float)) else None,
            session_id=agent.session_id,
            agent=agent_name,
        )
    return SourceResult(SOURCE_AGENT_QUESTIONS, True, items=list(items.values()))


# --------------------------------------------------------------------------- #
# 2. run state
# --------------------------------------------------------------------------- #

def _registered_projects() -> List[Dict[str, Any]]:
    """The registry, read without FastAPI (the api helper is a thin wrapper)."""
    from ..project_registry import load_projects
    return load_projects()


def collect_run_state(now: float) -> SourceResult:
    projects = _registered_projects()
    items: List[Dict[str, Any]] = []
    unmeasured_projects = 0
    for project in projects:
        name = project.get("name")
        if not isinstance(name, str) or not name:
            continue
        root = project.get("path") or None
        aw = fleet_awaiting.awaiting_for(name, project_root=root)
        if aw.source_missing:
            # Not measured is not nothing awaiting. The decision markers are
            # still read from the task files — they do not depend on a run.
            unmeasured_projects += 1
        for kind in RUN_STATE_KINDS:
            for change in getattr(aw, kind):
                items.append(_item(
                    SOURCE_RUN_STATE, f"run:{name}:{kind}:{change}",
                    project=name, kind=kind,
                    # A change name is authored in the project's own plan —
                    # display data, never logged.
                    title=change,
                    link=f"/p/{name}/orch",
                ))
    return SourceResult(SOURCE_RUN_STATE, True, items=items,
                        extra={"unmeasured_projects": unmeasured_projects})


# --------------------------------------------------------------------------- #
# 3. project questions — not agreed
# --------------------------------------------------------------------------- #

def collect_project_questions(now: float) -> SourceResult:
    """Design D3 is a proposal still on the bus. Until a consumer agrees the
    command's shape there is nothing to read — which is unmeasured, not zero."""
    return SourceResult(SOURCE_PROJECT_QUESTIONS, False, reason=REASON_NOT_AGREED)


# --------------------------------------------------------------------------- #
# 4. bus entries addressed to the owner
# --------------------------------------------------------------------------- #

def _sac_bin() -> str:
    value = local_config.get(KEY_SAC_BIN)
    return str(value) if value else DEFAULT_SAC_BIN


def _run_sac_owner(sac_bin: str) -> subprocess.CompletedProcess:
    return subprocess.run([sac_bin, "owner", "--json"], capture_output=True,
                          text=True, timeout=SAC_TIMEOUT_S)


def _parse_ts(value: Any) -> Optional[float]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _first_line(text: Any) -> Optional[str]:
    if not isinstance(text, str):
        return None
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:TITLE_MAX]
    return None


def collect_bus_owner(now: float) -> SourceResult:
    """Read the bus's own owner view. Only a failing or absent view is
    unmeasured; an empty `open` list is measured, zero open (design D4)."""
    sac_bin = _sac_bin()
    if not shutil.which(sac_bin):
        return SourceResult(SOURCE_BUS_OWNER, False, reason="bus command not found")
    try:
        proc = _run_sac_owner(sac_bin)
    except subprocess.TimeoutExpired:
        return SourceResult(SOURCE_BUS_OWNER, False,
                            reason=f"bus owner view timed out after {SAC_TIMEOUT_S:.0f} s")
    except (OSError, subprocess.SubprocessError) as exc:
        return SourceResult(SOURCE_BUS_OWNER, False,
                            reason=f"bus owner view could not run ({type(exc).__name__})")
    if proc.returncode != 0:
        # stderr is not carried: an error message can quote an entry.
        return SourceResult(SOURCE_BUS_OWNER, False,
                            reason=f"bus owner view exited {proc.returncode}")
    try:
        view = json.loads(proc.stdout)
    except (ValueError, TypeError):
        return SourceResult(SOURCE_BUS_OWNER, False, reason="bus owner view did not parse")
    if not isinstance(view, dict) or view.get("schema") != SAC_OWNER_SCHEMA:
        return SourceResult(SOURCE_BUS_OWNER, False,
                            reason=f"bus owner view is not {SAC_OWNER_SCHEMA}")
    entries = view.get("open")
    if not isinstance(entries, list):
        return SourceResult(SOURCE_BUS_OWNER, False, reason="bus owner view has no open list")

    items: List[Dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        room = entry.get("room")
        entry_id = entry.get("id")
        if not isinstance(room, str) or not isinstance(entry_id, str):
            continue
        sender = entry.get("from")
        etype = entry.get("type")
        items.append(_item(
            SOURCE_BUS_OWNER, f"bus:{room}:{entry_id}",
            kind=str(etype).lower() if isinstance(etype, str) and etype else "entry",
            title=_first_line(entry.get("text")),
            since=_parse_ts(entry.get("ts")),
            agent=sender if isinstance(sender, str) else None,
            room=room,
        ))
    return SourceResult(SOURCE_BUS_OWNER, True, items=items)


# --------------------------------------------------------------------------- #
# the aggregator
# --------------------------------------------------------------------------- #

Adapter = Callable[[float], SourceResult]

#: name -> adapter. Looked up by NAME at call time (not bound at import), so a
#: test that replaces one module function replaces it here too.
_ADAPTERS: Dict[str, str] = {
    SOURCE_AGENT_QUESTIONS: "collect_agent_questions",
    SOURCE_RUN_STATE: "collect_run_state",
    SOURCE_PROJECT_QUESTIONS: "collect_project_questions",
    SOURCE_BUS_OWNER: "collect_bus_owner",
}


def _run_adapter(name: str, adapter: Adapter, now: float) -> SourceResult:
    try:
        result = adapter(now)
    except Exception as exc:
        # The source NAME and the exception TYPE — never the message, which can
        # quote the content that failed to parse.
        logger.warning("fleet waiting: source %s failed (%s); reported as unmeasured",
                       name, type(exc).__name__)
        return SourceResult(name, False, reason=f"source failed ({type(exc).__name__})")
    if not isinstance(result, SourceResult):
        logger.warning("fleet waiting: source %s returned no result; reported as unmeasured", name)
        return SourceResult(name, False, reason="source returned no result")
    if not result.measured:
        # Unmeasured sources carry no items: a partial list next to "unmeasured"
        # would be counted by somebody.
        result.items = []
    return result


def _since_key(item: Dict[str, Any]):
    since = item.get("since")
    # Oldest first; items with no measured start go last rather than being
    # given a stand-in time that would place them somewhere they are not.
    return (since is None, since if isinstance(since, (int, float)) else 0.0)


def build_queue(now: Optional[float] = None, *,
                adapters: Optional[Dict[str, Adapter]] = None) -> Dict[str, Any]:
    """The owner's queue.

    ``{"sources": [{name, measured, reason, count, ...}] (exactly the four, in
    `SOURCES` order), "total": sum over measured sources, "unmeasured": how
    many sources were not, "items": [...] oldest first}``

    `adapters` replaces the built-in adapters by source name (tests); a source
    with no adapter is reported unmeasured.
    """
    reference = now if now is not None else time.time()
    lookup = adapters if adapters is not None else {
        name: globals()[fn] for name, fn in _ADAPTERS.items()
    }

    sources: List[Dict[str, Any]] = []
    items: List[Dict[str, Any]] = []
    total = 0
    unmeasured = 0
    for name in SOURCES:
        adapter = lookup.get(name)
        if adapter is None:
            result = SourceResult(name, False, reason="no adapter")
        else:
            result = _run_adapter(name, adapter, reference)
        count = len(result.items)
        row: Dict[str, Any] = {
            "name": name, "measured": result.measured,
            "reason": result.reason, "count": count,
        }
        row.update(result.extra)
        sources.append(row)
        if result.measured:
            total += count
            items.extend(result.items)
        else:
            unmeasured += 1

    items.sort(key=_since_key)
    logger.debug(
        "fleet waiting: total=%d unmeasured=%d per-source=%s",
        total, unmeasured,
        ", ".join(f"{s['name']}:{s['count'] if s['measured'] else '-'}" for s in sources),
    )
    return {"sources": sources, "total": total, "unmeasured": unmeasured, "items": items}


__all__: Sequence[str] = (
    "SOURCES", "SourceResult", "build_queue",
    "collect_agent_questions", "collect_run_state",
    "collect_project_questions", "collect_bus_owner",
)
