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

from . import judgment
from .attention import Queue
from .discovery import discover_agents, discover_projects
from .state import read_state

logger = logging.getLogger(__name__)

__all__ = ["PmSession", "session"]


class PmSession:
    """One machine's PM mode: on/off, the queue, and when the last cycle ran."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.enabled = False
        self.queue = Queue()
        self._watermarks: Dict[int, judgment.Watermark] = {}
        self._last_cycle: Optional[float] = None
        self._last_error: Optional[str] = None
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
        subjects = [
            judgment.Subject(
                pid=a.pid,
                project=project_of.get(a.pid, a.project_name or "unknown"),
                state=states[a.pid].state,
                session_log=a.session_log,
                label=getattr(a, "name", None),
            )
            for a in agents
        ]
        self._logs = {a.pid: a.session_log for a in agents if a.session_log}
        return subjects, states

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
        }


#: One per process. The queue is deliberately not shared or persisted — see the
#: module docstring.
session = PmSession()
