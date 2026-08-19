"""Carrying an instruction to a running agent, and reporting what became of it.

Group 4. This is the half of the fleet that WRITES, and every rule in it exists
because the writing half fails in a reassuring direction: a send that was
accepted looks exactly like a message that arrived.

## Why the bus and not the terminal

A session running in someone else's terminal cannot be typed into —
`dev.tty.legacy_tiocsti = 0` refuses the injection, and that is a boundary of
the system rather than an obstacle. So an instruction is *addressed* on the
messaging bus. The terminal remains the delivery path for an agent this
framework started (`owner.py`), and nothing here writes into a foreign one.

## Four outcomes, and the send call is none of them

The send call reports that a message was **accepted for delivery**. That is
compatible with the message never reaching anyone, so it is never reported as
delivery. What the channel says it DID is a separate fact, and it is composed
from two sources rather than read from one:

    the channel says whether the entry claims that seat's attention  (`wakes`)
    this module says whether anything is armed to act on it          (a waiter)

`wakes` alone is not delivery. The bus admits a seat that is *not known to be
gone* — a registered writer pid is alive, or the seat was merely seen recently
— so a named seat may have no live session behind it at all. Composing the two
is what makes the outcomes distinguishable:

    wakes + a live waiter                 → arrives now
    wakes, no waiter, agent working       → at the end of the current turn
    wakes, no waiter, agent not working   → sits unread
    wakes nobody                          → said verbatim, never upgraded

A fifth state exists on the runtime's own cross-session channel and on no other
source: **held** for the recipient's human, which then **expires** on its own.
It is not a resting state, so `DeliveryReport.lapsed()` exists to correct an
outcome already shown rather than leave it standing.

## What this module refuses to do

- **Broadcast in place of an address.** An unresolvable addressee is a refusal,
  never a message to everyone in the room. The bus refuses it at the sender and
  this module carries that refusal through unchanged.
- **Carry content on the direct channel.** `ring_mailbox_check` takes no
  message parameter at all. The prohibition is a signature rather than a rule,
  because a rule is one careless keyword argument away from being broken.
- **Tidy up.** An orphaned waiter is removed only by an action naming that one
  process, never as a side effect, and never when its session is alive or
  cannot be determined to be dead.

## Confidentiality

Instruction text is written by a person about a project that may not be ours,
and answers to open decisions land in a consumer's own tree. Nothing here logs a
message body, an answer body or an excerpt: the logs carry the seat, the
outcome, the room and the counts, which is what an operator needs and nothing a
boundary forbids.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from . import state as agent_state

logger = logging.getLogger(__name__)

__all__ = [
    "ARRIVES_NOW",
    "AT_TURN_END",
    "SITS_UNREAD",
    "WAKES_NOBODY",
    "HELD",
    "EXPIRED",
    "UNKNOWN",
    "REFUSED",
    "NOT_INSTRUCTABLE",
    "TERMINAL_OUTCOMES",
    "Seat",
    "Instructability",
    "DeliveryReport",
    "Waiter",
    "BellResult",
    "AnswerRecorded",
    "read_seats",
    "seat_for",
    "instructability",
    "send_instruction",
    "held",
    "instruct_agent",
    "ring_mailbox_check",
    "live_waiters",
    "waiters_for_session",
    "orphaned_waiters",
    "remove_waiter",
    "record_decision_answer",
    "resolve_answer_writer",
    "ANSWER_WRITER_GROUP",
]


# --------------------------------------------------------------------------- #
# outcomes
# --------------------------------------------------------------------------- #

#: A waiter under that session can start a new turn.
ARRIVES_NOW = "arrives-now"
#: The session is working; its stop-hook will not let the turn close over unread
#: addressed mail.
AT_TURN_END = "at-turn-end"
#: Nothing will start a turn until a person types into that session.
SITS_UNREAD = "sits-unread"
#: The channel said the entry claims nobody's attention. Carried verbatim.
WAKES_NOBODY = "wakes-nobody"
#: The channel did not deliver: someone at the far end must approve it first.
HELD = "held"
#: A hold that ran out. Not delivered, and it replaces an outcome already shown.
EXPIRED = "expired"
#: The channel gave no usable answer. NEVER upgraded to a delivery.
UNKNOWN = "unknown"
#: The send did not happen — an unresolvable addressee, or the bus refused.
REFUSED = "refused"
#: The agent has no bus identity, so there was nothing to send to.
NOT_INSTRUCTABLE = "not-instructable"

#: Outcomes after which nothing further is expected. `HELD` is deliberately
#: absent: it has a clock, and treating it as a resting state is the defect
#: `DeliveryReport.lapsed` exists to prevent.
TERMINAL_OUTCOMES = frozenset(
    {ARRIVES_NOW, AT_TURN_END, SITS_UNREAD, WAKES_NOBODY, EXPIRED, REFUSED, NOT_INSTRUCTABLE}
)

#: Reasons an agent cannot be instructed. Stated where the input would be.
NO_SEAT = "this session has no seat on the messaging bus"
NO_SESSION = "this process has no session id, so no seat can be resolved"
NO_BUS = "the messaging bus is not installed on this machine"
BUS_UNREADABLE = "the messaging bus could not be asked who exists"

#: The bus command. Named once; every entry point takes an override so a test
#: never needs the real one and a caller can point at another install.
SAC = "sac"


# --------------------------------------------------------------------------- #
# who exists on the bus
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Seat:
    """One session's address on the bus.

    `liveness` is the bus's own word — `live`, `gone` or `unknown` — and it is
    carried rather than collapsed into a bool. `unknown` means the seat was seen
    recently and no writer pid could be confirmed, which is weaker than live and
    stronger than gone; flattening it would lose exactly the distinction that
    makes an outcome honest.
    """

    seat: str
    agent: str
    session: Optional[str]
    liveness: str = "unknown"
    rooms: tuple = ()
    project: Optional[str] = None

    @property
    def known_gone(self) -> bool:
        return self.liveness == "gone"


def read_seats(
    *,
    sac_bin: str = SAC,
    env: Optional[Dict[str, str]] = None,
    timeout: float = 15.0,
) -> Optional[Dict[str, Seat]]:
    """Every seat the bus knows, keyed by the SESSION id behind it.

    Keyed by session because that is the join this whole capability rests on:
    the fleet knows an agent by its runtime session id, the bus knows a seat by
    the same id, and the pair is recorded by both sides rather than guessed.
    §1's pairing problem — a heuristic link was right 4 times in 9 — does not
    arise here at all.

    **None means the question could not be answered**, and it is a different
    value from an empty dict. An empty dict says the bus is installed and knows
    nobody; None says nothing was asked. Reporting "no seat" for an unreadable
    bus would mark every agent uninstructable on a machine where they are all
    reachable — the false-absence class, in the direction that hides work.
    """
    if not shutil.which(sac_bin):
        logger.info("fleet instruct: no messaging bus on PATH (%s)", sac_bin)
        return None
    try:
        proc = subprocess.run(
            [sac_bin, "agents", "--json"],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("fleet instruct: cannot ask the bus who exists: %s", exc)
        return None
    if proc.returncode != 0:
        logger.warning(
            "fleet instruct: the bus refused the roster (exit %s): %s",
            proc.returncode, (proc.stderr or "").strip()[:200],
        )
        return None
    try:
        report = json.loads(proc.stdout)
    except (ValueError, TypeError) as exc:
        logger.warning("fleet instruct: the bus roster did not parse: %s", exc)
        return None

    seats: Dict[str, Seat] = {}
    for entry in report.get("agents") or []:
        if not isinstance(entry, dict):
            continue
        agent = str(entry.get("agent") or "")
        project = entry.get("project")
        for raw in entry.get("seats") or []:
            if not isinstance(raw, dict):
                continue
            session = raw.get("session")
            if not session:
                # A seat with no session id belongs to no one session — several
                # processes share its file. It cannot be addressed as *this*
                # agent, so it is not a candidate for the join.
                continue
            seat = Seat(
                seat=str(raw.get("seat") or ""),
                agent=agent,
                session=str(session),
                liveness=str(raw.get("liveness") or "unknown"),
                rooms=tuple(entry.get("rooms") or ()),
                project=str(project) if project else None,
            )
            existing = seats.get(seat.session)
            # One session, one seat by construction — but a store that has both
            # keeps the live one, because addressing a gone seat is not delivery.
            if existing is None or (existing.known_gone and not seat.known_gone):
                seats[seat.session] = seat
    logger.debug("fleet instruct: %d seats with a session id", len(seats))
    return seats


def seat_for(session_id: Optional[str], seats: Optional[Dict[str, Seat]]) -> Optional[Seat]:
    """The seat behind one session, or None. Never a fuzzy match."""
    if not session_id or not seats:
        return None
    return seats.get(str(session_id))


@dataclass(frozen=True)
class Instructability:
    """Whether an agent can be instructed, and — when it cannot — why.

    The reason is not decoration. Task 4.4 puts it *where the input would be*:
    an agent with no bus identity is still discovered, still observable and
    still has a log, and dropping it would hide running work. An input that
    silently goes nowhere would be worse than either.
    """

    instructable: bool
    reason: Optional[str] = None
    seat: Optional[Seat] = None

    def as_dict(self) -> Dict[str, object]:
        return {
            "instructable": self.instructable,
            "reason": self.reason,
            "seat": self.seat.seat if self.seat else None,
        }


def instructability(
    session_id: Optional[str], seats: Optional[Dict[str, Seat]],
) -> Instructability:
    """Can this session be addressed, and if not, what does the surface say.

    The three negatives are kept apart because they are three different facts
    and only one of them is about the agent: no bus at all, a bus that could not
    be asked, and a bus that was asked and does not know this session.
    """
    if seats is None:
        return Instructability(False, BUS_UNREADABLE)
    if not session_id:
        return Instructability(False, NO_SESSION)
    seat = seats.get(str(session_id))
    if seat is None:
        return Instructability(False, NO_SEAT)
    return Instructability(True, None, seat)


# --------------------------------------------------------------------------- #
# waiters
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Waiter:
    """A `sac wait` process — the thing that starts a turn when mail arrives.

    Identified STRUCTURALLY, never by a substring. The first count of these was
    wrong because the counting command's own command line contained the pattern
    it searched for, so the measurement was inside the corpus it measured — and
    it over-reported, which is the direction that invites killing something.
    """

    pid: int
    session: Optional[str]
    cwd: Optional[str] = None
    rooms: tuple = ()

    @property
    def session_known(self) -> bool:
        return bool(self.session)


def _proc_argv(pid: str, proc_root: str) -> List[str]:
    try:
        with open(os.path.join(proc_root, pid, "cmdline"), "rb") as fh:
            raw = fh.read()
    except (OSError, PermissionError):
        return []
    return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]


def _proc_env(pid: str, proc_root: str, key: str) -> Optional[str]:
    try:
        with open(os.path.join(proc_root, pid, "environ"), "rb") as fh:
            raw = fh.read()
    except (OSError, PermissionError):
        return None
    for item in raw.split(b"\0"):
        if item.startswith(key.encode() + b"="):
            return item.split(b"=", 1)[1].decode("utf-8", "replace")
    return None


def _is_waiter_argv(argv: Sequence[str]) -> bool:
    """The structural test: `<node> …/sac.mjs wait […]`.

    Three positions must all hold, and no shell can satisfy them by accident —
    which is the point. A command line that merely CONTAINS the words (a grep
    looking for waiters, this module's own test run, a shell snapshot) matches
    none of them. Task 9.14 asserts exactly that case.
    """
    if len(argv) < 3:
        return False
    if not argv[1].endswith("sac.mjs"):
        return False
    return argv[2] == "wait"


def live_waiters(proc_root: str = "/proc") -> Optional[List[Waiter]]:
    """Every waiter process on this machine, resolved to an identity.

    None when `/proc` cannot be read at all — the caller must not read that as
    "no waiters", because the two lead to opposite actions: no waiters is an
    invitation to install one, an unreadable `/proc` is an invitation to do
    nothing.
    """
    try:
        entries = os.listdir(proc_root)
    except OSError as exc:
        logger.warning("fleet instruct: cannot read %s: %s", proc_root, exc)
        return None

    found: List[Waiter] = []
    for entry in entries:
        if not entry.isdigit():
            continue
        argv = _proc_argv(entry, proc_root)
        if not _is_waiter_argv(argv):
            continue
        rooms = tuple(a for a in argv[3:] if not a.startswith("-"))
        try:
            cwd = os.readlink(os.path.join(proc_root, entry, "cwd"))
        except OSError:
            cwd = None
        found.append(Waiter(
            pid=int(entry),
            session=_proc_env(entry, proc_root, "CLAUDE_CODE_SESSION_ID"),
            cwd=cwd,
            rooms=rooms,
        ))
    logger.debug("fleet instruct: %d waiter processes", len(found))
    return found


def waiters_for_session(
    session_id: Optional[str], waiters: Optional[Iterable[Waiter]],
) -> List[Waiter]:
    """The waiters belonging to one session — a LIST, because one session had four.

    Measured 2026-08-18: a single session owned four waiters at once, which no
    requirement anticipated. So a missing-waiter check counts rather than tests
    presence, and every caller here gets the list.
    """
    if not session_id or not waiters:
        return []
    return [w for w in waiters if w.session == str(session_id)]


def orphaned_waiters(
    waiters: Optional[Iterable[Waiter]],
    live_sessions: Optional[Iterable[str]],
) -> List[Waiter]:
    """Waiters whose session is known to have exited. Every doubt resolves to alive.

    `live_sessions is None` means liveness could not be determined at all, and
    the answer is an EMPTY list rather than every waiter: the fail direction is
    not symmetric. Leaving an orphan costs a process table entry; killing a live
    waiter silently removes the thing that would have delivered someone's next
    instruction, and the agent it belonged to then merely looks quiet.

    A waiter whose own session id cannot be read is treated the same way — an
    undeterminable session is alive.
    """
    if waiters is None or live_sessions is None:
        return []
    alive = {str(s) for s in live_sessions}
    return [w for w in waiters if w.session_known and w.session not in alive]


def remove_waiter(
    pid: int,
    *,
    live_sessions: Optional[Iterable[str]],
    proc_root: str = "/proc",
    kill: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, object]:
    """Stop ONE named waiter, having confirmed that one is what it is.

    Everything about this function is a refusal with a narrow exception. It
    takes a single pid — there is no bulk form, because a cleanup that takes a
    list is one mistaken list away from killing live waiters. It re-resolves the
    pid to a waiter identity at the moment of the removal rather than trusting a
    candidate list that may be seconds old and may name a pid that has since
    been recycled. And it refuses on every uncertainty.

    Returns a dict rather than raising: the caller is a surface, and "refused,
    because its session is alive" is information to show, not an error to
    swallow.
    """
    argv = _proc_argv(str(pid), proc_root)
    if not _is_waiter_argv(argv):
        logger.info("fleet instruct: refusing to remove pid %s — not a waiter", pid)
        return {"removed": False, "pid": pid, "reason": "this pid is not a waiter process"}
    if live_sessions is None:
        return {"removed": False, "pid": pid,
                "reason": "session liveness could not be determined, so it is treated as alive"}
    session = _proc_env(str(pid), proc_root, "CLAUDE_CODE_SESSION_ID")
    if not session:
        return {"removed": False, "pid": pid,
                "reason": "this waiter's session cannot be determined, so it is treated as alive"}
    if session in {str(s) for s in live_sessions}:
        return {"removed": False, "pid": pid, "session": session,
                "reason": "its session is alive"}
    send = kill or os.kill
    try:
        send(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError) as exc:
        logger.warning("fleet instruct: waiter %s could not be stopped: %s", pid, exc)
        return {"removed": False, "pid": pid, "session": session,
                "reason": f"the process could not be signalled: {exc}"}
    logger.info("fleet instruct: waiter pid %s (session %s) stopped with SIGTERM", pid, session)
    return {"removed": True, "pid": pid, "session": session}


# --------------------------------------------------------------------------- #
# delivery
# --------------------------------------------------------------------------- #


@dataclass
class DeliveryReport:
    """What became of one instruction — and what has NOT been observed yet.

    `accepted` and `outcome` are two facts, not one. The send call answering
    successfully means the message was taken for delivery; it is compatible with
    the message never reaching anyone. Anything that renders `accepted` as a
    delivery has measured that the call was made.
    """

    outcome: str
    #: The send call returned without refusing. NOT a delivery.
    accepted: bool = False
    seat: Optional[str] = None
    room: Optional[str] = None
    #: The seats the channel says this entry claims the attention of. `None`
    #: means the channel gave no answer at all — which is why the empty list
    #: cannot stand for it: `[]` is a measurement, `None` is an admission.
    wakes: Optional[List[str]] = None
    #: How many live waiters were found for the target session, at send time.
    waiters: int = 0
    #: The channel's own notices, verbatim. Shown, never parsed for a verdict.
    notices: List[str] = field(default_factory=list)
    reason: Optional[str] = None
    #: Set when a later notice corrected this outcome — see `lapsed`.
    superseded: Optional[str] = None

    @property
    def delivered_to_agent(self) -> bool:
        """Whether the AGENT has it. A held message is never counted here.

        Held means a human at the far end was interrupted and the agent saw
        nothing. Counting it as instructed would report an event that has not
        happened, in the one place that looks like a success.
        """
        return self.outcome in (ARRIVES_NOW, AT_TURN_END)

    @property
    def settled(self) -> bool:
        """Whether anything further is expected. `HELD` is never settled."""
        return self.outcome in TERMINAL_OUTCOMES

    def lapsed(self, reason: Optional[str] = None) -> "DeliveryReport":
        """Carry a hold's expiry through to where the first outcome was shown.

        A hold expires on its own, so the outcome is a claim about a moment. A
        surface that renders the first notice and stops is asserting a state
        that stopped being true with no further event — so the earlier outcome
        is not left standing, it is replaced and named as replaced.
        """
        logger.info("fleet instruct: hold on seat %s lapsed", self.seat)
        return DeliveryReport(
            outcome=EXPIRED,
            accepted=self.accepted,
            seat=self.seat,
            room=self.room,
            wakes=self.wakes,
            waiters=self.waiters,
            notices=list(self.notices),
            reason=reason or "the hold expired without the recipient's human answering",
            superseded=self.outcome,
        )

    def as_dict(self) -> Dict[str, object]:
        return {
            "outcome": self.outcome,
            "accepted": self.accepted,
            "delivered_to_agent": self.delivered_to_agent,
            "settled": self.settled,
            "seat": self.seat,
            "room": self.room,
            "wakes": self.wakes,
            "waiters": self.waiters,
            "notices": self.notices,
            "reason": self.reason,
            "superseded": self.superseded,
        }


def held(
    seat: Optional[str], *, room: Optional[str] = None, reason: Optional[str] = None,
) -> DeliveryReport:
    """A message the channel did NOT deliver: a human at the far end must approve it.

    Constructed rather than inferred, and deliberately not produced by
    `send_instruction`. A hold exists on the runtime's own cross-session
    channel and on no other source — measured twice, both held, both expired
    unanswered — and that channel is exactly the one
    `a-direct-channel-may-ring-the-bell-but-never-carry-the-message` forbids for
    content. So the outcome is modelled and its lapse is carried, while nothing
    here manufactures one from a durable send that cannot produce it.

    Inventing a producer would be worse than leaving the gap visible: a `held`
    read off a field the durable channel never sets would be a false value in
    the one place that looks like caution.
    """
    return DeliveryReport(
        outcome=HELD, accepted=True, seat=seat, room=room,
        reason=reason or "the recipient's human must approve it before the agent sees it",
    )


def _outcome_from(
    woke: bool, waiters: int, state: Optional[str],
) -> str:
    """Compose the channel's answer with what is armed to act on it.

    Neither source alone is an outcome. `wakes` is the channel's RULE decision
    about whose attention the entry claims; the waiter count is whether anything
    will act on it without a person. The agent's state separates the two ways of
    having no waiter, and only one of them is bad news.
    """
    if not woke:
        return WAKES_NOBODY
    if waiters > 0:
        return ARRIVES_NOW
    if state == agent_state.WORKING:
        return AT_TURN_END
    return SITS_UNREAD


def send_instruction(
    seat: Optional[Seat],
    text: str,
    *,
    kind: str = "REQUEST",
    room: Optional[str] = None,
    state: Optional[str] = None,
    waiters: Optional[Iterable[Waiter]] = None,
    sac_bin: str = SAC,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: float = 20.0,
) -> DeliveryReport:
    """Address one instruction to one seat, and report what the channel did.

    `kind` defaults to `REQUEST` deliberately. A `FACT` carrying an errand wakes
    nobody by the channel's own rule and waits for someone to happen to look —
    measured on the live bus, where five of five entries in one day were
    broadcast facts and every sender believed they had told the others. An
    instruction is by definition something someone must act on.
    """
    if seat is None:
        return DeliveryReport(outcome=NOT_INSTRUCTABLE, reason=NO_SEAT)
    if not text or not text.strip():
        return DeliveryReport(outcome=REFUSED, seat=seat.seat,
                              reason="an empty instruction is not sent")
    if not shutil.which(sac_bin):
        return DeliveryReport(outcome=NOT_INSTRUCTABLE, seat=seat.seat, reason=NO_BUS)

    # The room may be omitted when the entry is addressed: the channel resolves
    # it from the seat and reports which one it chose. Reading the room off the
    # ANSWER rather than choosing one here is what keeps this layer domain-free
    # — set-core does not know a project's room conventions and must not guess.
    argv = [sac_bin, "send"]
    if room:
        argv.append(room)
    argv += [kind, text, "--to", seat.seat]

    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env,
        )
    except subprocess.TimeoutExpired:
        logger.warning("fleet instruct: the send to %s timed out", seat.seat)
        return DeliveryReport(outcome=UNKNOWN, seat=seat.seat,
                              reason="the channel did not answer in time")
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("fleet instruct: the send to %s failed: %s", seat.seat, exc)
        return DeliveryReport(outcome=REFUSED, seat=seat.seat, reason=str(exc))

    if proc.returncode != 0:
        # A refusal is carried through unchanged and never retried without the
        # address. An unresolvable addressee is exactly when a broadcast would
        # be most tempting and most wrong: it would deliver a message meant for
        # one session to everyone who can read the room.
        why = (proc.stderr or proc.stdout or "").strip()
        logger.info("fleet instruct: the channel refused the send to %s", seat.seat)
        return DeliveryReport(outcome=REFUSED, seat=seat.seat, reason=why[:500] or
                              "the channel refused the send")

    try:
        answer = json.loads(proc.stdout)
    except (ValueError, TypeError):
        logger.warning("fleet instruct: the send to %s returned no usable answer", seat.seat)
        return DeliveryReport(outcome=UNKNOWN, accepted=True, seat=seat.seat,
                              reason="the channel's answer did not parse")
    if not isinstance(answer, dict) or "wakes" not in answer:
        # The call succeeded and said nothing about what it did. That is an
        # admission, not a delivery, and it must not be upgraded into one.
        return DeliveryReport(outcome=UNKNOWN, accepted=True, seat=seat.seat,
                              room=(answer or {}).get("room") if isinstance(answer, dict) else None,
                              reason="the channel did not say what the entry did")

    woke = [str(s) for s in (answer.get("wakes") or [])]
    notices = [str(n) for n in (answer.get("notice") or [])]
    if answer.get("warning"):
        notices.append(str(answer["warning"]))
    armed = len(waiters_for_session(seat.session, waiters))
    report = DeliveryReport(
        outcome=_outcome_from(seat.seat in woke, armed, state),
        accepted=True,
        seat=seat.seat,
        room=answer.get("room"),
        wakes=woke,
        waiters=armed,
        notices=notices,
    )
    logger.info(
        "fleet instruct: seat=%s room=%s outcome=%s wakes=%d waiters=%d",
        report.seat, report.room, report.outcome, len(woke), armed,
    )
    return report


# --------------------------------------------------------------------------- #
# the bell
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class BellResult:
    """Whether a mailbox-check prompt was delivered. Never part of the outcome.

    The bell is an optimisation on WHEN a message is read, never on WHETHER it
    was sent. So a failed bell is not a failed delivery, and this result is
    reported beside the delivery report rather than folded into it.
    """

    rung: bool
    reason: Optional[str] = None


def ring_mailbox_check(
    seat: Seat,
    *,
    transport: Optional[Callable[[str], bool]] = None,
) -> BellResult:
    """Ask a session to look at its mailbox. **Takes no message.**

    The missing parameter is the design. A direct socket to a running session is
    fire-and-forget: no record on disk, no addressee, no read cursor — so "who
    has not seen this yet" stops being answerable, and a surface whose whole
    rule is that nothing may be hidden cannot deliver through it. The
    instruction always travels the durable path; this only shortens the wait.

    Writing the prohibition as a signature rather than as a comment is
    deliberate. A rule saying *do not put the text here* is one careless keyword
    argument away from being broken, and the break would be invisible: the
    message would arrive, and the durable record simply would not exist.

    `transport` is injected rather than discovered because the direct channel is
    not a documented interface. With none supplied nothing is attempted, and the
    system behaves exactly as it does without a bell — the message is read at the
    next opportunity, only later.
    """
    if transport is None:
        return BellResult(False, "no direct channel is available")
    try:
        rung = bool(transport(seat.seat))
    except Exception as exc:  # noqa: BLE001 — a bell may never break a delivery
        logger.info("fleet instruct: the bell for %s did not ring: %s", seat.seat, exc)
        return BellResult(False, f"the direct channel refused: {exc}")
    logger.debug("fleet instruct: bell for %s rung=%s", seat.seat, rung)
    return BellResult(rung, None if rung else "the direct channel did not accept the prompt")


def instruct_agent(
    session_id: Optional[str],
    text: str,
    *,
    seats: Optional[Dict[str, Seat]] = None,
    waiters: Optional[Iterable[Waiter]] = None,
    state: Optional[str] = None,
    bell: Optional[Callable[[str], bool]] = None,
    **send_kwargs,
) -> Dict[str, object]:
    """The whole act: resolve, send on the durable path, and only then ring.

    The order is the requirement, not an implementation detail. The durable send
    happens first and unconditionally, so a bell that cannot ring degrades to
    exactly the behaviour of having no bell at all — the message is delivered and
    read at the next opportunity, only later. Ringing first would make the bell
    load-bearing, and its failure would then look like a delivery failure.

    The bell is offered for ONE outcome. `sits-unread` is the case where nothing
    will start a turn until a person types; `at-turn-end` already has a stop-hook
    and `arrives-now` already has a waiter, so ringing there would interrupt a
    session for a message it was going to read anyway.
    """
    can = instructability(session_id, seats)
    if not can.instructable:
        return {"delivery": DeliveryReport(outcome=NOT_INSTRUCTABLE, reason=can.reason).as_dict(),
                "bell": BellResult(False, "nothing was sent").__dict__,
                "instructable": False, "reason": can.reason}

    report = send_instruction(
        can.seat, text, waiters=waiters, state=state, **send_kwargs)
    if report.outcome == SITS_UNREAD:
        rung = ring_mailbox_check(can.seat, transport=bell)
    else:
        rung = BellResult(False, "nothing needed prompting")
    return {"delivery": report.as_dict(), "bell": rung.__dict__,
            "instructable": True, "reason": None}


# --------------------------------------------------------------------------- #
# answers to open decisions
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AnswerRecorded:
    """An answer that reached the connector. **Recorded**, never received."""

    change: str
    task: str
    path: str
    #: The word the surface must use. An answer in the connector has not been
    #: read by anything yet; it is read when the next unit starts, which may be
    #: hours away.
    outcome: str = "recorded"

    def as_dict(self) -> Dict[str, object]:
        return {"change": self.change, "task": self.task,
                "path": self.path, "outcome": self.outcome}


#: Where an answer-writer registers itself. A GROUP name, not a package name:
#: `set_orch` must not know which package supplies the connector, and this is
#: the mechanism the profile system already uses for the same reason.
ANSWER_WRITER_GROUP = "set_orch.deferred_work"


def resolve_answer_writer(group: str = ANSWER_WRITER_GROUP) -> Optional[Callable]:
    """The installed deferred-work connector's writer, or **None**.

    None is a first-class answer, not a failure: on a machine with no work-cycle
    engine there is nowhere keyed for an answer to go, so the control is not
    offered rather than offered and broken (design §8.1). For a while that is
    every machine.

    Resolved through an entry point rather than imported, because the dependency
    points one way — `set_workcycle` may import `set_orch`, never the reverse
    (engine design D10). That direction is what makes "orchestration keeps
    working with the engine deleted" a fact a test can check, and one is
    checking: `tests/unit/test_workcycle_dependency_direction.py` caught the
    first version of this function, which imported the connector directly.
    """
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover — Python < 3.8 is not supported here
        return None
    try:
        found = entry_points(group=group)
    except TypeError:  # pragma: no cover — older API shape
        found = entry_points().get(group, [])
    for entry in found:
        try:
            module = entry.load()
        except Exception as exc:  # noqa: BLE001 — a broken plugin is an absence, not a crash
            logger.warning("fleet instruct: the answer writer %r did not load: %s", entry.name, exc)
            continue
        writer = getattr(module, "write_answer", module)
        if callable(writer):
            logger.debug("fleet instruct: answer writer resolved from %r", entry.name)
            return writer
    logger.info("fleet instruct: no deferred-work connector is installed")
    return None


def record_decision_answer(
    tree: str, change: str, task: str, answer: str, *,
    writer: Callable, source: str = "fleet-surface",
) -> AnswerRecorded:
    """Answer an open decision by writing to the connector, not to a session.

    The question outlives the run that asked it — that is the entire reason it
    was written into the task file. So by the time a person answers, the session
    that asked is usually gone, and a message addressed to it is delivered to
    nobody or held until it lapses. A durable question needs a durable answer.

    Nothing about the asking session is consulted, deliberately: an answer must
    be accepted whether or not that session still exists, and a liveness check
    here could only ever refuse something that should succeed.

    `writer` is **required and injected**, with no default and no import behind
    it. The connector belongs to the work-cycle engine, and `set_orch` may not
    import that package in any form — the first version of this function did,
    and the dependency-direction test failed it before a commit was written.
    `resolve_answer_writer()` is how a caller finds one; `None` from it means the
    control is not offered at all.
    """
    path = writer(tree, change, task, answer, source=source)
    logger.info("fleet instruct: answer recorded for %s#%s by %s", change, task, source)
    return AnswerRecorded(change=change, task=task, path=str(path))
