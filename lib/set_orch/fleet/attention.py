"""The attention queue — who the reader deals with next, and when it may change.

Group 3 of the `fleet-pm-mode` change. This module holds no session text, spawns
nothing, and reads no files: it is the policy, given verdicts the judgment layer
produced and facts the state layer measured.

## What is in it, and what deliberately is not

Only agents whose next step is a person's answer. An agent that finished its turn
and asked nothing is **counted, never queued** — measured 2026-08-20, that is 12
of 17 quiet agents on this machine, and queueing them would make the reader
acknowledge a dozen completion reports before reaching a real question. Under the
freeze rule below they would sit *in front of* the questions rather than beside
them.

## Ordered by the money still on the table, freshness where nothing was measured

An agent answered while its prompt cache is still warm resumes from it; one
answered later re-reads its whole context at twenty times the price. Ordering
follows that cost directly: `cache size x (rewrite - read)` while the cache is
live, zero once it has expired.

**This used to be freshness, as a stand-in for exactly that cost, and the
docstring said so — "asserts no particular cache lifetime, it follows the
direction".** The direction was right and the proxy was blind twice. It cannot
see the STAKE: two agents blocked for the same ten minutes may hold caches that
differ more than tenfold, and on this machine live sessions ranged from 15k to
196k tokens. And it cannot see the THRESHOLD: past the lifetime there is nothing
left to save, so a long-blocked agent's position is no longer a cost question,
while freshness kept ranking it as merely "oldest".

Freshness remains, one tier down, for items whose cache was NOT measured. They
are not given a stand-in figure: a zero would sort them with the already-expired
and any positive guess would be a stake nobody measured.

Starvation is the obvious price, and three things pay it: nothing leaves the
queue except by being dealt with, what is queued is counted where the reader is
standing, and an item the reader sat silently in front of is **demoted** when it
returns rather than being presented first all over again.

## Typing is the guard; the countdown is a courtesy

Two separate mechanisms, deliberately. While the reader has typed recently
nothing switches, no countdown appears and nothing is asked. Only a silent screen
can be preempted, and then only by a *fresher* blockage. If the countdown were
the guard the reader would have to watch for it, and a mode that demands
vigilance to avoid losing a half-typed answer is a mode that gets turned off.

## Dealt with means the agent RESUMED

Not "a user entry appeared". Measured on a live log: an interrupt writes exactly
that, so `Esc` would advance the queue — see `state.resumed_since`.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, replace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import judgment
from . import state as agent_state

logger = logging.getLogger(__name__)

__all__ = [
    "TYPING_WINDOW_SECONDS", "COUNTDOWN_SECONDS",
    "Item", "Queue", "Counts",
    "REMOVED_RESUMED", "REMOVED_GONE", "REMOVED_DISMISSED",
]


#: How long after a keystroke the presented item is protected. The HARD guard —
#: while it holds, nothing switches and no countdown is shown.
TYPING_WINDOW_SECONDS = 20.0

#: How long a pending switch is announced before it happens. A courtesy, not the
#: guard: any input cancels it.
COUNTDOWN_SECONDS = 5.0

#: Why an item left the queue. Kept apart because they are three different facts
#: and only one of them means the reader did something.
REMOVED_RESUMED = "resumed"
REMOVED_GONE = "gone"
REMOVED_DISMISSED = "dismissed"


@dataclass(frozen=True)
class Item:
    """One agent waiting on a person.

    Carries an identity, a class and timestamps — and no session content at all.
    The text this queue reasons about is written inside projects that are not
    this framework's; the boundary allows it to be displayed and forbids it
    being written down, so the queue is rebuilt from live sources each cycle
    rather than saved and restored.
    """

    pid: int
    project: str
    label: Optional[str] = None
    #: Which layer concluded it: `structural` (measured) or `model` (an opinion).
    source: str = "model"
    #: Epoch at which the blockage began. The FALLBACK ordering — see
    #: `recoverable_usd`, which outranks it wherever a cache was measured.
    blocked_since: float = 0.0
    #: What answering this agent now still saves, in USD, versus letting its
    #: prompt cache expire first: cache size x (rewrite price - read price)
    #: while the cache is live, zero once it has expired.
    #:
    #: `None` means the cache was NOT MEASURED — no transcript, no usage record —
    #: which is not the same as zero. Zero says "nothing left to save here";
    #: None says "we do not know", and those two must not sort together.
    recoverable_usd: Optional[float] = None
    #: The point `resumed_since` measures from. An epoch, not a formatted time.
    blockage_point: Optional[float] = None
    #: How many times this item has been put in front of the reader without
    #: being dealt with. Non-zero demotes it — their silence is evidence.
    presented_count: int = 0


@dataclass
class Counts:
    """What the always-visible frame has to show.

    `judgment_measured` is the field that must never be confused with
    `queued == 0`. "Nothing needs you" and "we could not look" lead to opposite
    actions, and the first is the one a reader acts on by walking away.
    """

    queued: int = 0
    idle: int = 0
    dismissed: int = 0
    not_covered: int = 0
    unclassified: int = 0
    judgment_measured: bool = True
    judgment_reason: Optional[str] = None
    #: Has any cycle completed? Before the first one every number here is a
    #: default, not a measurement, and rendering `0 waiting` for it would be a
    #: zero nobody produced.
    counted: bool = False


class Queue:
    """The queue, its history, and the rules for changing what is on screen.

    Deliberately a plain object with no I/O. Everything it needs — verdicts,
    states, session logs — is passed in, which is what lets the rules be tested
    without a fleet, a model or a browser.
    """

    def __init__(self) -> None:
        self._items: Dict[int, Item] = {}
        self._presented: Optional[int] = None
        #: Presentation order, oldest first. Stepping back walks this.
        self._history: List[int] = []
        self._history_pos: Optional[int] = None
        self._dismissed: set[int] = set()
        #: Interruptions the reader explicitly refused, keyed by the item that
        #: was on screen when they refused — so refusing does not silence the
        #: same offer forever, only while the screen is unchanged.
        self._refused: Dict[int, set[int]] = {}
        self._counts = Counts()
        #: The last KNOWN class per agent, carried between cycles.
        #:
        #: Found by watching the live screen: `idle` fell 12 → 9 → 1 while
        #: nothing in the fleet changed. The candidate filter deliberately
        #: skips an agent whose log has not moved, so a per-pass count of
        #: `finished` verdicts shrinks every cycle as agents drop out of the
        #: pass — and it renders as agents becoming un-idle. A count is about
        #: the POPULATION; a pass is about what was looked at this time.
        self._classes: Dict[int, str] = {}

    # ----------------------------------------------------------------- #
    # building the queue from a cycle's result
    # ----------------------------------------------------------------- #

    def update(
        self,
        subjects: Sequence[judgment.Subject],
        result: judgment.PassResult,
        *,
        states: Optional[Dict[int, agent_state.AgentState]] = None,
        now: Optional[float] = None,
    ) -> None:
        """Fold one cycle's verdicts in. Never clears what a failed pass did not touch.

        An agent that has gone away leaves the queue; an agent whose verdict is
        no longer `asking` leaves only if the pass that says so was measured —
        an unmeasured pass must not empty the queue, which is exactly the calm
        screen this feature exists to prevent.
        """
        reference = now if now is not None else time.time()
        states = states or {}
        alive = {s.pid for s in subjects}
        by_pid = {s.pid: s for s in subjects}

        # Gone: the agent is not in the population any more.
        for pid in [p for p in self._items if p not in alive]:
            self._remove(pid, REMOVED_GONE)

        for pid, verdict in result.verdicts.items():
            subject = by_pid.get(pid)
            if subject is None:
                continue
            if verdict.verdict == judgment.ASKING:
                if pid in self._dismissed:
                    continue
                st = states.get(pid)
                if st is not None and st.state == agent_state.WORKING:
                    # An explicit refusal rather than an emergent one. The
                    # candidate filter already excludes a working agent, so
                    # today no such verdict can arrive — which is exactly why
                    # the rule needs to be written down here: the queue must
                    # not depend on an upstream filter staying correct for a
                    # guarantee it makes itself.
                    logger.warning(
                        "fleet queue: a verdict says pid %s is asking while the log says it is working; not queued",
                        pid,
                    )
                    continue
                existing = self._items.get(pid)
                if existing is not None:
                    # Already queued. Its blockage did not restart, so its
                    # position must not either — re-dating it here would send
                    # a long-waiting item back to the top on every cycle.
                    continue
                began = _blockage_start(st, reference)
                self._items[pid] = Item(
                    pid=pid,
                    project=subject.project,
                    label=subject.label,
                    source=verdict.source,
                    blocked_since=began,
                    blockage_point=began,
                    recoverable_usd=subject.recoverable_usd,
                )
            elif result.measured and pid in self._items:
                # It stopped asking, and we MEASURED that. An unmeasured pass
                # says nothing about it, so the item stands.
                self._remove(pid, REMOVED_RESUMED)

        # Carried, not recomputed: an agent skipped this cycle keeps the class
        # it was last given, and one that is gone loses it.
        for pid, verdict in result.verdicts.items():
            self._classes[pid] = verdict.verdict
        for pid in [p for p in self._classes if p not in alive]:
            del self._classes[pid]

        self._counts = Counts(
            queued=len(self._items),
            idle=sum(1 for c in self._classes.values() if c == judgment.FINISHED),
            dismissed=len(self._dismissed),
            not_covered=len(result.not_covered),
            unclassified=sum(1 for c in self._classes.values() if c == judgment.UNCLASSIFIED),
            judgment_measured=result.measured,
            judgment_reason=result.reason,
            #: False until a cycle has completed. Distinguishes a real zero
            #: from one nobody has measured yet — the same rule this module
            #: applies to `judgment_measured`, one step earlier.
            counted=True,
        )

    def _remove(self, pid: int, why: str) -> None:
        if self._items.pop(pid, None) is None:
            return
        logger.info("fleet queue: item %s left the queue (%s)", pid, why)
        if self._presented == pid:
            self._presented = None

    # ----------------------------------------------------------------- #
    # order
    # ----------------------------------------------------------------- #

    def ordered(self) -> List[Item]:
        """Reading order: the presented project first, then freshest, unseen first."""
        return _ordered(self._items.values(), self._current_project())

    def _current_project(self) -> Optional[str]:
        item = self._items.get(self._presented) if self._presented else None
        return item.project if item else None

    def head(self) -> Optional[Item]:
        """The item the queue currently presents, or would present next."""
        if self._presented is not None and self._presented in self._items:
            return self._items[self._presented]
        order = self.ordered()
        return order[0] if order else None

    def present(self, pid: Optional[int] = None) -> Optional[Item]:
        """Put an item on screen and record that it was shown.

        Recording the presentation is what makes demotion possible later, so it
        happens here rather than being inferred from a render.
        """
        if pid is None:
            candidate = self.head()
            pid = candidate.pid if candidate else None
        if pid is None or pid not in self._items:
            return None
        # Counted only when the screen actually CHANGES. `present()` is called
        # by advance, dismiss and defer as well as by the reader, so counting
        # every call would inflate the number that decides demotion — and
        # demotion is supposed to mean "the reader sat in front of this and did
        # nothing", not "the queue re-evaluated itself".
        if self._presented != pid:
            self._items[pid] = replace(
                self._items[pid], presented_count=self._items[pid].presented_count + 1,
            )
        self._presented = pid
        if not self._history or self._history[-1] != pid:
            self._history.append(pid)
        self._history_pos = len(self._history) - 1
        self._refused.pop(pid, None)
        return self._items[pid]

    # ----------------------------------------------------------------- #
    # leaving the queue
    # ----------------------------------------------------------------- #

    def advance_if_dealt_with(
        self, session_log: Optional[str], *, pid: Optional[int] = None,
    ) -> bool:
        """Has the presented agent RESUMED? If so, it leaves and the next is presented.

        The only test that counts. `resumed_since` returning unknown leaves the
        item exactly where it is — a queue that advanced on "we could not tell"
        would drop the item nobody has answered.
        """
        target = pid if pid is not None else self._presented
        if target is None or target not in self._items:
            return False
        verdict = agent_state.resumed_since(session_log, self._items[target].blockage_point)
        if verdict != agent_state.RESUMED:
            return False
        self._remove(target, REMOVED_RESUMED)
        self.present()
        return True

    def dismiss(self, pid: int) -> None:
        """The reader is done with this item without answering it.

        It leaves the queue and is COUNTED. A dismissal that vanished would be
        indistinguishable from an item that was never queued.
        """
        if pid in self._items:
            self._dismissed.add(pid)
            self._remove(pid, REMOVED_DISMISSED)
            self._counts.dismissed = len(self._dismissed)
            self._counts.queued = len(self._items)
            self.present()

    def defer(self, pid: Optional[int] = None) -> Optional[Item]:
        """Set the presented item aside. It stays queued, demoted, and counted."""
        target = pid if pid is not None else self._presented
        if target is None or target not in self._items:
            return None
        self._presented = None
        return self.present()

    # ----------------------------------------------------------------- #
    # preemption
    # ----------------------------------------------------------------- #

    def preemption(
        self,
        *,
        seconds_since_input: Optional[float],
        typing_window: float = TYPING_WINDOW_SECONDS,
    ) -> Optional[Item]:
        """What, if anything, may take the screen right now.

        `seconds_since_input` is None when the reader has never typed into the
        presented item — which is not protection, it is the absence of the thing
        protection is measured from.

        Returns None while the typing window holds, whatever else is waiting.
        That is the hard guarantee, and it is checked before anything else here.
        """
        if seconds_since_input is not None and seconds_since_input < typing_window:
            return None
        presented = self._items.get(self._presented) if self._presented else None
        if presented is None:
            return None
        refused = self._refused.get(presented.pid, set())
        # An item the reader has already been shown is not an interruption worth
        # making — they saw it and moved past it. Measured 2026-08-20 in the
        # browser: deferring the presented item handed the screen to the next
        # one, and the deferred item then preempted it back four seconds later,
        # which is exactly the loop deferral exists to break.
        fresher = [
            it for it in self._items.values()
            if it.pid != presented.pid
            and it.blocked_since > presented.blocked_since
            and it.pid not in refused
            and not it.presented_count
        ]
        if not fresher:
            return None
        return max(fresher, key=lambda it: it.blocked_since)

    def refuse(self, pid: int) -> None:
        """The reader declined THIS interruption, while THIS item is on screen."""
        if self._presented is None:
            return
        self._refused.setdefault(self._presented, set()).add(pid)

    # ----------------------------------------------------------------- #
    # history
    # ----------------------------------------------------------------- #

    def back(self) -> Optional[Item]:
        """One step back through what was presented. Marks nothing dealt with."""
        if self._history_pos is None or self._history_pos <= 0:
            return None
        pos = self._history_pos - 1
        while pos >= 0 and self._history[pos] not in self._items:
            pos -= 1
        if pos < 0:
            return None
        self._history_pos = pos
        self._presented = self._history[pos]
        return self._items[self._presented]

    def forward(self) -> Optional[Item]:
        """One step forward, bounded by the queue's own position."""
        if self._history_pos is None or self._history_pos >= len(self._history) - 1:
            return None
        pos = self._history_pos + 1
        while pos < len(self._history) and self._history[pos] not in self._items:
            pos += 1
        if pos >= len(self._history):
            return None
        self._history_pos = pos
        self._presented = self._history[pos]
        return self._items[self._presented]

    def can_go_back(self) -> bool:
        return self.back_target() is not None

    def back_target(self) -> Optional[int]:
        if self._history_pos is None:
            return None
        pos = self._history_pos - 1
        while pos >= 0 and self._history[pos] not in self._items:
            pos -= 1
        return self._history[pos] if pos >= 0 else None

    def can_go_forward(self) -> bool:
        if self._history_pos is None:
            return False
        pos = self._history_pos + 1
        while pos < len(self._history) and self._history[pos] not in self._items:
            pos += 1
        return pos < len(self._history)

    # ----------------------------------------------------------------- #
    # what the frame shows
    # ----------------------------------------------------------------- #

    @property
    def counts(self) -> Counts:
        self._counts.queued = len(self._items)
        self._counts.dismissed = len(self._dismissed)
        return self._counts


