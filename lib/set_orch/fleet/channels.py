"""Channel topology between live agents, derived from the messaging bus store.

The fleet screen shows who is alive; this module derives who is *talking*: the
channel graph the wire view renders. Two inputs are joined:

- the seat roster (`fleet.instruct.read_seats`), keyed by session id — the
  sanctioned fleet ↔ bus join, already carried by the instruct capability;
- the bus's on-disk store: `channels/<room>/<seat>.md` files, whose names name
  the sender and whose mtimes date the newest write.

**The confidentiality line is structural, not a convention.** Only the newest
channel file's first heading is read, and only to extract addressee seat names
from its `→` clause. Message bodies are never read, and nothing derived from
one — a body, an excerpt, a heading's timestamp text — can reach the payload,
because the parser stops at the addressee clause and returns seat names only.

Everything here is read-only. The bus is never written, never enrolled-into,
and no second transport is created beside it: a surface that finds an agent
with no seat says so, and leaves enrolment to the enrolment path.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

logger = logging.getLogger(__name__)

#: How fresh a channel's newest write must be for its wire to animate. One
#: constant, named, in one place — the "activity window" the specs speak of.
ACTIVITY_WINDOW_SECONDS = 30 * 60

#: Sender file names and addressee clauses both carry seats as
#: `<agent>#<hex-short>`. Anchored whole-token so a longer id cannot match a
#: shorter one by prefix — the negation-blind-pattern lesson, applied.
_SEAT_TOKEN = re.compile(r"[A-Za-z0-9_-]+#[0-9a-f]{6,12}")

#: The addressee clause of a channel heading: `→ seat#abc123, seat#def456`.
#: Only text after `→` on the FIRST heading line is inspected; the parser
#: never sees the body beneath it.
_ARROW = "→"

#: Store-root resolution mirrors the bus's own (`store.mjs`): its env var, then
#: XDG data home, then the platform default. Same precedence, so a redirected
#: store is found wherever the bus itself would find it.
_STORE_ENV = "SET_AGENT_COMM_DIR"
_STORE_LEAF = "set-agent-comm"


def resolve_store_root() -> Path:
    """Where the bus store lives, resolved exactly as the bus resolves it."""
    override = os.environ.get(_STORE_ENV)
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / _STORE_LEAF
    return Path.home() / ".local" / "share" / _STORE_LEAF


@dataclass
class LiveAgent:
    """The one slice of a discovered agent the join needs — passed in, not
    discovered here, so this module stays pure and testable."""

    pid: int
    session_id: Optional[str]
    project_root: Optional[str]
    name: Optional[str] = None


@dataclass
class ChannelNode:
    pid: int
    session_id: Optional[str]
    project_root: Optional[str]
    name: Optional[str]
    seat: Optional[str] = None
    agent: Optional[str] = None
    enrolled: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "pid": self.pid,
            "sessionId": self.session_id,
            "projectRoot": self.project_root,
            "name": self.name,
            "seat": self.seat,
            "agent": self.agent,
            "enrolled": self.enrolled,
        }


@dataclass
class ChannelEdge:
    room: str
    members: list = field(default_factory=list)  # session ids, live + enrolled
    member_seats: list = field(default_factory=list)
    sender_seat: Optional[str] = None
    sender_session: Optional[str] = None
    addressees: list = field(default_factory=list)  # session ids; empty = broadcast
    last_activity: Optional[float] = None  # epoch seconds of the newest write
    recent: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "room": self.room,
            "members": self.members,
            "memberSeats": self.member_seats,
            "from": self.sender_session,
            "fromSeat": self.sender_seat,
            # Empty `to` means broadcast — the client animates toward every
            # other member. It must stay EMPTY, not become the member list: a
            # filled list would make an unparseable write look addressed.
            "to": self.addressees,
            "lastActivity": self.last_activity,
            "recent": self.recent,
        }


def _parse_addressees(heading_line: str) -> list:
    """Seat names named after `→` on one heading line. Empty = no parse."""
    if _ARROW not in heading_line:
        return []
    clause = heading_line.split(_ARROW, 1)[1]
    # Stop at a parenthetical (`(re: ...)`) — a back-reference names a seat
    # that is not an addressee of THIS write.
    clause = clause.split("(", 1)[0]
    found = _SEAT_TOKEN.findall(clause)
    # De-duplicate, keep order.
    seen: set = set()
    ordered = []
    for seat in found:
        if seat not in seen:
            seen.add(seat)
            ordered.append(seat)
    return ordered


def _newest_channel_write(room_dir: Path) -> Optional[tuple]:
    """(seat name, mtime) of the newest file in one channel dir, or None."""
    if not room_dir.is_dir():
        return None
    newest: Optional[tuple] = None
    try:
        entries = list(room_dir.iterdir())
    except OSError as exc:
        logger.warning("fleet channels: channel dir unreadable (%s): %s",
                       room_dir.name, exc)
        return None
    for entry in entries:
        if not entry.is_file():
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError as exc:
            logger.warning("fleet channels: cannot stat %s: %s", entry.name, exc)
            continue
        if newest is None or mtime > newest[1]:
            newest = (entry.stem, mtime)
    return newest


def _read_addressee_line(path: Path) -> str:
    """The first `##` heading line of one channel file — the only line of
    message content this module ever reads, and only to extract addressees."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped.startswith("##"):
                    return stripped
    except OSError as exc:
        logger.warning("fleet channels: newest write unreadable (%s): %s",
                       path.stem, exc)
    return ""


