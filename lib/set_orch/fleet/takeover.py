"""Keeping a cross-project request moving — interrupt a stalled desk, then replace it.

Layer 1 (abstract). `fleet-mandate-and-desk` reports a request open past a bound as
*waiting*, a display state that changes nothing. Measured 2026-11-24 (change
`fleet-engagement-takeover`, measurements.md): one request sat three hours behind a desk
whose tool call had lost its process, while the inventory said `working`. The owner's
decision: the fleet takes such a request over on its own, without duplicating a desk that is
really working, and without spending tokens it does not have to.

## The stall test — movement, and work in the background

A desk is **stalled** when its last transcript movement is older than the stall bound AND
the CPU its process tree burns outside the agent's own process is below the background
bound. The agent's own process is excluded on purpose: its spinner redraws exactly while it
hangs (measured: ~9 ms/s on the hung desk). Background CPU that cannot be measured is not
evidence of work; the decision then says it rested on movement alone.

## The ladder

1. **Interrupt.** Esc ends the current turn; one fixed line naming the request (room,
   timestamp, asker — never its text) starts a new one. The session keeps its context, which
   makes this the cheapest recovery there is (measured live: the hung desk took a new turn
   within seconds).
2. **Replace**, one stall bound after the interrupt if the request is still unanswered and
   the desk still stalled — or at once when the desk is gone. The old desk is stopped (the
   label is an enforced identity, so it must be free), its mandate ends `replaced`, and a new
   desk is started with a takeover mandate that points at the request and the predecessor.

A request past the hard ceiling is interrupted once even when its desk moves. After
`max_handovers` replacements nothing more is done: a request that hangs every desk would
otherwise start one every ten minutes forever.

## Why every dependency is passed in

The decision is a pure function of an engagement, a desk row, a CPU rate and a clock; the
watch joins the stores, the inventory, the owner and the resolver through callables. Both can
be tested without any of them.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from .. import local_config
from . import engagement as engagement_mod

logger = logging.getLogger(__name__)

CONFIG_STALL_MINUTES = "fleet_takeover_stall_minutes"
CONFIG_MAX = "fleet_takeover_max"
CONFIG_CPU_PERCENT = "fleet_takeover_cpu_percent"
DEFAULT_STALL_MINUTES = 5.0
DEFAULT_MAX = 2
#: Measured on a hung desk: helpers outside the agent used ~1.7 % of a core. A test run or a
#: build uses tens to hundreds of percent.
DEFAULT_CPU_PERCENT = 5.0

#: What the sampler answers on the first sample of a unit: not "no work" and not "cannot be
#: measured" — "ask again next round". Measured on the first live round after a service
#: restart: every desk was unsampled, so every decision fell back to movement alone, which
#: would interrupt a long test run that writes nothing to the transcript.
PENDING = "pending"

NONE = "none"
INTERRUPT = "interrupt"
REPLACE = "replace"
BOUND = "bound-reached"
#: fleet-room-request-adoption: an adopted request given the project's live desk, or a started one.
ASSIGN = "assign"
START = "start"

#: Pauses between the three writes of an interrupt. The CR is a separate write so the
#: terminal does not take it as part of a paste (measured: 0.8 s works).
ESC_PAUSE_SECONDS = 1.0
SUBMIT_PAUSE_SECONDS = 0.8

__all__ = [
    "NONE", "INTERRUPT", "REPLACE", "BOUND", "PENDING", "Bounds", "bounds", "decide", "CpuSampler",
    "interrupt_line", "TakeoverWatch", "owner_interrupt",
]


@dataclass(frozen=True)
class Bounds:
    stall_seconds: float
    ceiling_seconds: float
    cpu_percent: float
    max_handovers: int
    #: An idle desk (no turn running) that has not moved since the request arrived is
    #: interrupted after this long rather than after the full stall bound: nothing is running
    #: that an Esc could kill, and the bus did not wake it (measurements M4).
    idle_wake_seconds: float = 90.0


def _positive(key: str, default: float) -> float:
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


def bounds() -> Bounds:
    """The bounds from local config. The ceiling is the engagement waiting bound itself."""
    return Bounds(
        stall_seconds=_positive(CONFIG_STALL_MINUTES, DEFAULT_STALL_MINUTES) * 60.0,
        ceiling_seconds=engagement_mod.waiting_seconds(),
        cpu_percent=_positive(CONFIG_CPU_PERCENT, DEFAULT_CPU_PERCENT),
        max_handovers=int(_positive(CONFIG_MAX, DEFAULT_MAX)),
    )


# -- the decision ----------------------------------------------------------------------


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def decide(engagement: Dict[str, Any], desk_row: Optional[Dict[str, Any]], *,
           cpu_percent: Any, asking: int, now: float, b: Bounds) -> Tuple[str, str]:
    """(decision, why) for one OPEN engagement. Pure.

    `desk_row` is the live inventory row of the engagement's desk, or None when it is not
    live. `asking` is how many live engagements that desk itself asked: a desk waiting on
    another project is quiet for a reason, and the request it waits on has its own watch.
    """
    handovers = int(engagement.get("handovers") or 0)

    def act(decision: str, why: str) -> Tuple[str, str]:
        if handovers >= b.max_handovers:
            return BOUND, f"{why}; {handovers} takeover(s) already"
        return decision, why

    if desk_row is None:
        return act(REPLACE, "desk-gone")
    if desk_row.get("state") == "asking":
        # Waiting on the person — the question relay carries that; Esc would kill the question.
        return NONE, "desk-asking-owner"
    if asking > 0:
        return NONE, "desk-waiting-on-its-own-request"

    if cpu_percent == PENDING:
        return NONE, "cpu-sampling"
    moved = _number(desk_row.get("last_movement_seconds"))
    busy = cpu_percent is not None and cpu_percent >= b.cpu_percent
    stalled = moved is not None and moved > b.stall_seconds and not busy
    basis = "movement+cpu" if cpu_percent is not None else "movement-only"
    started = _number(engagement.get("sent_at")) or _number(engagement.get("opened_at")) or now
    age = now - started
    nudged = _number(engagement.get("nudged_at"))

    if nudged is None:
        if (desk_row.get("state") == "quiet" and moved is not None and moved > age
                and age >= b.idle_wake_seconds):
            return act(INTERRUPT, "idle-not-woken")
        if stalled:
            return act(INTERRUPT, f"stalled ({basis})")
        if age > b.ceiling_seconds:
            return act(INTERRUPT, "past-ceiling")
        return NONE, "working" if busy else "moving"
    if stalled and now - nudged >= b.stall_seconds:
        return act(REPLACE, f"still-stalled-after-interrupt ({basis})")
    return NONE, "interrupted-recently" if now - nudged < b.stall_seconds else "moving-after-interrupt"


# -- background CPU --------------------------------------------------------------------


def cgroup_usage_usec(pid: int) -> Optional[int]:
    """CPU microseconds used by the whole cgroup a process lives in, or None when unreadable.

    The cgroup is read from the process itself (`/proc/<pid>/cgroup`), not from a unit name:
    the inventory row carries no unit for a framework-held agent (measured 2026-11-24 — every
    round therefore read "unmeasured", and a desk burning a full core in a test loop was
    interrupted on movement alone).
    """
    try:
        with open(f"/proc/{pid}/cgroup", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        path = next((line.split("::", 1)[1] for line in lines if line.startswith("0::")), None)
        if not path:
            return None
        with open(f"/sys/fs/cgroup{path.strip()}/cpu.stat", encoding="ascii") as handle:
            for line in handle:
                if line.startswith("usage_usec "):
                    return int(line.split()[1])
    except (OSError, ValueError):
        return None
    return None


def process_cpu_usec(pid: int) -> Optional[int]:
    """utime+stime of one process in microseconds, or None."""
    try:
        with open(f"/proc/{pid}/stat", encoding="ascii", errors="replace") as handle:
            fields = handle.read().rsplit(")", 1)[1].split()
        ticks = int(fields[11]) + int(fields[12])   # utime, stime (14th, 15th of the full line)
        return int(ticks * 1_000_000 / os.sysconf("SC_CLK_TCK"))
    except (OSError, ValueError, IndexError):
        return None


class CpuSampler:
    """The background CPU rate of an agent's cgroup between two calls, in percent of one core.

    Keyed by the agent's pid; the previous sample is kept in memory. The first call for a pid
    answers `PENDING`; a read failure or a counter that went backwards answers None.
    """

    def __init__(self, *, cgroup: Callable[[int], Optional[int]] = cgroup_usage_usec,
                 process: Callable[[int], Optional[int]] = process_cpu_usec,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._cgroup = cgroup
        self._process = process
        self._clock = clock
        self._last: Dict[int, Tuple[float, int, int]] = {}

    def rate(self, unit: Optional[str], pid: Optional[int]) -> Any:
        """Percent of one core, `PENDING` on a pid's first sample, None when unmeasurable.

        `unit` is accepted for the caller's convenience and not needed: the cgroup is read
        from the process.
        """
        if not isinstance(pid, int) or isinstance(pid, bool):
            return None
        total, own, now = self._cgroup(pid), self._process(pid), self._clock()
        if total is None or own is None:
            self._last.pop(pid, None)
            return None
        previous = self._last.get(pid)
        self._last[pid] = (now, total, own)
        if previous is None:
            return PENDING
        elapsed = now - previous[0]
        if elapsed <= 0 or total < previous[1] or own < previous[2]:
            return None
        background = (total - previous[1]) - (own - previous[2])
        return max(0.0, background) / (elapsed * 1_000_000) * 100.0


# -- the interrupt ---------------------------------------------------------------------


def interrupt_line(engagement: Dict[str, Any], why: str, *, now: float) -> str:
    """The one line typed into the desk. Pointers only — never the request's text."""
    room, ts, asker = engagement.get("room"), engagement.get("ts"), engagement.get("asker") or "another agent"
    started = _number(engagement.get("sent_at")) or _number(engagement.get("opened_at")) or now
    minutes = max(1, int((now - started) // 60))
    if why == "past-ceiling":
        head = (f"[fleet] The request in bus room {room} at {ts} from {asker} has been open for "
                f"{minutes} min, so the fleet interrupted your turn.")
    else:
        head = (f"[fleet] The request in bus room {room} at {ts} from {asker} is still open and "
                "your session showed no progress, so the fleet interrupted your turn.")
    return (f"{head} Continue it now: re-run only what you still need, with a short bound, then "
            f"answer with a reply linked to it (--re {ts}). If you cannot finish, answer with what "
            "you have and what is left.")


def owner_interrupt(label: str, line: str, *, client: Any = None,
                    sleep: Callable[[float], None] = time.sleep) -> None:
    """Esc, the line, Enter — written into a framework-held terminal through the owner."""
    if client is None:
        from .owner_client import OwnerClient
        client = OwnerClient()
    client.write(label, b"\x1b")
    sleep(ESC_PAUSE_SECONDS)
    client.write(label, " ".join(line.split()).encode("utf-8"))
    sleep(SUBMIT_PAUSE_SECONDS)
    client.write(label, b"\r")


# -- waking the asker when its request is answered (fleet-reply-wake) -------------------

#: A reply older than this wakes nobody: it predates the wake, or something else long since
#: brought it to the asker. 20 min, not the first draft's 2 h: the owner read a 34-minute-old
#: reply as old (2026-11-24, *„ezek régiek 34 percesek"*), and a live wake lands within one
#: round (60 s) of the reply anyway.
WAKE_MAX_AGE_SECONDS = 20 * 60.0
#: Somebody typed into the asker this recently: they are at it, and an Esc-free line would
#: still land in the middle of their typing.
OPERATOR_PRESENT_SECONDS = 120.0
#: The bus's stop hook writes its own entry just after the reply; movement within this slack
#: of the reply is not "moved on".
MOVED_SLACK_SECONDS = 30.0
_IDLE_STATUSES = ("idle", "shell")


def _iso_epoch(value: Any) -> Optional[float]:
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _asker_row(asker: Optional[str], rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The live row of the asking seat: by seat name, else by its session-id suffix (D4)."""
    if not asker:
        return None
    for row in rows:
        if row.get("seat") == asker:
            return row
    suffix = asker.split("#", 1)[1] if "#" in asker else ""
    if len(suffix) >= 8:
        for row in rows:
            if str(row.get("session_id") or "").startswith(suffix):
                return row
    return None


def wake_decision(record: Dict[str, Any], rows: List[Dict[str, Any]], *, now: float,
                  off_here: Callable[[Optional[str]], bool] = lambda label: False) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Whether to wake the asker of an answered engagement, and the row to type into.

    `busy` means: not now, look again next round. Every other outcome but `woken` means: never.
    """
    answered_at = _iso_epoch(record.get("answer_ts")) or _number(record.get("closed_at"))
    if answered_at is None or now - answered_at > WAKE_MAX_AGE_SECONDS:
        return "too-old", None
    row = _asker_row(record.get("asker"), rows)
    if row is None:
        return "gone", None
    if row.get("population") != "started-here" or not row.get("terminal_label"):
        return "not-fleet-held", row
    moved = _number(row.get("last_movement_seconds"))
    if moved is not None and moved < (now - answered_at) - MOVED_SLACK_SECONDS:
        return "moved", row
    if row.get("runtime_status") not in _IDLE_STATUSES or row.get("state") not in ("quiet",):
        return "busy", row
    human = _number(row.get("last_human_input_seconds"))
    if human is not None and human < OPERATOR_PRESENT_SECONDS:
        return "operator-present", row
    if off_here(row.get("terminal_label")):
        return "off-here", row
    return "woken", row


def wake_line(record: Dict[str, Any]) -> str:
    """The one line typed into the asker. Pointers only — never the request's or reply's text."""
    return (f"[fleet] Your request in bus room {record.get('room')} at {record.get('ts')} was answered "
            f"(reply at {record.get('answer_ts')}). Read the reply on the bus and continue your thread.")


def owner_type(label: str, line: str, *, client: Any = None,
               sleep: Callable[[float], None] = time.sleep) -> None:
    """The line, then Enter, into a framework-held terminal at a free prompt — no Esc (D3)."""
    if client is None:
        from .owner_client import OwnerClient
        client = OwnerClient()
    client.write(label, " ".join(line.split()).encode("utf-8"))
    sleep(SUBMIT_PAUSE_SECONDS)
    client.write(label, b"\r")


def wake_askers(engagements: engagement_mod.EngagementStore, rows: List[Dict[str, Any]], *,
                type_line: Callable[[str, str], None] = owner_type,
                off_here: Callable[[Optional[str]], bool] = lambda label: False,
                clock: Callable[[], float] = time.time) -> List[Dict[str, Any]]:
    """One pass over answered engagements whose asker has no wake outcome yet."""
    out = []
    now = clock()
    for record in engagements.answered_unwoken():
        outcome, row = wake_decision(record, rows, now=now, off_here=off_here)
        if outcome == "busy":
            logger.debug("fleet reply wake: %s asker busy; next round", record["id"])
            out.append({"id": record["id"], "wake": outcome})
            continue
        if outcome == "woken":
            try:
                type_line(row["terminal_label"], wake_line(record))
            except Exception as exc:  # noqa: BLE001 — the owner may be restarting
                logger.warning("fleet reply wake: %s could not type into %s (%s); next round",
                               record["id"], row["terminal_label"], type(exc).__name__)
                out.append({"id": record["id"], "wake": "error"})
                continue
            logger.info("fleet reply wake: %s woke %s", record["id"], row["terminal_label"])
        engagements.mark_asker_wake(record["id"], outcome)
        out.append({"id": record["id"], "wake": outcome})
    return out


# -- the watch -------------------------------------------------------------------------


def _desk_row(engagement: Dict[str, Any], rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The live row of the engagement's desk: by its mandate id, else by label and project."""
    wanted = engagement.get("desk_mandate")
    if wanted:
        for row in rows:
            if (row.get("mandate") or {}).get("id") == wanted:
                return row
    label = engagement.get("desk_label")
    for row in rows:
        held = row.get("mandate") or {}
        if (label and row.get("terminal_label") == label and held.get("kind") == "desk"
                and held.get("project") == engagement.get("project") and not held.get("ended")):
            return row
    return None


def _project_desk_row(project: Optional[str], rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The live row of the project's framework desk: a terminal holding an open desk mandate."""
    for row in rows:
        held = row.get("mandate") or {}
        if (held.get("kind") == "desk" and held.get("project") == project and not held.get("ended")
                and row.get("terminal_label")):
            return row
    return None


def _unclaimed(record: Dict[str, Any]) -> bool:
    """An adopted engagement nobody holds yet (fleet-room-request-adoption D4)."""
    return (record.get("source") == "room" and not record.get("desk_seat")
            and not record.get("desk_label") and not record.get("desk_mandate"))


class TakeoverWatch:
    """One round over the open engagements. Every collaborator is a callable.

    `rows` — the live inventory rows; `cpu(unit, pid)` — background CPU percent or None;
    `interrupt(label, line)`; `stop(label)` — stops a framework-held agent;
    `start_desk(project, requested_by, takeover)` — returns a `desk.Desk`.
    """

    def __init__(self, *, engagements: engagement_mod.EngagementStore, mandates: Any,
                 rows: List[Dict[str, Any]], cpu: Callable[[Optional[str], Optional[int]], Optional[float]],
                 interrupt: Callable[[str, str], None], stop: Callable[[str], Any],
                 start_desk: Callable[..., Any], b: Bounds,
                 clock: Callable[[], float] = time.time,
                 seen: Optional[Callable[[str, str, Optional[str], List[str]], Optional[str]]] = None) -> None:
        self.engagements = engagements
        self.mandates = mandates
        self.rows = rows
        self.cpu = cpu
        self.interrupt = interrupt
        self.stop = stop
        self.start_desk = start_desk
        self.b = b
        self.clock = clock
        # fleet-room-request-adoption: which live seat of the project has read a request.
        self.seen = seen or engagement_mod.seen_by

    def run(self) -> List[Dict[str, Any]]:
        out = []
        for record in self.engagements.list(state="open"):
            try:
                out.append(self._one(record))
            except Exception as exc:  # noqa: BLE001 — one engagement must not end the round
                logger.warning("fleet takeover: engagement %s — the round raised %s",
                               record["id"], type(exc).__name__)
                out.append({"id": record["id"], "decision": "error", "why": type(exc).__name__})
        return out

    def _one(self, record: Dict[str, Any]) -> Dict[str, Any]:
        if _unclaimed(record):
            return self._claim(record)
        row = _desk_row(record, self.rows)
        cpu = self.cpu(row.get("unit"), row.get("pid")) if row else None
        asking = self.engagements.live_asked_by(row.get("seat")) if row else 0
        now = self.clock()
        decision, why = decide(record, row, cpu_percent=cpu, asking=asking, now=now, b=self.b)
        moved = row.get("last_movement_seconds") if row else None
        result = {"id": record["id"], "decision": decision, "why": why,
                  "desk": record.get("desk_label"), "moved": moved, "cpu": cpu}
        if decision == NONE:
            logger.debug("fleet takeover: %s kept (%s; moved=%s cpu=%s)", record["id"], why, moved, cpu)
            return result
        logger.info("fleet takeover: %s -> %s (%s; desk=%s moved=%s cpu=%s handovers=%s)",
                    record["id"], decision, why, record.get("desk_label"), moved,
                    f"{cpu:.1f}%" if isinstance(cpu, float) else (cpu or "unmeasured"),
                    record.get("handovers"))
        if decision == INTERRUPT:
            self.interrupt(row["terminal_label"], interrupt_line(record, why, now=now))
            self.engagements.mark_nudged(record["id"])
        elif decision == REPLACE:
            result["new_desk"] = self._replace(record, row)
        return result

    def _claim(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Give an adopted request a desk: the project's live one, else a started one after a grace.

        Neither counts as a handover — nobody held the request, so nobody handed it over.
        """
        result = {"id": record["id"], "desk": None, "moved": None, "cpu": None}
        row = _project_desk_row(record.get("project"), self.rows)
        if row is not None:
            held = row.get("mandate") or {}
            self.engagements.assign_desk(record["id"], label=row.get("terminal_label"),
                                         seat=row.get("seat"), mandate_id=held.get("id"))
            logger.info("fleet takeover: %s -> assign (live desk %s)", record["id"], row.get("terminal_label"))
            return {**result, "decision": ASSIGN, "why": "live-desk", "desk": row.get("terminal_label")}
        now = self.clock()
        started = _number(record.get("sent_at")) or _number(record.get("opened_at")) or now
        if now - started < self.b.stall_seconds:
            logger.debug("fleet takeover: %s unclaimed, within the grace (%.0f s)", record["id"], now - started)
            return {**result, "decision": NONE, "why": "unclaimed-grace"}
        seats = [r["seat"] for r in self.rows
                 if r.get("seat") and engagement_mod.project_of(r["seat"]) == record.get("project")]
        reader = self.seen(record.get("room"), record.get("ts"), record.get("asker"), seats)
        if reader:
            logger.debug("fleet takeover: %s unclaimed but read by live %s; no desk", record["id"], reader)
            return {**result, "decision": NONE, "why": "read-by-a-live-session", "desk": None}
        takeover = {
            "room": record.get("room"), "ts": record.get("ts"), "asker": record.get("asker"),
            "from_seat": None, "from_session": None, "engagement_id": record["id"],
        }
        logger.info("fleet takeover: %s -> start (unclaimed for %.0f s; project %s has no live desk)",
                    record["id"], now - started, record.get("project"))
        desk = self.start_desk(record["project"], requested_by=record.get("asker"), takeover=takeover)
        self.engagements.assign_desk(record["id"], label=desk.label, seat=desk.seat,
                                     mandate_id=desk.mandate_id)
        return {**result, "decision": START, "why": "unclaimed", "desk": desk.label, "new_desk": desk.seat}

    def _replace(self, record: Dict[str, Any], row: Optional[Dict[str, Any]]) -> Optional[str]:
        from_session = row.get("session_id") if row else None
        if not from_session and record.get("desk_mandate"):
            # The desk is gone, so there is no row — but its mandate listed the sessions it ran
            # (measured live: a replaced-because-gone desk handed over with no session).
            held = self.mandates.get(record["desk_mandate"]) or {}
            sessions = held.get("session_ids") or []
            from_session = sessions[-1] if sessions else None
        if row is not None:
            self.stop(row["terminal_label"])
        if record.get("desk_mandate"):
            self.mandates.end(record["desk_mandate"], "replaced")
        takeover = {
            "room": record.get("room"), "ts": record.get("ts"), "asker": record.get("asker"),
            "from_seat": record.get("desk_seat"), "from_session": from_session,
            "engagement_id": record["id"],
        }
        desk = self.start_desk(record["project"], requested_by=record.get("asker"), takeover=takeover)
        self.engagements.mark_handover(record["id"], label=desk.label, seat=desk.seat,
                                       mandate_id=desk.mandate_id)
        logger.info("fleet takeover: %s handed over %s -> %s (mandate %s)", record["id"],
                    record.get("desk_seat"), desk.seat, desk.mandate_id)
        return desk.seat
