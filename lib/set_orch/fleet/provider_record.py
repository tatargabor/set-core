"""Which provider each started agent runs on — kept where a service restart cannot reach it.

**Why a file at all.** After the fork nothing on the process tree says which
provider an agent is talking to: the environment that decided it belongs to a
child this service no longer owns, and `/proc/<pid>/environ` is only readable
while the process lives and only says what it was *given*, not which level
decided. The owning service holds the answer in memory for exactly as long as it
runs — and it is restarted by an ordinary `systemctl restart`, after which every
agent it started is still alive and every answer about them is gone.

That gap is not cosmetic. A per-project credential means the level that won
decides **whose account is billed**, and an agent quietly resumed on the machine
default spends against a different one with nothing on any screen saying so.

## Two properties, both failure-directional

**An agent with no entry is UNRECORDED, never "on the default".** The two are
different facts and only one of them is known. Answering with the default would
be the false-value class in its most expensive direction: a confident,
plausible, wrong statement about who is paying. Every reader here gets `None`
and has to say so.

**Nothing secret is ever written.** The provider's identifier, the model's name,
and the LEVEL that supplied each field — never a token, never an endpoint
carrying one, never a header. The provenance's usefulness is the level, which is
also the half that is safe.

Keyed on the **unit**, not the label: a label can be renamed while the agent
keeps running, and the unit is what `recover()` addresses and what survives in
systemd across this service's restart.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

#: Exactly what an entry may carry. Built field by field rather than by copying
#: an input dict, so a field added upstream — a resolved environment, an argv,
#: a credential — cannot reach the file by being passed along. The same
#: discipline `roster.ENTRY_FIELDS` uses, for the same reason.
ENTRY_FIELDS = ("provider", "model", "provenance", "recorded_at")

EMPTY: Dict[str, Any] = {"version": 1, "agents": {}}


def default_record_path() -> str:
    """The framework's durable per-user store — beside `fleet-roster.json`.

    Resolved here rather than imported from `roster`: two documents with two
    lifetimes, and a shared resolver would make a change to one silently move
    the other.
    """
    root = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share")
    return os.path.join(root, "set-core", "fleet-providers.json")


def _load(path: str) -> Dict[str, Any]:
    """The document, or an empty one. An unreadable file is never fatal.

    A start must not fail because this record cannot be read — the record exists
    to describe a start, and letting it veto one would invert that. The loss is
    logged, because a file that silently resets is indistinguishable from one
    that was never written.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        return dict(EMPTY, agents={})
    except (OSError, ValueError) as exc:
        logger.warning("fleet providers: %s is unreadable (%s); starting empty", path, exc)
        return dict(EMPTY, agents={})
    if not isinstance(raw, dict) or not isinstance(raw.get("agents"), dict):
        logger.warning("fleet providers: %s has an unexpected shape; starting empty", path)
        return dict(EMPTY, agents={})
    agents = {
        str(unit): {f: entry.get(f) for f in ENTRY_FIELDS}
        for unit, entry in raw["agents"].items()
        if isinstance(entry, dict)
    }
    return {"version": 1, "agents": agents}


def _write_atomically(payload: Dict[str, Any], path: str) -> None:
    """Rename over the old file, so a reader never sees a half-written one.

    `0600`: the document names which account each agent bills, which is not
    secret but is nobody else's business on a shared machine.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".fleet-providers-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def record(unit: str, *, provider: str, model: str,
           provenance: Optional[Dict[str, str]] = None,
           path: Optional[str] = None) -> None:
    """Write what one start decided. Called at the start, never at a read."""
    target = path or default_record_path()
    document = _load(target)
    document["agents"][str(unit)] = {
        "provider": provider,
        "model": model,
        # Levels only. `resolve()` already guarantees this dict holds no secret;
        # the values are re-stringified here so a future shape change upstream
        # cannot smuggle a structure through.
        "provenance": {str(k): str(v) for k, v in (provenance or {}).items()},
        "recorded_at": time.time(),
    }
    _write_atomically(document, target)
    logger.info("fleet providers: recorded %s on %s/%s", unit, provider, model)


def get(unit: str, *, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """What was recorded for this unit, or `None` — which means UNRECORDED.

    ⚠ `None` must never be turned into the machine default by a caller. That is
    the whole point of this module returning it.
    """
    entry = _load(path or default_record_path())["agents"].get(str(unit))
    return dict(entry) if entry else None


def forget(unit: str, *, path: Optional[str] = None) -> bool:
    """Drop one unit's entry — for a stop, so the file does not grow forever.

    Returns whether anything was there. A caller that logs the difference can
    tell "cleaned up" from "there was nothing", which are different facts.
    """
    target = path or default_record_path()
    document = _load(target)
    if str(unit) not in document["agents"]:
        return False
    document["agents"].pop(str(unit))
    _write_atomically(document, target)
    logger.info("fleet providers: forgot %s", unit)
    return True
