"""Why an agent was started — the mandate record (capability `agent-mandate-record`).

Layer 1 (abstract). The fleet can say an agent is alive and what it is doing; this module
holds what it could not say: what the agent is *for*, who asked for it, and what closes it.

## Why the record lives here and not in the owner

The agent owner persists nothing, on purpose (`owner.py`: "a line of business logic added
here is a future outage of every running agent"). A relation that exists only in the act of
starting — who asked, and why — therefore has to be written by the process that performs the
act and outlives the agents: the dashboard service. The owner is handed the mandate's **id**
and nothing else; it puts that id into the child's environment, which is what lets the
running process be joined back to its record after the owner has forgotten it.

## Three things this refuses to do

- **Invent a goal.** An agent with no record has no mandate, and the absence carries a reason.
  Nothing is derived from a label, a transcript, a declared focus or a directory.
- **Call a mandate fulfilled.** An agent that ends leaves an `ended` record with a reason
  (`stopped`, `ended`, `desk-quiet`). Whether the work was done is another capability's
  question, answered from evidence.
- **Log its text.** A goal is the operator's own words and may name a client. Log lines carry
  ids, kinds and outcome classes only; the store is readable by its owner only.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import os
import secrets
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional

logger = logging.getLogger(__name__)

KINDS = ("work", "desk")
SOURCES = ("start", "declared")
#: `agent-done`: the agent ran `set-fleet-mandate done` — its OWN claim that the work is
#: over (fleet-work-agent-done). Like the others it says the mandate ended, never that it
#: was fulfilled; checking that is `agent-goal-closure`'s job.
#: `work-idle`: the work sweep closed a work agent that never ran its done step.
#: `replaced`: the takeover watch stopped a stalled or gone desk and started another for its
#: open request (fleet-engagement-takeover).
END_REASONS = ("stopped", "ended", "desk-quiet", "agent-done", "work-idle", "replaced")

#: Why an agent has no mandate. `not-started-here`: the framework did not start it.
#: `not-declared`: the framework started it and nobody gave it a goal.
ABSENT_NOT_STARTED_HERE = "not-started-here"
ABSENT_NOT_DECLARED = "not-declared"
#: The store could not be read. Not the same as having none: the agent may well have one.
ABSENT_UNMEASURED = "unmeasured"

#: The variables the owner sets on the child, and the only identity a running process
#: carries that the framework can MEASURE from outside after the owner restarted.
ENV_MANDATE = "SET_FLEET_MANDATE"
ENV_LABEL = "SET_FLEET_LABEL"

#: How long an ended mandate is kept. Pruned on the next write, with the count logged.
RETENTION_SECONDS = 30 * 24 * 3600

VERSION = 1

__all__ = [
    "KINDS", "SOURCES", "END_REASONS", "ENV_MANDATE", "ENV_LABEL",
    "ABSENT_NOT_STARTED_HERE", "ABSENT_NOT_DECLARED", "ABSENT_UNMEASURED",
    "payload_for", "open_by_label", "for_session", "reserved_desk_project",
    "MandateError", "MandateStoreUnreadable", "MandateStore",
    "default_store_path", "new_id", "desk_label", "mandate_id_of_pid", "join", "absence", "public",
    "atomic_write_json", "file_lock", "unit_alive", "TAKEOVER_FIELDS",
]


class MandateError(ValueError):
    """A mandate that cannot be recorded as given. `kind` names the class for the caller."""

    def __init__(self, message: str, kind: str) -> None:
        super().__init__(message)
        self.kind = kind


class MandateStoreUnreadable(RuntimeError):
    """The store exists and could not be parsed. Never treated as an empty store."""


def default_store_path() -> str:
    """Per-user STATE directory, beside the idle-close log — machine-local, never a repo."""
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return os.path.join(base, "set-core", "fleet-mandates.json")


def new_id() -> str:
    return "m-" + secrets.token_hex(6)


def desk_label(project: str) -> str:
    """The label of a project's desk — its address on the bus as well as on the screen."""
    return f"{project}-desk"


# -- shared write discipline (the engagement store uses the same two helpers) ----------


