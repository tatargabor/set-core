"""One agent asking another project for something — the engagement record.

Layer 1 (abstract). The bus carries the request; nothing on it says whether the request was
ever answered. Measured 2026-11-23 over two weeks of traffic: 379 cross-project requests and
questions, 44 with a reply linked to them, and for the rest no way to tell an answer from an
unrelated entry by the same project. This module is the record that makes "still open" a
fact a screen can show.

## A pointer, never a copy

An engagement holds who asked, which project was addressed, and **where the request is on the
bus** — its room and its timestamp. The request's text is not stored: there is one copy, on
the bus, under the bus's own audience rule. No field of this record can hold request or reply
text; the only free text is an optional short subject the asker supplies for the map.

## Closure is the bus's own link, read from headings only

An engagement is answered when an entry by a seat of the addressed project, in the same room,
links to the request's timestamp. That is the bus's own definition (its `re:`), not a second
one invented here. It is decided by parsing entry **headings** — the same structural line
`fleet/channels.py` holds: a heading is the only line that is matched, and nothing below it
can reach a payload or a log.

Heading shapes, verbatim from the bus's writer (`measurements.md` M5)::

    ## <ts> — REQUEST → <addressee>
    ## <ts> — ANSWER (re: <request ts>)
    ## <ts> — FACT

The sender is the FILE NAME (`channels/<room>/<seat>.md`), not a field of the heading.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .. import local_config
from .channels import resolve_store_root
from .mandate import atomic_write_json, file_lock

logger = logging.getLogger(__name__)

STATES = ("resolving", "open", "answered", "failed", "withdrawn")
#: States that count against an asker's bound and keep a desk alive.
LIVE_STATES = ("resolving", "open")
KINDS = ("REQUEST", "QUESTION")
SOURCES = ("ask", "room")

#: Why an engagement failed — classes, never prose, so a caller does not grep a sentence.
FAIL_CLASSES = (
    "unknown-project", "archived", "start-location", "not-on-bus", "not-trusted",
    "unmeasured", "desk-not-ready", "start-refused", "owner-unavailable", "send-failed",
)

#: What became of waking the asker when its request was answered (fleet-reply-wake). Every
#: outcome is final: one reply wakes at most once. `busy` is never recorded — the next round
#: looks again.
WAKE_OUTCOMES = ("woken", "moved", "operator-present", "off-here", "not-fleet-held", "gone", "too-old")

CONFIG_WAITING_MINUTES = "fleet_engagement_waiting_minutes"
CONFIG_MAX_OPEN = "fleet_engagement_max_open"
DEFAULT_WAITING_MINUTES = 30.0
DEFAULT_MAX_OPEN = 5

#: An ended engagement is kept this long, then pruned on the next write.
RETENTION_SECONDS = 30 * 24 * 3600
SUBJECT_MAX = 80
VERSION = 1

#: A heading: ISO timestamp, an em dash, the type — and, for a reply, the link. Anchored on
#: the WHOLE line; a body line that merely contains `(re: …)` is not a heading.
_HEADING = re.compile(
    r"^## (?P<ts>\d{4}-\d\d-\d\dT[0-9:.+\-Z]+) — (?P<type>[A-Z]+)"
    r"(?: → (?P<to>.*?))?(?: \(re: (?P<re>\S+?)\))?\s*$"
)

__all__ = [
    "STATES", "LIVE_STATES", "KINDS", "WAKE_OUTCOMES", "FAIL_CLASSES", "EngagementError", "BusUnreadable",
    "EngagementStore", "default_store_path", "project_of", "linked_reply", "refresh",
    "unlinked_answer", "room_requests", "adopt_room_requests", "adoption_since", "relation_projects",
    "seen_by",
    "waiting_seconds", "max_open", "view",
]


class EngagementError(ValueError):
    def __init__(self, message: str, kind: str, open_engagements: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.open = open_engagements or []


class EngagementStoreUnreadable(RuntimeError):
    """The store exists and could not be parsed. Never treated as an empty store."""


class BusUnreadable(RuntimeError):
    """The bus store could not be read, so engagement states are UNMEASURED, not open."""


def default_store_path() -> str:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return os.path.join(base, "set-core", "fleet-engagements.json")


def _number(key: str, default: float) -> float:
    raw = local_config.get(key)
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"local config {key}={raw!r} is not a number")
    if value <= 0:
        raise ValueError(f"local config {key}={raw!r} must be positive")
    return value


def waiting_seconds() -> float:
    return _number(CONFIG_WAITING_MINUTES, DEFAULT_WAITING_MINUTES) * 60.0


def max_open() -> int:
    return int(_number(CONFIG_MAX_OPEN, DEFAULT_MAX_OPEN))


def project_of(seat: str) -> str:
    """The project a seat belongs to: `proj#abcd1234` and `proj@machine#abcd` are both `proj`."""
    return seat.split("#", 1)[0].split("@", 1)[0]


def _text(value: Any, limit: Optional[int] = None) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        value = " ".join(value.split())
        return value[:limit] if limit else value
    return None


def _normalise(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict) or not _text(raw.get("id")) or not _text(raw.get("project")):
        return None
    state = raw.get("state") if raw.get("state") in STATES else "failed"
    return {
        "id": raw["id"],
        "asker": _text(raw.get("asker")),
        "asker_mandate": _text(raw.get("asker_mandate")),
        "project": _text(raw.get("project")),
        "desk_label": _text(raw.get("desk_label")),
        "desk_seat": _text(raw.get("desk_seat")),
        "desk_mandate": _text(raw.get("desk_mandate")),
        "kind": raw.get("kind") if raw.get("kind") in KINDS else "REQUEST",
        # fleet-room-request-adoption: `ask` was opened by set-fleet-ask, `room` was found
        # posted straight into a relation room and adopted.
        "source": raw.get("source") if raw.get("source") in SOURCES else "ask",
        "subject": _text(raw.get("subject"), SUBJECT_MAX),
        "room": _text(raw.get("room")),
        "ts": _text(raw.get("ts")),
        "state": state,
        "reason": raw.get("reason") if raw.get("reason") in FAIL_CLASSES else None,
        "opened_at": raw.get("opened_at") if isinstance(raw.get("opened_at"), (int, float)) else None,
        "sent_at": raw.get("sent_at") if isinstance(raw.get("sent_at"), (int, float)) else None,
        "closed_at": raw.get("closed_at") if isinstance(raw.get("closed_at"), (int, float)) else None,
        "answer_ts": _text(raw.get("answer_ts")),
        # fleet-engagement-takeover: when the desk was last interrupted for this request, and
        # how many times the request has been handed to a fresh desk.
        "nudged_at": raw.get("nudged_at") if isinstance(raw.get("nudged_at"), (int, float)) else None,
        "handovers": raw.get("handovers") if isinstance(raw.get("handovers"), int)
        and not isinstance(raw.get("handovers"), bool) and raw.get("handovers") > 0 else 0,
        # fleet-reply-wake: whether the asker was woken when the reply arrived, and when.
        "asker_wake": raw.get("asker_wake") if raw.get("asker_wake") in WAKE_OUTCOMES else None,
        "asker_wake_at": raw.get("asker_wake_at") if isinstance(raw.get("asker_wake_at"), (int, float)) else None,
    }


class EngagementStore:
    """The machine-local engagement document. Every mutation is one locked read-modify-write."""

    def __init__(self, path: Optional[str] = None, *, clock: Callable[[], float] = time.time) -> None:
        self.path = path or default_store_path()
        self._clock = clock

    def _load(self) -> Dict[str, Dict[str, Any]]:
        import json

        try:
            with open(self.path, encoding="utf-8") as handle:
                raw = json.load(handle)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            logger.warning("fleet engagement: store unreadable (%s)", type(exc).__name__)
            raise EngagementStoreUnreadable(type(exc).__name__) from exc
        records = raw.get("engagements") if isinstance(raw, dict) else None
        if not isinstance(records, dict):
            raise EngagementStoreUnreadable("shape")
        out = {}
        for key, value in records.items():
            record = _normalise(value)
            if record is not None and record["id"] == key:
                out[key] = record
        return out

    def _save(self, records: Dict[str, Dict[str, Any]]) -> None:
        now = self._clock()
        stale = [
            key for key, rec in records.items()
            if rec["state"] not in LIVE_STATES and now - float(rec["closed_at"] or now) > RETENTION_SECONDS
        ]
        for key in stale:
            del records[key]
        if stale:
            logger.info("fleet engagement: pruned %d closed engagement(s) past retention", len(stale))
        atomic_write_json({"version": VERSION, "engagements": records}, self.path)

    # -- reading ----------------------------------------------------------------

    def all(self) -> Dict[str, Dict[str, Any]]:
        return self._load()

    def get(self, engagement_id: str) -> Optional[Dict[str, Any]]:
        return self._load().get(engagement_id)

    def list(self, *, asker: Optional[str] = None, project: Optional[str] = None,
             state: Optional[str] = None) -> List[Dict[str, Any]]:
        out = [
            r for r in self._load().values()
            if (asker is None or r["asker"] == asker)
            and (project is None or r["project"] == project)
            and (state is None or r["state"] == state)
        ]
        return sorted(out, key=lambda r: r["opened_at"] or 0)

    def live_for_desk(self, project: str) -> int:
        """How many engagements keep this project's desk alive."""
        return sum(1 for r in self._load().values()
                   if r["project"] == project and r["state"] in LIVE_STATES)

    def live_asked_by(self, seat: Optional[str]) -> int:
        """How many live engagements a seat itself asked — it is waiting on their answers."""
        if not seat:
            return 0
        return sum(1 for r in self._load().values()
                   if r["asker"] == seat and r["state"] in LIVE_STATES)

    # -- writing ----------------------------------------------------------------

    def open(self, *, asker: Optional[str], project: str, kind: str = "REQUEST",
             subject: Optional[str] = None, asker_mandate: Optional[str] = None,
             limit: Optional[int] = None) -> Dict[str, Any]:
        """Record a new engagement in `resolving`. Refused when the asker is at its bound."""
        if kind not in KINDS:
            raise EngagementError(f"unknown engagement kind: {kind!r}", "unknown-kind")
        if not _text(project):
            raise EngagementError("an engagement needs a project", "no-project")
        limit = max_open() if limit is None else limit
        with file_lock(self.path):
            records = self._load()
            if asker:
                held = [r for r in records.values()
                        if r["asker"] == asker and r["state"] in LIVE_STATES]
                if len(held) >= limit:
                    logger.info("fleet engagement: refused — the asker holds %d open (bound %d)",
                                len(held), limit)
                    raise EngagementError(
                        f"this agent already has {len(held)} open engagement(s); the bound is {limit}",
                        "bound", sorted(held, key=lambda r: r["opened_at"] or 0))
            record = _normalise({
                "id": "e-" + secrets.token_hex(6), "asker": asker, "asker_mandate": asker_mandate,
                "project": project, "kind": kind, "subject": subject, "state": "resolving",
                "opened_at": self._clock(),
            })
            assert record is not None
            records[record["id"]] = record
            self._save(records)
        logger.info("fleet engagement: %s opened (kind=%s state=resolving)", record["id"], kind)
        return record

    def _transition(self, engagement_id: str, allowed_from: tuple, **fields: Any) -> Optional[Dict[str, Any]]:
        with file_lock(self.path):
            records = self._load()
            record = records.get(engagement_id)
            if record is None:
                return None
            if record["state"] not in allowed_from:
                # A late report must not reopen or overwrite a decided engagement.
                logger.info("fleet engagement: %s is %s; transition to %s ignored",
                            engagement_id, record["state"], fields.get("state"))
                return dict(record)
            old = record["state"]
            record.update(fields)
            self._save(records)
        logger.info("fleet engagement: %s state: %s -> %s%s", engagement_id, old, record["state"],
                    f" ({record['reason']})" if record.get("reason") else "")
        return dict(record)

    def set_desk(self, engagement_id: str, *, label: Optional[str], seat: Optional[str],
                 mandate_id: Optional[str]) -> Optional[Dict[str, Any]]:
        return self._transition(engagement_id, ("resolving",), state="resolving",
                                desk_label=_text(label), desk_seat=_text(seat),
                                desk_mandate=_text(mandate_id))

    def mark_sent(self, engagement_id: str, *, room: str, ts: str) -> Optional[Dict[str, Any]]:
        if not _text(room) or not _text(ts):
            raise EngagementError("a sent engagement needs the entry's room and timestamp", "no-pointer")
        return self._transition(engagement_id, ("resolving",), state="open",
                                room=_text(room), ts=_text(ts), sent_at=self._clock())

    def mark_failed(self, engagement_id: str, reason: str) -> Optional[Dict[str, Any]]:
        if reason not in FAIL_CLASSES:
            raise EngagementError(f"unknown failure class: {reason!r}", "unknown-reason")
        return self._transition(engagement_id, ("resolving",), state="failed",
                                reason=reason, closed_at=self._clock())

    def withdraw(self, engagement_id: str) -> Optional[Dict[str, Any]]:
        return self._transition(engagement_id, LIVE_STATES, state="withdrawn",
                                closed_at=self._clock())

    def mark_nudged(self, engagement_id: str) -> Optional[Dict[str, Any]]:
        """The desk was interrupted for this request. The state stays `open`."""
        return self._transition(engagement_id, ("open",), state="open", nudged_at=self._clock())

    def mark_handover(self, engagement_id: str, *, label: Optional[str], seat: Optional[str],
                      mandate_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """The request now belongs to a fresh desk. Still `open`; the ladder starts over."""
        with file_lock(self.path):
            records = self._load()
            record = records.get(engagement_id)
            if record is None:
                return None
            if record["state"] != "open":
                logger.info("fleet engagement: %s is %s; handover ignored", engagement_id, record["state"])
                return dict(record)
            record.update(desk_label=_text(label), desk_seat=_text(seat),
                          desk_mandate=_text(mandate_id), nudged_at=None,
                          handovers=record["handovers"] + 1)
            self._save(records)
        logger.info("fleet engagement: %s handed over (handovers=%d)", engagement_id, record["handovers"])
        return dict(record)

    def answered_unwoken(self) -> List[Dict[str, Any]]:
        """Answered engagements whose asker has no wake outcome yet (fleet-reply-wake)."""
        return [dict(r) for r in self._load().values() if r["state"] == "answered" and not r.get("asker_wake")]

    def mark_asker_wake(self, engagement_id: str, outcome: str) -> Optional[Dict[str, Any]]:
        if outcome not in WAKE_OUTCOMES:
            raise ValueError(f"unknown wake outcome {outcome!r}")
        with file_lock(self.path):
            records = self._load()
            record = records.get(engagement_id)
            if record is None or record.get("asker_wake"):
                return dict(record) if record else None
            record.update(asker_wake=outcome, asker_wake_at=self._clock())
            self._save(records)
        logger.info("fleet engagement: %s asker wake: %s", engagement_id, outcome)
        return dict(record)

    def adopt(self, *, room: str, ts: str, asker: Optional[str], project: str,
              kind: str = "REQUEST", sent_at: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Record a request found posted straight into a relation room. Idempotent on room+ts.

        Returns the new record, or None when that entry already has an engagement. Not bound by
        the asker's open limit: the request is already on the bus, and refusing to record it
        would not unsend it — it would only make it invisible again.
        """
        if kind not in KINDS:
            raise EngagementError(f"unknown engagement kind: {kind!r}", "unknown-kind")
        if not _text(project) or not _text(room) or not _text(ts):
            raise EngagementError("an adopted engagement needs a project, a room and a timestamp", "no-pointer")
        with file_lock(self.path):
            records = self._load()
            if any(r["room"] == room and r["ts"] == ts for r in records.values()):
                return None
            now = self._clock()
            record = _normalise({
                "id": "e-" + secrets.token_hex(6), "asker": asker, "project": project, "kind": kind,
                "source": "room", "state": "open", "room": room, "ts": ts,
                "opened_at": now, "sent_at": sent_at if sent_at is not None else now,
            })
            assert record is not None
            records[record["id"]] = record
            self._save(records)
        logger.info("fleet engagement: %s adopted from room %s (kind=%s project=%s)",
                    record["id"], room, kind, project)
        return record

    def assign_desk(self, engagement_id: str, *, label: Optional[str], seat: Optional[str],
                    mandate_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """Give an unclaimed engagement its first desk. Not a handover: nobody held it.

        Also recorded when the engagement was answered meanwhile — measured live: the started desk
        answered in 12 s, the round closed the record first, and it no longer named who answered.
        """
        with file_lock(self.path):
            records = self._load()
            record = records.get(engagement_id)
            if record is None:
                return None
            if record["state"] not in ("open", "answered") or record["desk_seat"] or record["desk_label"]:
                logger.info("fleet engagement: %s already claimed or closed; assignment ignored",
                            engagement_id)
                return dict(record)
            record.update(desk_label=_text(label), desk_seat=_text(seat), desk_mandate=_text(mandate_id))
            self._save(records)
        logger.info("fleet engagement: %s assigned to desk %s", engagement_id, record["desk_seat"] or label)
        return dict(record)

    def mark_answered(self, engagement_id: str, answer_ts: str) -> Optional[Dict[str, Any]]:
        return self._transition(engagement_id, ("open",), state="answered",
                                answer_ts=_text(answer_ts), closed_at=self._clock())


# -- closure from the bus --------------------------------------------------------------


def linked_reply(room: str, request_ts: str, project: str,
                 *, store_root: Optional[Path] = None) -> Optional[str]:
    """The timestamp of the earliest entry by `project` in `room` that links to `request_ts`.

    None when there is none. Raises `BusUnreadable` when the room cannot be read at all —
    "nobody answered" and "we could not look" are different answers and only one is a state.
    """
    root = Path(store_root) if store_root is not None else resolve_store_root()
    room_dir = root / "channels" / room
    try:
        files = sorted(p for p in room_dir.iterdir() if p.suffix == ".md")
    except OSError as exc:
        raise BusUnreadable(type(exc).__name__) from exc
    best: Optional[str] = None
    for path in files:
        if project_of(path.stem) != project:
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    # Only a heading is ever matched; every other line is skipped unread.
                    if not line.startswith("## "):
                        continue
                    match = _HEADING.match(line.rstrip("\n"))
                    if match and match.group("re") == request_ts:
                        ts = match.group("ts")
                        if best is None or ts < best:
                            best = ts
        except OSError as exc:
            raise BusUnreadable(type(exc).__name__) from exc
    return best


def _epoch(ts: Any) -> Optional[float]:
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _headings(path: Path):
    """(match) for every heading line of one seat file. Raises OSError."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith("## "):
                continue
            match = _HEADING.match(line.rstrip("\n"))
            if match:
                yield match


def unlinked_answer(room: str, request_ts: str, project: str,
                    *, store_root: Optional[Path] = None) -> Optional[str]:
    """The earliest ANSWER by `project` in `room` after `request_ts` that links to nothing.

    The closure an adopted request needs besides the bus's own link: measured 2026-11-24, 36 of
    66 requests posted straight into a relation room were answered by an unlinked ANSWER. An
    ANSWER linked to a different request does not count. Raises `BusUnreadable`.
    """
    after = _epoch(request_ts)
    if after is None:
        return None
    root = Path(store_root) if store_root is not None else resolve_store_root()
    room_dir = root / "channels" / room
    try:
        files = sorted(p for p in room_dir.iterdir() if p.suffix == ".md")
    except OSError as exc:
        raise BusUnreadable(type(exc).__name__) from exc
    best: Optional[Tuple[float, str]] = None
    for path in files:
        if project_of(path.stem) != project:
            continue
        try:
            for match in _headings(path):
                if match.group("type") != "ANSWER" or match.group("re"):
                    continue
                when = _epoch(match.group("ts"))
                if when is not None and when > after and (best is None or when < best[0]):
                    best = (when, match.group("ts"))
        except OSError as exc:
            raise BusUnreadable(type(exc).__name__) from exc
    return best[1] if best else None


#: A request older than this is never adopted, so a closed record pruned after its retention
#: cannot bring an old request back (fleet-room-request-adoption D3).
ADOPT_MAX_AGE_SECONDS = 24 * 3600.0
#: A request younger than this is left for a round: `set-fleet-ask` posts first and records the
#: timestamp after, and adopting in between would double it.
ADOPT_MIN_AGE_SECONDS = 90.0


def adoption_since(*, path: Optional[str] = None, now: Optional[float] = None) -> float:
    """The epoch adoption was first switched on, created on first use (forward only, D3)."""
    import json

    path = path or os.path.join(os.path.dirname(default_store_path()), "fleet-engagement-adopt.json")
    try:
        with open(path, encoding="utf-8") as handle:
            since = json.load(handle).get("since")
        if isinstance(since, (int, float)) and not isinstance(since, bool):
            return float(since)
        logger.warning("fleet engagement: adoption watermark has no epoch; starting it again")
    except FileNotFoundError:
        pass
    except (OSError, ValueError, AttributeError) as exc:
        logger.warning("fleet engagement: adoption watermark unreadable (%s); starting it again",
                       type(exc).__name__)
    since = time.time() if now is None else now
    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomic_write_json({"since": since}, path)
    logger.info("fleet engagement: adoption switched on; nothing posted before %.0f is adopted", since)
    return since


def relation_projects(room: str) -> Optional[Tuple[str, str]]:
    """The two projects of a relation room `dm-<a>--<b>`, or None for any other room."""
    if not room.startswith("dm-") or room.count("--") != 1:
        return None
    a, b = room[3:].split("--", 1)
    return (a, b) if a and b and a != b else None


def room_requests(*, since: float, now: float,
                  store_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Cross-project requests in relation rooms that adoption may record. Headings only.

    A REQUEST or QUESTION by a seat of one project of the room, unaddressed or addressed to the
    other project by name, between `ADOPT_MIN_AGE_SECONDS` and `ADOPT_MAX_AGE_SECONDS` old and
    not older than `since`. An entry addressed to one session is a conversation, not adopted.
    """
    root = Path(store_root) if store_root is not None else resolve_store_root()
    floor = max(since, now - ADOPT_MAX_AGE_SECONDS)
    out: List[Dict[str, Any]] = []
    try:
        rooms = [p for p in (root / "channels").iterdir() if p.is_dir()]
    except OSError as exc:
        raise BusUnreadable(type(exc).__name__) from exc
    for room_dir in rooms:
        pair = relation_projects(room_dir.name)
        if pair is None:
            continue
        try:
            files = [p for p in room_dir.iterdir() if p.suffix == ".md"]
        except OSError:
            logger.warning("fleet engagement: room %s unreadable; skipped this round", room_dir.name)
            continue
        for path in files:
            sender = project_of(path.stem)
            if sender not in pair:
                continue
            addressed = pair[1] if sender == pair[0] else pair[0]
            try:
                if path.stat().st_mtime < floor:
                    continue
                for match in _headings(path):
                    if match.group("type") not in KINDS:
                        continue
                    to = (match.group("to") or "").strip()
                    if to and to != addressed:
                        continue
                    when = _epoch(match.group("ts"))
                    if when is None or when < floor or now - when < ADOPT_MIN_AGE_SECONDS:
                        continue
                    out.append({"room": room_dir.name, "ts": match.group("ts"), "asker": path.stem,
                                "project": addressed, "kind": match.group("type"), "sent_at": when})
            except OSError:
                logger.warning("fleet engagement: a seat file in %s unreadable; skipped this round",
                               room_dir.name)
    return out


def seen_by(room: str, ts: str, asker: Optional[str], seats: List[str],
            *, store_root: Optional[Path] = None) -> Optional[str]:
    """The first of `seats` whose bus read cursor in `room` is at or past the request. None else.

    The bus keeps, per room and reading seat, the last entry it read from each writer
    (`cursors.json`, key `<room>::<reader>`, value `{writer: ts}`). A live session of the
    addressed project that has read the request has it in front of it: measured 2026-11-24, 81 of
    108 answered room requests were answered after more than five minutes, so a desk started
    then would work in parallel with a session already on it. Unreadable → None, counted as
    unseen: the fail direction keeps a request from stopping, not a duplicate from starting.
    """
    import json

    if not asker or not seats:
        return None
    root = Path(store_root) if store_root is not None else resolve_store_root()
    try:
        with open(root / "cursors.json", encoding="utf-8") as handle:
            cursors = json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        logger.warning("fleet engagement: bus read cursors unreadable (%s); counted as unseen",
                       type(exc).__name__)
        return None
    if not isinstance(cursors, dict):
        return None
    wanted = _epoch(ts)
    for seat in seats:
        entry = cursors.get(f"{room}::{seat}")
        read = _epoch(entry.get(asker)) if isinstance(entry, dict) else None
        if read is not None and wanted is not None and read >= wanted:
            return seat
    return None


def adopt_room_requests(store: EngagementStore, *, store_root: Optional[Path] = None,
                        since: Optional[float] = None, now: Optional[float] = None) -> List[str]:
    """Adopt every untracked cross-project request in a relation room. Returns the new ids."""
    now = time.time() if now is None else now
    if since is None:
        since = adoption_since(path=os.path.join(os.path.dirname(store.path) or ".",
                                                 "fleet-engagement-adopt.json"), now=now)
    known = {(r["room"], r["ts"]) for r in store.all().values() if r["room"] and r["ts"]}
    adopted: List[str] = []
    for found in room_requests(since=since, now=now, store_root=store_root):
        if (found["room"], found["ts"]) in known:
            continue
        record = store.adopt(**found)
        if record is not None:
            adopted.append(record["id"])
    return adopted


def refresh(store: EngagementStore, *, store_root: Optional[Path] = None) -> Dict[str, Any]:
    """Turn every open engagement whose reply the bus links into `answered`.

    Returns `{"measured": bool, "answered": [ids], "unreadable": [ids]}`. An engagement whose
    room could not be read stays `open` in the store and is reported in `unreadable`, so the
    caller can show it as unmeasured rather than as waiting.
    """
    answered: List[str] = []
    unreadable: List[str] = []
    for record in store.list(state="open"):
        if not record["room"] or not record["ts"]:
            continue
        try:
            reply = linked_reply(record["room"], record["ts"], record["project"], store_root=store_root)
            if not reply and record.get("source") == "room":
                reply = unlinked_answer(record["room"], record["ts"], record["project"],
                                        store_root=store_root)
        except BusUnreadable:
            unreadable.append(record["id"])
            continue
        if reply:
            store.mark_answered(record["id"], reply)
            answered.append(record["id"])
    if unreadable:
        logger.warning("fleet engagement: %d open engagement(s) could not be checked against the bus",
                       len(unreadable))
    return {"measured": not unreadable, "answered": answered, "unreadable": unreadable}


def view(record: Dict[str, Any], *, now: Optional[float] = None,
         waiting_after: Optional[float] = None, unmeasured: bool = False) -> Dict[str, Any]:
    """An engagement as a payload. `waiting` is a display state; it changes nothing stored."""
    now = time.time() if now is None else now
    waiting_after = waiting_seconds() if waiting_after is None else waiting_after
    opened = record.get("opened_at")
    age = max(0.0, now - opened) if isinstance(opened, (int, float)) else None
    state = record["state"]
    return {
        "id": record["id"],
        "asker": record["asker"],
        "project": record["project"],
        "desk_label": record["desk_label"],
        "desk_seat": record["desk_seat"],
        "kind": record["kind"],
        "source": record.get("source", "ask"),
        "subject": record["subject"],
        "state": "unmeasured" if (unmeasured and state == "open") else state,
        "stored_state": state,
        "reason": record["reason"],
        "age_seconds": round(age, 1) if age is not None else None,
        "waiting": bool(state == "open" and not unmeasured and age is not None and age > waiting_after),
        "handovers": record.get("handovers", 0),
        "nudged": record.get("nudged_at") is not None,
    }
