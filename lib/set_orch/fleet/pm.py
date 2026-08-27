"""PM mode's wiring — the only place that touches discovery, the model and the clock.

`judgment.py` decides classes and `attention.py` decides order; neither reads a
file or knows a fleet. This module is what joins them to the running system, and
it is deliberately the thin part: everything worth testing lives in the two
modules below it.

## Nothing here is persisted, so nothing survives a restart

The queue holds identities and classes; the text it reasoned about is never
written down. A restart therefore empties it until the next cycle rebuilds it
from live sources — chosen rather than discovered, because the convenient design
(save the queue) is the one that would carry a consumer's session content onto
this machine's disk under set-core's name.

## Off by default, and off means no invocation

The cycle runs only while the mode is on. A framework that judged the fleet
whether or not anyone was looking would spend tokens on a screen nobody opened.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from . import instruct as fleet_instruct
from .owner_client import OwnerClient
from . import judgment
from .attention import Queue
from .cache_heat import read_cache_heat
from ..cost import (
    CACHE_READ_MULTIPLIER, CACHE_WRITE_1H_MULTIPLIER, CACHE_WRITE_5M_MULTIPLIER,
)
from .discovery import discover_agents, discover_projects
from .state import read_state

logger = logging.getLogger(__name__)

__all__ = ["PmSession", "session"]


def _recoverable_usd(session_log: Optional[str]) -> Optional[float]:
    """What answering this agent now still saves, versus after its cache expires.

    The difference between rewriting the cache (2x base input on a one-hour
    entry) and reading it (0.1x) — so it is what the reader's promptness buys,
    not what the session cost.

    Zero once the cache has expired: past the lifetime the money is already
    spent, and hurrying buys nothing. `None` when nothing was measured, and the
    queue keeps that apart from zero — a zero would sort an unmeasured seat in
    with the already-expired.
    """
    heat = read_cache_heat(session_log)
    if heat is None or heat.rewrite_usd is None:
        return None
    if heat.is_cold():
        return 0.0
    read_share = heat.rewrite_usd * (CACHE_READ_MULTIPLIER / (
        CACHE_WRITE_1H_MULTIPLIER if heat.ttl_seconds > 300 else CACHE_WRITE_5M_MULTIPLIER))
    return round(heat.rewrite_usd - read_share, 4)


class PmSession:
    """One machine's PM mode: on/off, the queue, and when the last cycle ran."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.enabled = False
        self.queue = Queue()
        self._watermarks: Dict[int, judgment.Watermark] = {}
        self._last_cycle: Optional[float] = None
        self._last_error: Optional[str] = None
        #: True while a cycle is in flight. One at a time, and never on the
        #: request thread — see `cycle_in_background`.
        self._running = False
        #: pid → session log, kept so `advance` can ask about the presented
        #: agent without a second discovery pass.
        self._logs: Dict[int, str] = {}

    # ----------------------------------------------------------------- #

    def enable(self) -> None:
        """Turn the mode on. Touches no agent — it is a way of looking, not of acting."""
        with self._lock:
            self.enabled = True
        logger.info("fleet pm: mode enabled")

    def disable(self) -> None:
        with self._lock:
            self.enabled = False
        logger.info("fleet pm: mode disabled")

    # ----------------------------------------------------------------- #

    def _subjects(self):
        agents = discover_agents()
        states = {a.pid: read_state(a.session_log, record=a.record) for a in agents}
        projects = discover_projects(agents, registered=[], messaging=None)
        project_of = {pid: p.name for p in projects for pid in p.agent_pids}
        reachable = self._reachable(agents)
        subjects = [
            judgment.Subject(
                pid=a.pid,
                project=project_of.get(a.pid, a.project_name or "unknown"),
                state=states[a.pid].state,
                session_log=a.session_log,
                label=getattr(a, "name", None),
                reachable=reachable(a),
                # Measured HERE because this is the module that touches
                # discovery, the model and the clock — the queue and the
                # judgment layer below it read no files, so the figure has to
                # arrive as an argument.
                recoverable_usd=_recoverable_usd(a.session_log),
            )
            for a in agents
        ]
        self._logs = {a.pid: a.session_log for a in agents if a.session_log}
        return subjects, states

    @staticmethod
    def _reachable(agents):
        """Can the reader ANSWER this agent at all — a terminal, or a bus seat.

        The user's rule, stated 2026-08-20 on seeing one presented: *"PM mode
        behozott egy olyan agentet ami felett nincs kontrollunk. ezeket
        excludeold"*. Presenting an agent nobody can reply to costs the reader
        the one thing the mode promises — that what is on screen is something
        they can deal with — and there is no action that clears it.

        Two channels, and either is enough: a pty the framework holds, or a seat
        on the messaging bus. A log alone is not one; it is a way of LOOKING.

        ## Absent is not the same as unmeasured, and the direction matters

        When the owner cannot be asked or the bus cannot be read, the answer is
        REACHABLE. An agent excluded on the strength of a service being down
        disappears from the queue with nothing to show that it did — the false
        absence this repository keeps finding. A false inclusion, by contrast,
        is visible the moment it is presented, and the reader can dismiss it.
        """
        try:
            owned = {a["pid"] for a in OwnerClient().list_agents() if a.get("pid")}
        except Exception as exc:                       # noqa: BLE001 - see docstring
            logger.debug("fleet pm: the owner could not be asked what it holds: %s", exc)
            owned = None
        try:
            seats = fleet_instruct.seats_cached()
        except Exception as exc:                       # noqa: BLE001
            logger.debug("fleet pm: the bus could not be asked who exists: %s", exc)
            seats = None

        def reachable(agent) -> bool:
            if owned is None or seats is None:
                return True                            # unmeasured, not absent
            if agent.pid in owned:
                return True                            # a terminal to type into
            return fleet_instruct.instructability(
                getattr(agent, "session_id", None), seats,
            ).instructable

        return reachable

    def cycle(self, *, force: bool = False, now: Optional[float] = None) -> bool:
        """Run one judgement cycle if the period has elapsed. Returns whether it ran.

        Rate-limited here rather than by the caller, because the caller is an
        HTTP endpoint the browser polls: a period enforced client-side is one
        refresh away from not being enforced at all.
        """
        reference = now if now is not None else time.time()
        with self._lock:
            if not self.enabled:
                return False
            if not force and self._last_cycle is not None:
                if reference - self._last_cycle < judgment.CYCLE_SECONDS:
                    return False
            self._last_cycle = reference

        try:
            subjects, states = self._subjects()
        except Exception as exc:
            # The message names the class, never a body — discovery walks
            # consumer trees and its errors can carry paths.
            logger.warning("fleet pm: the fleet could not be read (%s)", exc.__class__.__name__)
            self._last_error = f"the fleet could not be read ({exc.__class__.__name__})"
            return False

        result = judgment.run_pass(subjects, self._watermarks)
        for subject in subjects:
            mark = judgment.watermark_of(subject.session_log)
            if mark is not None:
                self._watermarks[subject.pid] = mark
        self.queue.update(subjects, result, states=states, now=reference)
        self._last_error = None if result.measured else result.reason
        return True

    def cycle_in_background(self) -> bool:
        """Start a cycle on its own thread, if one is due and none is running.

        ⚠ The cycle makes a model call, which takes tens of seconds. Running it
        on the request thread makes the browser's poll hang for that long —
        measured the first time this was wired up, where a `POST` that should
        answer instantly did not answer at all. A surface that freezes while
        deciding what to show is worse than one that shows the previous answer
        and catches up.

        Returns whether a thread was started. `False` covers both "the mode is
        off" and "one is already in flight", which need no distinction here: in
        both cases the caller serves the snapshot it already has.
        """
        with self._lock:
            if not self.enabled or self._running:
                return False
            self._running = True

        def _run() -> None:
            try:
                self.cycle(force=True)
            finally:
                with self._lock:
                    self._running = False

        threading.Thread(target=_run, name="fleet-pm-cycle", daemon=True).start()
        return True

    def due(self, *, now: Optional[float] = None) -> bool:
        """Has the period elapsed since the last cycle?"""
        reference = now if now is not None else time.time()
        if self._last_cycle is None:
            return True
        return reference - self._last_cycle >= judgment.CYCLE_SECONDS

    # ----------------------------------------------------------------- #

    def advance(self) -> bool:
        """Move on IF the presented agent resumed. Never on anything else."""
        head = self.queue.head()
        if head is None:
            return False
        return self.queue.advance_if_dealt_with(self._logs.get(head.pid), pid=head.pid)

    def snapshot(self, *, seconds_since_input: Optional[float] = None) -> Dict[str, Any]:
        """Everything the frame renders, in one payload.

        `seconds_since_input` comes from the browser, because that is where the
        fact lives: the keystroke went into a terminal the client holds. Sending
        it per request keeps the server from having to model a clock it cannot
        see.
        """
        # Showing it IS presenting it. Found on the live screen, not by a test:
        # nothing ever called `present()`, so `_presented` stayed None — and
        # with it the preemption offer (which needs something to preempt), the
        # presented count that drives demotion, and the history the back and
        # forward controls walk. The queue rendered a head and every mechanism
        # hanging off "what is on screen" was dead, silently, while the screen
        # looked right.
        if self.queue.head() is not None:
            self.queue.present()
        head = self.queue.head()
        counts = self.queue.counts
        offer = (
            self.queue.preemption(seconds_since_input=seconds_since_input)
            if head is not None else None
        )
        return {
            "enabled": self.enabled,
            "presented": asdict(head) if head else None,
            "queued": [asdict(i) for i in self.queue.ordered()],
            "counts": asdict(counts),
            "can_go_back": self.queue.can_go_back(),
            "can_go_forward": self.queue.can_go_forward(),
            # What WOULD take the screen, and null while the typing window
            # holds. The client renders a countdown from this; the decision
            # itself is not the client's to make.
            "pending_switch": asdict(offer) if offer else None,
            "last_cycle": self._last_cycle,
            "last_error": self._last_error,
            # A cycle is in flight. Rendered as "still looking", which is
            # neither an empty queue nor a failure — the third thing.
            "cycling": self._running,
        }


#: One per process. The queue is deliberately not shared or persisted — see the
#: module docstring.
session = PmSession()
