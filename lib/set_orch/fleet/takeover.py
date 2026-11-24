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

NONE = "none"
INTERRUPT = "interrupt"
REPLACE = "replace"
BOUND = "bound-reached"

#: Pauses between the three writes of an interrupt. The CR is a separate write so the
#: terminal does not take it as part of a paste (measured: 0.8 s works).
ESC_PAUSE_SECONDS = 1.0
SUBMIT_PAUSE_SECONDS = 0.8

__all__ = [
    "NONE", "INTERRUPT", "REPLACE", "BOUND", "Bounds", "bounds", "decide", "CpuSampler",
    "interrupt_line", "TakeoverWatch", "owner_interrupt",
]


@dataclass(frozen=True)
class Bounds:
    stall_seconds: float
    ceiling_seconds: float
    cpu_percent: float
    max_handovers: int


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
           cpu_percent: Optional[float], asking: int, now: float, b: Bounds) -> Tuple[str, str]:
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

    moved = _number(desk_row.get("last_movement_seconds"))
    busy = cpu_percent is not None and cpu_percent >= b.cpu_percent
    stalled = moved is not None and moved > b.stall_seconds and not busy
    basis = "movement+cpu" if cpu_percent is not None else "movement-only"
    started = _number(engagement.get("sent_at")) or _number(engagement.get("opened_at")) or now
    age = now - started
    nudged = _number(engagement.get("nudged_at"))

    if nudged is None:
        if stalled:
            return act(INTERRUPT, f"stalled ({basis})")
        if age > b.ceiling_seconds:
            return act(INTERRUPT, "past-ceiling")
        return NONE, "working" if busy else "moving"
    if stalled and now - nudged >= b.stall_seconds:
        return act(REPLACE, f"still-stalled-after-interrupt ({basis})")
    return NONE, "interrupted-recently" if now - nudged < b.stall_seconds else "moving-after-interrupt"


# -- background CPU --------------------------------------------------------------------


def cgroup_usage_usec(unit: str) -> Optional[int]:
    """CPU microseconds the scope's cgroup has used, or None when unreadable."""
    try:
        done = subprocess.run(["systemctl", "--user", "show", "-p", "ControlGroup", "--value", unit],
                              capture_output=True, text=True, timeout=10)
        cgroup = (done.stdout or "").strip()
        if done.returncode != 0 or not cgroup:
            return None
        with open(f"/sys/fs/cgroup{cgroup}/cpu.stat", encoding="ascii") as handle:
            for line in handle:
                if line.startswith("usage_usec "):
                    return int(line.split()[1])
    except (OSError, ValueError, subprocess.SubprocessError):
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
    """The background CPU rate of a scope between two calls, in percent of one core.

    The previous sample is kept in memory per unit; the first call for a unit, a read failure,
    or a counter that went backwards (a new scope under an old name) is None — unmeasured.
    """

    def __init__(self, *, cgroup: Callable[[str], Optional[int]] = cgroup_usage_usec,
                 process: Callable[[int], Optional[int]] = process_cpu_usec,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._cgroup = cgroup
        self._process = process
        self._clock = clock
        self._last: Dict[str, Tuple[float, int, int, int]] = {}

    def rate(self, unit: Optional[str], pid: Optional[int]) -> Optional[float]:
        if not unit or not isinstance(pid, int):
            return None
        total, own, now = self._cgroup(unit), self._process(pid), self._clock()
        if total is None or own is None:
            self._last.pop(unit, None)
            return None
        previous = self._last.get(unit)
        self._last[unit] = (now, total, own, pid)
        if previous is None or previous[3] != pid:
            return None
        elapsed = now - previous[0]
        background = (total - previous[1]) - (own - previous[2])
        if elapsed <= 0 or total < previous[1] or own < previous[2]:
            return None
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
                 clock: Callable[[], float] = time.time) -> None:
        self.engagements = engagements
        self.mandates = mandates
        self.rows = rows
        self.cpu = cpu
        self.interrupt = interrupt
        self.stop = stop
        self.start_desk = start_desk
        self.b = b
        self.clock = clock

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
                    "unmeasured" if cpu is None else f"{cpu:.1f}%", record.get("handovers"))
        if decision == INTERRUPT:
            self.interrupt(row["terminal_label"], interrupt_line(record, why, now=now))
            self.engagements.mark_nudged(record["id"])
        elif decision == REPLACE:
            result["new_desk"] = self._replace(record, row)
        return result

    def _replace(self, record: Dict[str, Any], row: Optional[Dict[str, Any]]) -> Optional[str]:
        from_session = row.get("session_id") if row else None
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