def derive_channel_graph(
    seats: Optional[Dict[str, Any]],
    store_root: Optional[Path],
    live_agents: Iterable[LiveAgent],
    now: float,
    activity_window: float = ACTIVITY_WINDOW_SECONDS,
) -> Dict[str, Any]:
    """The channel graph payload: nodes (live agents, enrolled or not) and
    edges (channels between enrolled live agents).

    `seats` is `None` when the bus could not be asked at all — a different
    value from an empty dict, which says the bus answered and knows nobody.
    Both produce nodes for every live agent; only `None` (or an unreadable
    store) sets `sourceAvailable: false`, because that is the case where
    "not enrolled" would be a claim this code cannot stand behind.
    """
    live = list(live_agents)
    seat_by_session: Dict[str, Any] = dict(seats or {})
    seat_to_session: Dict[str, str] = {
        seat.seat: session
        for session, seat in seat_by_session.items()
        if getattr(seat, "seat", None)
    }

    # Seats grouped by project path, for the unique-root fallback only.
    seats_by_project: Dict[str, list] = {}
    for seat in seat_by_session.values():
        project = getattr(seat, "project", None)
        if project:
            seats_by_project.setdefault(project, []).append(seat)

    nodes: list = []
    enrolled_sessions: set = set()
    for agent in live:
        node = ChannelNode(
            pid=agent.pid,
            session_id=agent.session_id,
            project_root=agent.project_root,
            name=agent.name,
        )
        session = agent.session_id
        seat = seat_by_session.get(str(session)) if session else None
        if seat is None and agent.project_root:
            candidates = seats_by_project.get(agent.project_root, [])
            # Exactly one candidate joins; two or more would be a guess, and
            # a guessed wire lands on the wrong conversation.
            if len(candidates) == 1:
                seat = candidates[0]
                logger.debug(
                    "fleet channels: session-less agent pid=%s joined by unique project root",
                    agent.pid)
            elif len(candidates) > 1:
                logger.debug(
                    "fleet channels: pid=%s left unjoined — %d seats share its project root",
                    agent.pid, len(candidates))
        if seat is not None:
            node.enrolled = True
            node.seat = getattr(seat, "seat", None)
            node.agent = getattr(seat, "agent", None)
            if session:
                enrolled_sessions.add(str(session))
        nodes.append(node)

    # Rooms shared by two or more enrolled live agents are channels. A room
    # with one live member has nobody on this screen to wire it to.
    rooms: Dict[str, list] = {}
    for node in nodes:
        if not node.enrolled or not node.session_id:
            continue
        seat = seat_by_session[str(node.session_id)]
        for room in getattr(seat, "rooms", ()) or ():
            rooms.setdefault(room, []).append(node)

    channels_root = Path(store_root) / "channels" if store_root else None
    # The source is available only when BOTH halves could be consulted: the
    # roster was asked and answered (seats is not None), and the store root
    # exists. Either half missing means "unenrolled / no channels" would be a
    # claim this code cannot stand behind.
    source_available = (
        seats is not None
        and store_root is not None
        and Path(store_root).is_dir()
    )
    if not source_available:
        # Spec'd degradation: an empty EDGE list with the marker. Nodes still
        # travel — the fleet's live agents are real regardless — but no edge
        # may be claimed from a store that was never read.
        return {
            "sourceAvailable": False,
            "nodes": [n.as_dict() for n in nodes],
            "edges": [],
            "activityWindowSeconds": activity_window,
        }

    edges: list = []
    for room, members in rooms.items():
        if len(members) < 2:
            continue
        edge = ChannelEdge(
            room=room,
            members=[m.session_id for m in members if m.session_id],
            member_seats=[m.seat for m in members if m.seat],
        )
        if channels_root is not None:
            newest = _newest_channel_write(channels_root / room)
            if newest is not None:
                sender_seat, mtime = newest
                edge.sender_seat = sender_seat
                edge.sender_session = seat_to_session.get(sender_seat)
                edge.last_activity = mtime
                edge.recent = (now - mtime) <= activity_window
                sender_path = channels_root / room / f"{sender_seat}.md"
                addressed = _parse_addressees(_read_addressee_line(sender_path))
                edge.addressees = [
                    seat_to_session[s] for s in addressed
                    if s in seat_to_session and s != sender_seat
                ]
                # An addressed seat that resolves to nobody (gone, or not a
                # seat this store knows) degrades to broadcast — an edge that
                # animates nowhere is worse than one that animates everywhere.
                if addressed and not edge.addressees:
                    logger.debug(
                        "fleet channels: room %s addressees unresolved; degrading to broadcast",
                        room)
                    edge.addressees = []
        edges.append(edge)

    logger.debug(
        "fleet channels: %d live agents -> %d nodes (%d enrolled), %d channels",
        len(live), len(nodes), len(enrolled_sessions), len(edges))
    return {
        "sourceAvailable": source_available,
        "nodes": [n.as_dict() for n in nodes],
        "edges": [e.as_dict() for e in edges],
        "activityWindowSeconds": activity_window,
    }