@contextlib.contextmanager
def file_lock(path: str) -> Iterator[None]:
    """An exclusive lock for one read-modify-write of `path`, held on a sidecar file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def atomic_write_json(payload: Dict[str, Any], path: str) -> None:
    """Temp file then rename. The temp file is created owner-only, so the result is too."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=directory, prefix="." + os.path.basename(path) + ".", delete=False
    )
    try:
        with handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(handle.name, 0o600)
        os.replace(handle.name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(handle.name)
        raise


# -- the record ---------------------------------------------------------------------


def _text(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _scope(raw: Any) -> Dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    paths = [p for p in (raw.get("paths") or []) if isinstance(p, str) and p.strip()]
    return {"paths": paths, "change": _text(raw.get("change"))}


#: The fields a takeover mandate carries: where the request is on the bus, who asked, and
#: which session held it before. Pointers only — never the request's text.
TAKEOVER_FIELDS = ("room", "ts", "asker", "from_seat", "from_session", "engagement_id")


def _takeover(raw: Any) -> Optional[Dict[str, Optional[str]]]:
    if not isinstance(raw, dict):
        return None
    out = {key: _text(raw.get(key)) for key in TAKEOVER_FIELDS}
    # A takeover without the request's place on the bus points nowhere.
    return out if out["room"] and out["ts"] else None


def _normalise(raw: Any) -> Optional[Dict[str, Any]]:
    """One stored record made safe to use, or None for something that is not a record."""
    if not isinstance(raw, dict) or not _text(raw.get("id")):
        return None
    kind = raw.get("kind") if raw.get("kind") in KINDS else "work"
    ended = raw.get("ended")
    if not (isinstance(ended, dict) and ended.get("reason") in END_REASONS):
        ended = None
    return {
        "id": raw["id"],
        "kind": kind,
        "goal": _text(raw.get("goal")),
        "scope": _scope(raw.get("scope")),
        "done_when": _text(raw.get("done_when")),
        "requested_by": _text(raw.get("requested_by")),
        # A requester is whatever the caller said. Nothing verifies it, so it is a claim.
        "requester_is_claim": True,
        "project": _text(raw.get("project")),
        "cwd": _text(raw.get("cwd")),
        "label": _text(raw.get("label")),
        "unit": _text(raw.get("unit")),
        "session_ids": [s for s in (raw.get("session_ids") or []) if isinstance(s, str) and s],
        "source": raw.get("source") if raw.get("source") in SOURCES else "start",
        "delivered": bool(raw.get("delivered")),
        "carrier": bool(raw.get("carrier")),
        "declared_at": raw.get("declared_at") if isinstance(raw.get("declared_at"), (int, float)) else None,
        "ended": ended,
        "takeover": _takeover(raw.get("takeover")),
    }


def public(record: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The record as a payload: every field a surface may show, and no store internals."""
    if record is None:
        return None
    return {k: record[k] for k in (
        "id", "kind", "goal", "scope", "done_when", "requested_by", "requester_is_claim",
        "project", "label", "source", "delivered", "declared_at", "ended", "takeover",
    )}


def absence(*, started_here: bool) -> Dict[str, Any]:
    """What the inventory reports for an agent with no mandate — a reason, never a goal."""
    return {"reason": ABSENT_NOT_DECLARED if started_here else ABSENT_NOT_STARTED_HERE}


class MandateStore:
    """The machine-local mandate document. Every mutation is one locked read-modify-write."""

    def __init__(self, path: Optional[str] = None, *, clock: Callable[[], float] = time.time) -> None:
        self.path = path or default_store_path()
        self._clock = clock

    # -- reading ----------------------------------------------------------------

    def _load(self) -> Dict[str, Dict[str, Any]]:
        try:
            with open(self.path, encoding="utf-8") as handle:
                raw = json.load(handle)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            logger.warning("fleet mandate: store unreadable (%s)", type(exc).__name__)
            raise MandateStoreUnreadable(type(exc).__name__) from exc
        records = raw.get("mandates") if isinstance(raw, dict) else None
        if not isinstance(records, dict):
            logger.warning("fleet mandate: store has no mandate map; refusing to treat it as empty")
            raise MandateStoreUnreadable("shape")
        out: Dict[str, Dict[str, Any]] = {}
        dropped = 0
        for key, value in records.items():
            record = _normalise(value)
            if record is None or record["id"] != key:
                dropped += 1
                continue
            out[key] = record
        if dropped:
            logger.warning("fleet mandate: %d stored entr(ies) were not records and were ignored", dropped)
        return out

    def all(self) -> Dict[str, Dict[str, Any]]:
        return self._load()

    def get(self, mandate_id: str) -> Optional[Dict[str, Any]]:
        return self._load().get(mandate_id)

    # -- writing ----------------------------------------------------------------

    @contextlib.contextmanager
    def _mutate(self) -> Iterator[Dict[str, Dict[str, Any]]]:
        with file_lock(self.path):
            records = self._load()
            yield records
            now = self._clock()
            stale = [
                key for key, rec in records.items()
                if rec["ended"] and now - float(rec["ended"].get("at") or now) > RETENTION_SECONDS
            ]
            for key in stale:
                del records[key]
            if stale:
                logger.info("fleet mandate: pruned %d ended mandate(s) past retention", len(stale))
            atomic_write_json({"version": VERSION, "mandates": records}, self.path)

    def create(
        self,
        *,
        kind: str = "work",
        goal: Optional[str],
        project: Optional[str],
        cwd: Optional[str],
        label: Optional[str],
        unit: Optional[str] = None,
        scope: Optional[Dict[str, Any]] = None,
        done_when: Optional[str] = None,
        requested_by: Optional[str] = None,
        source: str = "start",
        carrier: bool = False,
        session_id: Optional[str] = None,
        mandate_id: Optional[str] = None,
        takeover: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Write a new mandate. A mandate without a goal is not a mandate and is refused.

        `mandate_id` is given when the id was allocated before the record: every framework
        start gets an id in its environment whether or not it has a goal, so a mandate
        declared later can take that id and be found by the agent's own session-start hook.
        """
        if kind not in KINDS:
            raise MandateError(f"unknown mandate kind: {kind!r}", "unknown-kind")
        if source not in SOURCES:
            raise MandateError(f"unknown mandate source: {source!r}", "unknown-source")
        if not _text(goal):
            raise MandateError("a mandate needs a goal", "no-goal")
        record = _normalise({
            "id": _text(mandate_id) or new_id(), "kind": kind, "goal": goal, "scope": scope, "done_when": done_when,
            "requested_by": requested_by, "project": project, "cwd": cwd, "label": label,
            "unit": unit, "session_ids": [session_id] if session_id else [],
            "source": source, "delivered": False, "carrier": carrier,
            "declared_at": self._clock(), "ended": None, "takeover": takeover,
        })
        assert record is not None
        with self._mutate() as records:
            if record["id"] in records:
                raise MandateError("this mandate id is already recorded", "id-taken")
            records[record["id"]] = record
        logger.info(
            "fleet mandate: recorded %s (kind=%s source=%s requester=%s carrier=%s)",
            record["id"], kind, source, "yes" if record["requested_by"] else "no", carrier,
        )
        return record

    def remove(self, mandate_id: str) -> bool:
        """Take back a record whose start never happened. Not for ending a mandate."""
        with self._mutate() as records:
            found = records.pop(mandate_id, None) is not None
        logger.info("fleet mandate: removed %s (start did not happen) found=%s", mandate_id, found)
        return found

    def update(self, mandate_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        """Set identity fields (`label`, `unit`, `carrier`). Text fields are not editable here."""
        allowed = {"label", "unit", "carrier"}
        unknown = set(fields) - allowed
        if unknown:
            raise MandateError(f"not an updatable field: {sorted(unknown)}", "not-updatable")
        with self._mutate() as records:
            record = records.get(mandate_id)
            if record is None:
                return None
            for key, value in fields.items():
                old = record.get(key)
                record[key] = bool(value) if key == "carrier" else _text(value)
                # Label and unit are identity, not the operator's text — safe to log.
                logger.info("fleet mandate: %s %s: %r -> %r", mandate_id, key, old, record[key])
            return dict(record)

    def observe_session(self, mandate_id: str, session_id: str) -> bool:
        """Append a session id the agent was seen running. True when it was new."""
        if not session_id:
            return False
        with file_lock(self.path):
            records = self._load()
            record = records.get(mandate_id)
            if record is None or session_id in record["session_ids"]:
                return False
            record["session_ids"].append(session_id)
            atomic_write_json({"version": VERSION, "mandates": records}, self.path)
        logger.debug("fleet mandate: %s now lists %d session(s)", mandate_id, len(record["session_ids"]))
        return True

    def mark_delivered(self, mandate_id: str) -> bool:
        """The carrier handed the mandate to the agent. True when the flag changed."""
        with file_lock(self.path):
            records = self._load()
            record = records.get(mandate_id)
            if record is None or record["delivered"]:
                return False
            record["delivered"] = True
            atomic_write_json({"version": VERSION, "mandates": records}, self.path)
        logger.info("fleet mandate: %s delivered: False -> True", mandate_id)
        return True

    def end(self, mandate_id: str, reason: str) -> Optional[Dict[str, Any]]:
        """Mark a mandate ended. Never 'fulfilled' — that is not this record's claim to make."""
        if reason not in END_REASONS:
            raise MandateError(f"unknown end reason: {reason!r}", "unknown-reason")
        with self._mutate() as records:
            record = records.get(mandate_id)
            if record is None:
                return None
            if record["ended"] is None:
                record["ended"] = {"at": self._clock(), "reason": reason}
                logger.info("fleet mandate: %s ended: None -> %s", mandate_id, reason)
            return dict(record)

    def resume(self, session_id: str, *, label: Optional[str], unit: Optional[str]) -> Optional[Dict[str, Any]]:
        """Continue the mandate a recorded session held, on the agent restored from it.

        The newest mandate that lists the session is reopened and re-pointed at the restored
        agent's label and unit. Returns it, or None when the session never had a mandate.
        """
        if not session_id:
            return None
        with self._mutate() as records:
            held = [r for r in records.values() if session_id in r["session_ids"]]
            if not held:
                return None
            record = max(held, key=lambda r: r["declared_at"] or 0)
            was = record["ended"]["reason"] if record["ended"] else None
            record["ended"] = None
            record["label"] = _text(label) or record["label"]
            record["unit"] = _text(unit) or record["unit"]
            logger.info("fleet mandate: %s continued on a restored agent (was ended=%s)", record["id"], was)
            return dict(record)

    def reopen(self, mandate_id: str, *, only_reasons: Iterable[str] = ("ended",)) -> Optional[Dict[str, Any]]:
        """Re-open a mandate that was ended for one of `only_reasons`. Returns it, or None.

        For the case where the end was written during a blind spot — a listing that did not
        see a live agent ends it as `ended` — and the agent is then measured alive. Any other
        reason (stopped, replaced, done) was an act, and is not undone here.
        """
        allowed = set(only_reasons)
        with self._mutate() as records:
            record = records.get(mandate_id)
            if record is None or record["ended"] is None or record["ended"].get("reason") not in allowed:
                return None
            was = record["ended"]["reason"]
            record["ended"] = None
        logger.info("fleet mandate: %s re-opened (was ended=%s) — its agent is measured alive",
                    mandate_id, was)
        return dict(record)

    def end_missing(self, alive_ids: Iterable[str], *, grace_seconds: float = 120.0,
                    unit_alive: Optional[Callable[[str], Optional[bool]]] = None) -> List[str]:
        """End every open, started mandate whose agent is gone. Returns the ids ended.

        `alive_ids` are the mandates joined to a live agent in the round just measured. A
        mandate younger than `grace_seconds` is left alone: its agent may not be visible yet,
        and ending it would be a false absence about a process that is starting.

        `unit_alive(unit)` measures the agent's scope directly. Absence from one listing is a
        gap, not a zero (measured 2026-11-24: a listing taken while the service was stopping
        ended a desk that ran on for fifteen minutes and kept its label, and the next request
        to that project failed). A unit measured alive — or whose state cannot be measured —
        keeps its mandate.
        """
        alive = set(alive_ids)
        now = self._clock()
        ended: List[str] = []
        with self._mutate() as records:
            for record in records.values():
                if record["ended"] or record["id"] in alive or record["source"] != "start":
                    continue
                if now - float(record["declared_at"] or now) < grace_seconds:
                    continue
                if unit_alive is not None and record["unit"]:
                    try:
                        live = unit_alive(record["unit"])
                    except Exception as exc:  # noqa: BLE001 — unmeasured, never "gone"
                        logger.warning("fleet mandate: unit state of %s unreadable (%s)",
                                       record["unit"], type(exc).__name__)
                        live = None
                    if live is not False:
                        logger.info("fleet mandate: %s kept although absent from the listing "
                                    "(unit %s %s)", record["id"], record["unit"],
                                    "alive" if live else "unmeasured")
                        continue
                record["ended"] = {"at": now, "reason": "ended"}
                ended.append(record["id"])
        if ended:
            logger.info("fleet mandate: %d mandate(s) ended — their agents are gone", len(ended))
        return ended


def unit_alive(unit: str) -> Optional[bool]:
    """Whether a framework scope still holds a live agent. None when it cannot be measured."""
    try:
        from . import scopes
        return not scopes.scope_is_gone(scopes.get(scopes.as_unit_name(unit)))
    except Exception as exc:  # noqa: BLE001 — a failed measurement is not an absence
        logger.warning("fleet mandate: scope state of %s could not be measured (%s)",
                       unit, type(exc).__name__)
        return None


# -- joining a record to a running agent ------------------------------------------------


def mandate_id_of_pid(pid: int, *, proc_root: str = "/proc") -> Optional[str]:
    """The mandate id in a running process's environment, measured from the process itself.

    None when the platform has no such file, the process is gone, or it carries no mandate —
    the caller falls back to the unit and the session id, and cannot tell those apart from
    here, which is why this is the first step of the join and not the only one.
    """
    try:
        with open(os.path.join(proc_root, str(pid), "environ"), "rb") as handle:
            blob = handle.read()
    except OSError:
        return None
    prefix = ENV_MANDATE.encode() + b"="
    for entry in blob.split(b"\0"):
        if entry.startswith(prefix):
            value = entry[len(prefix):].decode("utf-8", "replace").strip()
            return value or None
    return None


def join(
    records: Dict[str, Dict[str, Any]],
    *,
    pid: Optional[int] = None,
    unit: Optional[str] = None,
    session_id: Optional[str] = None,
    env_reader: Callable[[int], Optional[str]] = mandate_id_of_pid,
) -> Optional[Dict[str, Any]]:
    """The mandate a live agent holds, or None.

    Order is by how much is measured: the id the process itself carries, then the scope unit
    the framework started it under, then a session id the record already lists. An ended
    record is returned only by the first step — the process still carrying the id is stronger
    evidence than the record's own `ended`, which may have been written during a blind spot.
    """
    if pid is not None:
        carried = env_reader(pid)
        if carried and carried in records:
            return records[carried]
    open_records = [r for r in records.values() if r["ended"] is None]
    if unit:
        for record in open_records:
            if record["unit"] == unit:
                return record
    if session_id:
        matches = [r for r in open_records if session_id in r["session_ids"]]
        if matches:
            return max(matches, key=lambda r: r["declared_at"] or 0)
    return None


def payload_for(
    records: Optional[Dict[str, Dict[str, Any]]],
    *,
    pid: Optional[int],
    unit: Optional[str],
    session_id: Optional[str],
    started_here: bool,
) -> Dict[str, Any]:
    """What the inventory says about one agent's mandate.

    `{"mandate": <public record> | None, "absent": {"reason": …} | None, "record": <record>}`.
    `records` is None when the store could not be read — then the answer is `unmeasured`,
    never "none": an unreadable store is not evidence that nobody declared a goal.
    """
    if records is None:
        return {"mandate": None, "absent": {"reason": ABSENT_UNMEASURED}, "record": None}
    record = join(records, pid=pid, unit=unit, session_id=session_id)
    if record is None:
        return {"mandate": None, "absent": absence(started_here=started_here), "record": None}
    return {"mandate": public(record), "absent": None, "record": record}


def for_session(records: Dict[str, Dict[str, Any]], session_id: str) -> Optional[Dict[str, Any]]:
    """The newest mandate that lists a session id — ended or not. Read-only."""
    held = [r for r in records.values() if session_id and session_id in r["session_ids"]]
    return max(held, key=lambda r: r["declared_at"] or 0) if held else None


def open_by_label(records: Dict[str, Dict[str, Any]], label: str) -> Optional[Dict[str, Any]]:
    """The open mandate recorded under a fleet label, newest first. None when there is none."""
    held = [r for r in records.values() if r["ended"] is None and r["label"] == label]
    return max(held, key=lambda r: r["declared_at"] or 0) if held else None


def reserved_desk_project(label: str, project_names: Iterable[str]) -> Optional[str]:
    """The registered project whose desk label this is, or None.

    A desk's label is its address: nothing that is not that project's desk may take it.
    """
    for name in project_names:
        if label == desk_label(name):
            return name
    return None