def _blockage_start(st: Optional[agent_state.AgentState], now: float) -> float:
    """When this agent's blockage began, from what the state layer measured.

    Two sources, and neither is a guess. A structurally measured blockage knows
    exactly how long its question tool has been open. A quiet agent's turn ended
    when its log last moved. Where neither is available the blockage is dated
    NOW — which ranks it freshest, and that is the safe direction: a new item is
    seen rather than buried.
    """
    if st is None:
        return now
    if st.state == agent_state.ASKING and st.tool_elapsed is not None:
        return now - st.tool_elapsed
    if st.last_movement_age is not None:
        return now - st.last_movement_age
    return now


def _ordered(items: Iterable[Item], current_project: Optional[str]) -> List[Item]:
    items = list(items)
    if not items:
        return []
    # Seen-ness outranks the project. Demotion has to be able to LEAVE the
    # project, or `later` is a dead button: measured 2026-08-20 in the browser
    # with two queued items in two projects — deferring the presented one put it
    # straight back on screen, because its own project was ranked first BY IT.
    # Project exhaustion still holds, one rank down, among items of equal
    # seen-ness, which is where the reader's context switch actually costs.
    unseen = [it for it in items if not it.presented_count]
    # A project is ranked by its freshest UNSEEN item; a project holding only
    # items the reader already skipped must not keep the lead it earned with
    # them. Where a project has no unseen item, its freshest item stands in.
    fresh_unseen: Dict[str, float] = {}
    for it in unseen:
        fresh_unseen[it.project] = max(fresh_unseen.get(it.project, float("-inf")), it.blocked_since)
    freshest: Dict[str, float] = {}
    for it in items:
        if it.project in fresh_unseen:
            freshest[it.project] = fresh_unseen[it.project]
        else:
            freshest[it.project] = max(freshest.get(it.project, float("-inf")), it.blocked_since)
    rank = {p: i for i, p in enumerate(sorted(freshest, key=lambda p: -freshest[p]))}

    def key(it: Item) -> Tuple:
        # Money first, freshness where there is no money to speak of.
        #
        # A measured item sorts by what answering it now SAVES; an unmeasured one
        # keeps the old freshness ordering. The two are kept in separate tiers
        # rather than mixed, because there is no honest number to give an
        # unmeasured item: a zero would sort it with the already-expired, and any
        # positive stand-in would be a stake nobody measured.
        #
        # Within the measured tier, an expired cache scores zero and falls to the
        # bottom of it — correctly. Past expiry the money is already spent, so
        # answering that agent sooner buys nothing, and the item's urgency is no
        # longer a cost question at all.
        measured = it.recoverable_usd is not None
        return (
            1 if it.presented_count else 0,
            0 if it.project == current_project else 1,
            rank[it.project],
            0 if measured else 1,
            -(it.recoverable_usd or 0.0),
            -it.blocked_since,
        )

    return sorted(items, key=key)
