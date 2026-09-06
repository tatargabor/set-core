"""Read a project's own development status through its published contract.

This is the transport half of `set_orch.project_status`. The rules that module states
apply here unchanged and are worth repeating at the boundary, because an API is exactly
where they get broken:

**Nothing here is written down.** No file, no state entry, no log of the payload. The
one place a contract answer lingers is `_CACHE`, in memory, for a few seconds, so that a
dashboard polling every 5s does not spawn the project's toolchain every 5s. It dies with
the process. Do not "improve" it into a disk cache — the answers are full of the
project's domain (partner names, reporter addresses, business rules) and set-core's side
of the bargain is that it reads them and forgets them.

**Nothing here invents a value.** A command that failed renders as a gap with its reason,
never as `0`, never as an empty list. `gaps` is part of the response for that reason: the
surface has to be able to show "we could not ask" as distinct from "the answer is none".

**The command name reaches `subprocess`.** It arrives from a URL. Two guards, in order:
the project's own declared command list when it has one, and a name shape that cannot
produce a flag when it does not.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Body, HTTPException, Query

from .helpers import _resolve_project
from ..project_status import (
    StatusConfig,
    StatusResult,
    StatusSnapshot,
    is_valid_command_name,
    query,
    resolve_status_config,
    write,
)

logger = logging.getLogger(__name__)

router = APIRouter()

#: How long an answer may be reused. Short enough that the panel tracks reality, long
#: enough that a 5s poll and three open tabs do not become three subprocesses a second.
CACHE_TTL_SECONDS = 30

#: A slow answer also buys a longer reuse window: an answer that cost
#: `duration` seconds of the project's own toolchain is reused for
#: `DURATION_TTL_FACTOR × duration`, capped. Measured 2026-09-06 (B-139): a
#: project whose `snapshot` command takes ~15 s was re-asked on a 30 s cycle —
#: the subprocess was running essentially continuously. The floor stays
#: `CACHE_TTL_SECONDS`, so cheap commands keep the panel's freshness.
DURATION_TTL_FACTOR = 10
DURATION_TTL_MAX_SECONDS = 600

#: (project_path, command) → (monotonic deadline, result). In memory only. See module docstring.
_CACHE: Dict[Tuple[str, str], Tuple[float, StatusResult]] = {}

#: The routes here run in FastAPI's threadpool, so the cache and the in-flight
#: table are touched from several threads at once.
_CACHE_LOCK = threading.Lock()

#: (project_path, command) → Event for the query currently running. Single-flight:
#: however many pollers stack on an endpoint slower than its own answer — measured
#: live at four concurrent `snapshot` children under the server pid — exactly one
#: subprocess per (project, command) runs; the rest wait and share its answer.
_INFLIGHT: Dict[Tuple[str, str], threading.Event] = {}
_INFLIGHT_LOCK = threading.Lock()


def _ttl_for(duration_seconds: float, ok: bool) -> float:
    """The reuse window an answer earns.

    A failure keeps the short window whatever it cost to produce: a command that
    times out at 30 s must not buy itself five minutes of being unaskable — the
    panel has to see it recover. Only a real answer extends its own lease.
    """
    if not ok:
        return CACHE_TTL_SECONDS
    return min(DURATION_TTL_MAX_SECONDS,
               max(CACHE_TTL_SECONDS, DURATION_TTL_FACTOR * duration_seconds))


def _cached_query(project_path: Path, command: str, cfg: StatusConfig,
                  refresh: bool) -> StatusResult:
    key = (str(project_path), command)
    now = time.monotonic()
    if not refresh:
        with _CACHE_LOCK:
            hit = _CACHE.get(key)
        if hit and hit[0] > now:
            return hit[1]

    # Single-flight: register before asking. The winner runs the subprocess and
    # lands the answer in the cache; everyone who arrived meanwhile waits on the
    # event and reads the same answer instead of spawning their own.
    with _INFLIGHT_LOCK:
        registered = _INFLIGHT.get(key)
        winner = registered is None
        if winner:
            registered = threading.Event()
            _INFLIGHT[key] = registered
    if not winner:
        registered.wait()
        with _CACHE_LOCK:
            hit = _CACHE.get(key)
        if hit is not None:
            return hit[1]
        # The winner raised before it could cache anything. Fall through and ask
        # once here — rare, and bounded by this branch: the next caller finds the
        # key free and becomes the single flight again.

    try:
        started = time.monotonic()
        result = query(project_path, command, config=cfg)
        duration = time.monotonic() - started

        # A failure is cached too, and deliberately: a project whose contract is broken
        # would otherwise be re-spawned on every poll, turning one defect into load.
        with _CACHE_LOCK:
            _CACHE[key] = (time.monotonic() + _ttl_for(duration, getattr(result, "ok", False)),
                           result)
        return result
    finally:
        # Only the thread that registered the event may remove it — a fall-through
        # waiter after a crashed winner must not un-register somebody else's query.
        if winner:
            with _INFLIGHT_LOCK:
                if _INFLIGHT.get(key) is registered:
                    _INFLIGHT.pop(key, None)
        registered.set()


def _contract_info(cfg: Optional[StatusConfig]) -> Dict[str, Any]:
    """What set-core will call, without calling it.

    The displayed command is the argv, joined for reading. It is the project's own
    committed manifest or the operator's own config — neither is a secret from the
    operator looking at this screen.
    """
    if cfg is None:
        return {"configured": False, "source": None, "command": None,
                "commands": [], "writeCommands": [], "primary": None,
                "onDemand": [], "timeout": None, "timeouts": {}, "cwd": None}
    return {
        "configured": True,
        "source": cfg.source,
        "command": " ".join(cfg.argv_prefix),
        "commands": list(cfg.commands),
        "writeCommands": list(cfg.write_commands),
        # Null when the project named nothing usable — which includes naming something
        # unusable. The surface must not be able to tell those apart, or it would start
        # reporting a preference the loader already refused.
        "primary": cfg.primary,
        # Declared read commands the surface must not ask for on its own. Reported so the
        # page can show the tab and say the answer has not been asked for yet — which is
        # a different thing from a gap, and must not render as one.
        "onDemand": list(cfg.on_demand),
        "timeout": cfg.timeout,
        # Per-command overrides, reported because "why did THAT one time out" is the next
        # question after it does, and the answer must not require reading someone's repo.
        "timeouts": {name: seconds for name, seconds in cfg.timeouts},
        "cwd": cfg.cwd,
    }


def _requested_commands(cfg: StatusConfig, requested: Optional[str]) -> list:
    """Decide which commands to ask for, refusing anything the project did not declare.

    With no explicit request, the answer is the project's declared list — set-core keeps
    no default list of its own, because that would make the framework the authority on
    what a project can be asked.
    """
    declared = list(cfg.commands)
    if not requested:
        # A page load asks everything the project declares EXCEPT what it marked as
        # too expensive to ask automatically. Those are still askable — by name, which
        # is what the surface's "ask now" does — so this narrows what happens by itself,
        # never what a person can request.
        return [n for n in declared if n not in cfg.on_demand]

    names = [part.strip() for part in requested.split(",") if part.strip()]
    for name in names:
        if not is_valid_command_name(name):
            raise HTTPException(400, f"not a contract command name: {name!r}")
        if declared and name not in declared:
            raise HTTPException(
                404,
                f"this project does not publish a {name!r} command "
                f"(it declares: {', '.join(declared) or 'nothing'})",
            )
    return names


@router.get("/api/{project}/project-status/contract")
def get_status_contract(project: str):
    """Whether this project publishes a status contract, and what it declares.

    Separate from the data route on purpose: a surface has to be able to say "this
    project publishes nothing" without waiting on a subprocess to tell it so.
    """
    project_path = _resolve_project(project)
    return _contract_info(resolve_status_config(project_path))


@router.get("/api/{project}/project-status")
def get_project_status(
    project: str,
    commands: Optional[str] = Query(None, description="comma-separated command names"),
    refresh: bool = Query(False, description="bypass the short-lived answer cache"),
):
    """Ask the project where it stands, one command per question.

    One command failing never blanks the others; each gap is reported with its reason.
    The response is a transport shape — nothing in it is stored on this side.
    """
    project_path = _resolve_project(project)
    cfg = resolve_status_config(project_path)

    if cfg is None:
        return {
            "project": project,
            "contract": _contract_info(None),
            "ok": False,
            "commands": {},
            "gaps": {},
        }

    names = _requested_commands(cfg, commands)
    if not names:
        # Configured, but nothing declared and nothing asked for. Saying so beats
        # guessing at command names on the project's behalf.
        return {
            "project": project,
            "contract": _contract_info(cfg),
            "ok": False,
            "commands": {},
            "gaps": {
                "*": "the project publishes a status contract but declares no commands — "
                     "ask for one by name, or add a 'commands' list to its manifest",
            },
        }

    snapshot = StatusSnapshot()
    for name in names:
        snapshot.results[name] = _cached_query(project_path, name, cfg, refresh)

    payload = snapshot.to_dict()
    payload["project"] = project
    payload["contract"] = _contract_info(cfg)
    logger.info(
        "project_status API: %s asked %d command(s), %d gap(s)",
        project, len(names), len(payload.get("gaps", {})),
    )
    return payload


@router.post("/api/{project}/project-status/write/{command}")
def post_project_write(project: str, command: str, args: Optional[dict] = Body(None)):
    """Ask the project to record something. set-core never writes; it asks.

    Deliberately a different route from the read one, not a flag on it. The two are
    separated all the way down — declared list, function, endpoint — so that "read
    everything the project offers", which happens on every page load, cannot reach a
    command that changes something no matter how the caller is composed.

    Nothing is cached. On success the read cache for this project is dropped, because
    the answer that was true a moment ago no longer is, and a status panel showing a
    step as un-acknowledged right after acknowledging it is worse than a slow one.
    """
    project_path = _resolve_project(project)
    cfg = resolve_status_config(project_path)

    if cfg is None:
        raise HTTPException(404, "this project publishes no status contract")

    if command not in cfg.write_commands:
        declared = ", ".join(cfg.write_commands) or "none"
        raise HTTPException(
            404,
            f"the project does not publish {command!r} as a write command "
            f"(it declares: {declared})",
        )

    if args is not None and not isinstance(args, dict):
        raise HTTPException(400, "arguments must be an object of {flag: value}")

    result = write(project_path, command, args or {}, config=cfg)

    if result.ok:
        for key in [k for k in _CACHE if k[0] == str(project_path)]:
            _CACHE.pop(key, None)
        logger.info("project_status API: write '%s' ok; read cache dropped", command)

    return {
        "project": project,
        "command": command,
        "ok": result.ok,
        "data": result.data if result.ok else None,
        "error": result.error,
        "errorClass": result.error_class,
        "generatedAt": result.generated_at,
        "contractVersion": result.contract_version,
    }
