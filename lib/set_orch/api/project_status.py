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
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query

from .helpers import _resolve_project
from ..project_status import (
    StatusConfig,
    StatusResult,
    StatusSnapshot,
    is_valid_command_name,
    query,
    resolve_status_config,
)

logger = logging.getLogger(__name__)

router = APIRouter()

#: How long an answer may be reused. Short enough that the panel tracks reality, long
#: enough that a 5s poll and three open tabs do not become three subprocesses a second.
CACHE_TTL_SECONDS = 30

#: (project_path, command) → (monotonic deadline, result). In memory only. See module docstring.
_CACHE: Dict[Tuple[str, str], Tuple[float, StatusResult]] = {}


def _cached_query(project_path: Path, command: str, cfg: StatusConfig,
                  refresh: bool) -> StatusResult:
    key = (str(project_path), command)
    now = time.monotonic()
    if not refresh:
        hit = _CACHE.get(key)
        if hit and hit[0] > now:
            return hit[1]

    result = query(project_path, command, config=cfg)

    # A failure is cached too, and deliberately: a project whose contract is broken
    # would otherwise be re-spawned on every poll, turning one defect into load.
    _CACHE[key] = (now + CACHE_TTL_SECONDS, result)
    return result


def _contract_info(cfg: Optional[StatusConfig]) -> Dict[str, Any]:
    """What set-core will call, without calling it.

    The displayed command is the argv, joined for reading. It is the project's own
    committed manifest or the operator's own config — neither is a secret from the
    operator looking at this screen.
    """
    if cfg is None:
        return {"configured": False, "source": None, "command": None,
                "commands": [], "timeout": None, "cwd": None}
    return {
        "configured": True,
        "source": cfg.source,
        "command": " ".join(cfg.argv_prefix),
        "commands": list(cfg.commands),
        "timeout": cfg.timeout,
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
        return declared

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
