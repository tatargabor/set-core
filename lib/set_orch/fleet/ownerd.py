"""The agent owner as a service — the socket the dashboard talks to (task 5.8).

`owner.py` holds the ptys and the scopes. This module is the *only* thing that
lets another process reach it: an `AF_UNIX` stream speaking the JSON-lines
protocol in `protocol.py`, one passthrough per `AgentOwner` method.

**Why a separate service at all** is in `owner.py`'s header and in
`templates/systemd/set-agent-owner.service`: the dashboard restarts on every
crash and every deploy, and an agent started from it joined its control group
and died with it (finding CB-1).

**Why this file must stay boring.** This service's uptime IS every held agent's
uptime — a pty master cannot be reacquired, so when this process exits, every
pty-attached agent it holds reaches EOF on its own tty and exits. A line of
business logic added here is a future outage of every running agent. Everything
below is therefore dispatch, and the one piece of real behaviour is the drain,
which is not a feature but a precondition:

**The drain, and the measurement that makes it mandatory.** A pty's buffer is
small and a writer blocks when it fills. Measured 2026-08-18 on this machine: a
child writing to its own tty with nobody reading the master stopped after
**17 408 bytes** of the 4 MB it was asked to write, and a **single** drain of the
master let it advance exactly **4 096 bytes** further before stopping again. So
an agent started under a framework-owned pty that nobody reads does not fail —
it *freezes*, after roughly one screenful, looking from the outside like an agent
that is thinking. Holding a master without draining it is not neutral.

**Nothing is persisted.** Drained bytes go into a bounded in-memory tail and
nowhere else — not to disk, not to a log. Diagnostics name the stream and the
failure kind, never the content.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import errno
import json
import logging
import os
import signal
import socket
import sys
import time
from typing import Any, Dict, List, Optional, Sequence

from . import provider_record, scopes
from ..providers import resolver as providers
from ..providers.errors import (
    ConfigError, IncompleteCredential, MissingCredential, ProviderError,
    UnknownModel, UnknownProvider,
)
from .owner import (
    FOREIGN, STARTED_HERE, AgentOwner, CommandNotResolvable, EnvironmentNotDelivered,
    OwnedAgent, OwnerError, recover,
)
from .protocol import (
    SUPPORTED_METHODS, Request, Response, make_error, make_frame, make_result,
)

logger = logging.getLogger(__name__)

#: How much of each agent's terminal output is kept in memory. Bounded because
#: it is a tail, not a transcript: the conversation already has a durable home in
#: the session log, and this service is the wrong place to grow a second one.
DEFAULT_TAIL_BYTES = 64 * 1024

#: The default command for a bare interactive session. Matches `owner.recover()`,
#: which resumes with the same argv — the two must not drift, because a resumed
#: agent and a fresh one appearing on the same screen with different permissions
#: would be a difference nothing on the surface explains.
DEFAULT_AGENT_ARGV = ("claude", "--dangerously-skip-permissions")

#: What this owner understands, sent in `health`. Add a name here when a start
#: gains a parameter an older owner would silently drop.
#:
#: `unit-origin` covers `requested_by`, which a run's record turns into
#: `started_by`. Measured 2026-08-29 at a peer's request: the parameter landed on
#: 08-19 (`7f582c87`) and the owner running today understands it, so this is not
#: a live defect — it is the same trap one layer along, and the reason to name it
#: now is that its silent loss writes a FALSE record rather than an empty one.
#: The design distinguishes "no origin was declared" from "the origin is
#: unknown"; a dropped parameter produces the first while the second is true.
FEATURES = frozenset({"provider-selection", "unit-origin"})

#: Resolution refusals, as KINDS rather than as prose. A caller that has to grep
#: the sentence to tell "you named a provider that does not exist" from "this
#: machine's configuration is broken" breaks the moment the sentence improves —
#: and those two need different answers from different people.
_PROVIDER_ERROR_KINDS = {
    UnknownProvider: "unknown-provider",
    UnknownModel: "unknown-model",
    MissingCredential: "provider-config",
    IncompleteCredential: "provider-config",
    ConfigError: "provider-config",
}


#: How far past a cut `_resync` will look for a boundary before giving up.
#:
#: Measured 2026-08-26 across 12 live terminals: the first `ESC` after an
#: arbitrary cut was 0-66 bytes away, mean 14.5. 1 KiB is therefore two orders of
#: magnitude of headroom, and it bounds the one case that would otherwise be
#: unbounded — a long run of plain text with no escape in it at all.
_RESYNC_WINDOW = 1024


def _resync(buf: bytes, drop: int) -> int:
    """Where to cut `buf` so that what REMAINS starts at a sequence boundary.

    ## The defect this exists for — B-82

    The tail is a ring buffer of raw pty bytes and the cut was `len - cap`:
    wherever 64 KiB happened to land. A terminal stream is mostly escape
    sequences — measured on live agents, one `ESC` every 8-18 bytes — so the cut
    lands INSIDE a sequence most of the time, and what is replayed then begins
    with its tail: `ESC[55;1H` arrives as `55;1H`.

    xterm has no way to know those five characters were ever a command. It draws
    them, at the top-left, as text. Reported 2026-08-26 from a live screen, with
    that exact string in the corner of a tile that was otherwise near-empty.

    **This is not the same failure as a truncated replay, and the difference is
    the point.** A replay missing its head is INCOMPLETE, which the ack already
    says (`replay_truncated`). A replay whose head is a decapitated sequence is
    WRONG: the cursor never moved, so everything after it lands in the wrong
    place, and the tile reads as broken rather than as partial. That is also why
    resizing repairs it and nothing else does — a resize makes the program
    repaint from scratch, which is the reader's own workaround
    (*"átméretezés megjavítja mindig"*).

    ## Why forward-to-the-next-ESC, and not a parser

    An exact repair would parse the dropped region and work out whether the cut
    fell inside a sequence. That is ~40 lines of escape-sequence grammar — CSI,
    OSC, DCS, string terminators, charset designators — and every one of its
    mistakes would fail in the silent direction, producing a stream that still
    looks like a terminal.

    `ESC` always begins a new unit. So skipping forward to the next one cannot
    leave a decapitated sequence, needs no grammar, and is checkable in one line.
    Its cost is dropping a few more bytes of an ALREADY truncated replay, and
    that cost was measured before the design was chosen: at most 66 bytes across
    12 live terminals, of 65 536. Under 0.1 %.

    Two bounds keep it honest:

    - **the search is bounded** (`_RESYNC_WINDOW`), so a stream with no escapes
      in it cannot make this drop the whole buffer. Failing towards "keep some
      plain text that renders fine" is right; failing towards "empty the replay"
      is not.
    - **when no `ESC` is found, the UTF-8 alignment is still repaired.** A cut
      inside a multi-byte character leaves continuation bytes at the head, which
      render as replacement characters — a smaller version of the same defect,
      and the box-drawing an agent's TUI is made of is exactly where it shows.

    Returns an index >= `drop`; cutting there is safe.
    """
    if drop <= 0:
        return 0
    limit = min(len(buf), drop + _RESYNC_WINDOW)
    esc = buf.find(0x1B, drop, limit)
    if esc >= 0:
        return esc
    # No sequence within reach: at least do not start inside a character.
    # UTF-8 continuation bytes are 0b10xxxxxx; a boundary is anything else.
    i = drop
    while i < len(buf) and (buf[i] & 0xC0) == 0x80:
        i += 1
    return i


SOCKET_NAME = "set-agent-owner.sock"


def _sun_path_max() -> int:
    """The kernel's `sun_path` capacity on this platform.

    `sun_path` is a fixed-size char array in `sockaddr_un` and the size differs
    by platform. Exceeded, `bind()` fails with an errno that reads as a missing
    directory — which sends the reader to check a directory that is present.

    Resolved at call time, not frozen at import, for the same reason
    `start_command()` is: it is a fact about the running machine, and a constant
    computed once at import is a fact a test cannot vary without reaching inside
    the module.
    """
    return 104 if sys.platform == "darwin" else 108


def _runtime_dir() -> str:
    """The directory the owner's control socket lives in, per platform.

    Linux keeps `$XDG_RUNTIME_DIR`, falling back to `/run/user/<uid>` — the
    expansion the systemd unit's `%t` already produces, so the service and this
    resolver cannot disagree about where the socket is.

    macOS has neither, so the framework's own per-user data directory is used.
    Not `$TMPDIR`: it would fit the length limit, but it is per-session and
    periodically cleaned, and a control socket that disappears on a schedule is a
    fleet that stops answering for no visible reason.
    """
    if sys.platform == "darwin":
        from ..paths import SET_TOOLS_DATA_DIR
        return os.path.join(SET_TOOLS_DATA_DIR, "runtime")
    return os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"


def default_socket_path(*, create: bool = False) -> str:
    """Where the owner listens, resolved the same way for the service and every client.

    `create=True` is for the side that binds; a client asking where to connect
    must not bring the directory into being as a side effect of looking.
    """
    directory = _runtime_dir()
    if create:
        os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, SOCKET_NAME)
    encoded = len(path.encode("utf-8"))
    limit = _sun_path_max()
    if encoded >= limit:
        raise OwnerError(
            f"the owner's socket path is too long for this platform: {path} "
            f"is {encoded} bytes and the limit is {limit}. "
            "This is not a missing directory — the path itself cannot be bound."
        )
    return path


def _agent_payload(agent: OwnedAgent, *, tail_len: int = 0, dropped: bool = False) -> Dict[str, Any]:
    """What one owned agent looks like on the wire.

    The pty master's file descriptor is deliberately absent: it is a number that
    means something only inside this process, and a descriptor on the wire is an
    invitation to treat it as a handle somewhere it is not one.
    """
    return {
        "label": agent.label,
        "unit": agent.unit,
        "pid": agent.pid,
        "cwd": agent.cwd,
        "population": agent.population,
        "resumed_session": agent.resumed_session,
        "requested_by": agent.requested_by,
        "tail_bytes": tail_len,
        # A tail that has already lost its head says so. Silence here would let a
        # partial stream read as the whole one.
        "tail_truncated": dropped,
    }


class OwnerDaemon:
    """One socket, one `AgentOwner`, one event loop."""

    def __init__(
        self,
        socket_path: str,
        *,
        owner: Optional[AgentOwner] = None,
        tail_bytes: int = DEFAULT_TAIL_BYTES,
    ) -> None:
        self.socket_path = socket_path
        self.owner = owner or AgentOwner()
        self.tail_bytes = tail_bytes
        self.started_at = time.time()
        self._tails: Dict[str, bytearray] = {}
        self._dropped: Dict[str, bool] = {}
        self._drained: Dict[str, int] = {}
        self._server: Optional[asyncio.AbstractServer] = None
        self._stopping = asyncio.Event()
        #: label -> the connections currently watching that terminal. A terminal
        #: may have several viewers; none of them owns it.
        self._subscribers: Dict[str, List[asyncio.StreamWriter]] = {}
        #: the per-connection handler tasks. asyncio makes one per accepted
        #: connection and keeps no public handle on them, so shutdown cannot
        #: reach them without this set — see `shutdown()` for why that matters.
        self._clients: "set[asyncio.Task]" = set()

    # -- the drain -------------------------------------------------------- #

    def _attach_drain(self, agent: OwnedAgent) -> None:
        """Read the pty master continuously, so the agent is never blocked on it."""
        loop = asyncio.get_running_loop()
        self._tails.setdefault(agent.label, bytearray())
        self._dropped.setdefault(agent.label, False)
        self._drained.setdefault(agent.label, 0)
        try:
            # The fd, and deliberately NOT the label: the callback outlives every
            # name the agent will ever have (see `_drain`).
            loop.add_reader(agent.master_fd, self._drain, agent.master_fd)
        except (OSError, ValueError) as exc:
            # An agent nobody drains freezes after about a screenful (see the
            # module header), so this is not a degraded mode — say so loudly.
            logger.error(
                "fleet owner: cannot watch the terminal of %s (%s); it will block once "
                "its pty buffer fills", agent.label, exc,
            )

    def _drain(self, fd: int) -> None:
        """One readable pty master, drained under the name it has NOW.

        **Keyed by fd, and that is the bug this carries a name for.** It used to
        take the label the agent had when the reader was installed, and a rename
        re-keys the owner's map — so the very next read asked for a name nobody
        held, got an `OwnerError`, and the `except` below turned that into an
        empty read, which this method reads as EOF. Measured 2026-08-23 on a live
        agent, six seconds after the rename:

            16:12:28  fleet owner: renamed consumer-app-… to … (pid …, unchanged)
            16:12:34  fleet owner: terminal of consumer-app-… reached EOF after 0 bytes

        Both halves fail in the reassuring direction. The reader is REMOVED, so
        the terminal goes silent for every viewer — a keystroke still reaches the
        pty, it just never echoes, which reads as *I cannot type into it* rather
        than as a broken terminal. And an undrained pty fills after about a
        screenful, at which point the agent itself blocks (see the module
        header): a rename, whose whole promise is that the process is untouched,
        eventually stops it.

        `label_for_fd` asks the owner, so no name is carried across a rename here
        or anywhere downstream — `_rekey` has already moved the stores.
        """
        label = self.owner.label_for_fd(fd)
        if label is None:
            # Not EOF either: nothing is held on this fd, so there is nothing to
            # read and nowhere to put it. Said with the fd, because there is no
            # name left to say it with.
            self._detach_drain(fd)
            logger.warning(
                "fleet owner: nothing is owned on fd %s any more; stopped draining it", fd,
            )
            return
        try:
            data = self.owner.read(label)
        except OwnerError as exc:
            # A refusal is NOT an end-of-file, and reporting it as one is what
            # made a rename look like a terminal that had finished.
            self._detach_drain(fd)
            logger.warning("fleet owner: stopped draining %s: %s", label, exc)
            return
        if not data:
            self._detach_drain(fd)
            logger.info("fleet owner: terminal of %s reached EOF after %d bytes",
                        label, self._drained.get(label, 0))
            return
        self._append(label, data)

    def _append(self, label: str, data: bytes) -> None:
        """Record one chunk: count it, keep the bounded tail, publish it.

        ⚠ **THE ONLY PLACE THAT DOES THIS, and it was not always.** The real
        drain and the test seam below used to hold two copies, and they had
        already diverged: the seam extended the tail and never applied
        `tail_bytes` at all. So every test written through it measured a buffer
        that is unbounded — a different system from the one that ships, and one
        in which B-82 cannot occur, because nothing is ever cut.

        Found 2026-08-26 by writing a test for B-82 through the seam and having
        it fail for the wrong reason. That is the cheap way to find this; the
        expensive way is a green suite that proves nothing about the code the
        reader is looking at.
        """
        self._drained[label] = self._drained.get(label, 0) + len(data)
        tail = self._tails.setdefault(label, bytearray())
        tail.extend(data)
        if len(tail) > self.tail_bytes:
            # WHERE the cut lands is a decision, not an offset — see `_resync`.
            del tail[:_resync(tail, len(tail) - self.tail_bytes)]
            self._dropped[label] = True
        self._publish(label, data)

    def _drain_from(self, data: bytes, label: str = "term") -> None:
        """Feed one chunk as though the pty had produced it. Test seam only.

        Named so it cannot be mistaken for a production path: the real drain is
        driven by `loop.add_reader` on a pty master, and a test that reached for
        that would need a pty, a child and a race.

        It differs from `_drain` in exactly one way — where the bytes came from.
        Everything after that is `_append`, shared, so a test through this seam
        measures the shipping behaviour rather than a relaxed copy of it.
        """
        self._append(label, data)

    def _detach_drain(self, fd: int) -> None:
        try:
            asyncio.get_running_loop().remove_reader(fd)
        except (OSError, ValueError, RuntimeError) as exc:
            logger.debug("fleet owner: removing reader for fd %s: %s", fd, exc)

    # -- the stream (task 5.3 / 6.4) ------------------------------------- #

    #: How much unwritten output a viewer may accumulate before it is dropped.
    #: A viewer that cannot keep up must not be able to stall the drain, because
    #: the drain is what keeps the AGENT running (see the module header).
    SLOW_VIEWER_BYTES = 4 * 1024 * 1024

    #: The most RAW output one frame may carry. Not a tuning knob — a protocol
    #: limit, measured on 2026-08-19 against a live terminal.
    #:
    #: A frame is one JSON line, and the payload is base64, so N raw bytes
    #: become 4N/3 on the wire. asyncio's StreamReader refuses a line longer
    #: than 64 KiB by default and raises `LimitOverrunError`, which is NOT the
    #: connection closing: the reading task dies with an exception nobody
    #: retrieves, and the viewer is told the owner hung up on it.
    #:
    #: Both of this file's own sizes crossed that line. `owner.read()` takes up
    #: to 65536 bytes at once, and `tail_bytes` is 65536 — so a replay of a
    #: screen that already held ~48 KiB was not merely at risk, it was
    #: GUARANTEED to kill the connection. That is why the first attach to a
    #: fresh agent worked (0 bytes replayed) and the reattach after a minute of
    #: output never could.
    #:
    #: 32 KiB raw → ~43.7 KB of base64 plus a short envelope: under the limit
    #: with room for the JSON around it, and still one syscall's worth.
    MAX_FRAME_BYTES = 32 * 1024

    def _frames(self, label: str, data: bytes, replay: bool = False) -> List[bytes]:
        """Encode one chunk as one or more wire frames, none over the limit.

        Split rather than truncated: a terminal replay with a hole in the middle
        renders as garbage — escape sequences do not survive being cut — and a
        hole that is not announced is worse than a slow screen.
        """
        out: List[bytes] = []
        for start in range(0, max(len(data), 1), self.MAX_FRAME_BYTES):
            piece = data[start : start + self.MAX_FRAME_BYTES]
            if not piece:
                break
            out.append(
                (make_frame(label, base64.b64encode(piece).decode("ascii"), replay=replay) + "\n").encode("utf-8")
            )
        return out

    def _publish(self, label: str, data: bytes) -> None:
        """Push one chunk to every viewer of this terminal.

        Written without awaiting, because this runs inside the drain callback and
        the drain must never block: an owner that waits on a slow browser is an
        owner that is not reading the pty, and an agent whose pty is not read
        freezes after about a screenful.

        So backpressure is handled by DROPPING the viewer rather than by slowing
        the source. A dropped viewer sees its stream end and can reattach — a
        frozen agent looks like one that is thinking.
        """
        watchers = self._subscribers.get(label)
        if not watchers:
            return
        frames = self._frames(label, data)
        for writer in list(watchers):
            try:
                pending = writer.transport.get_write_buffer_size()  # type: ignore[union-attr]
            except (AttributeError, TypeError):
                pending = 0
            if writer.is_closing() or pending > self.SLOW_VIEWER_BYTES:
                logger.warning(
                    "fleet owner: dropping a viewer of %s (%s)",
                    label, "closing" if writer.is_closing() else f"{pending} bytes behind",
                )
                self._unsubscribe(label, writer)
                continue
            try:
                for frame in frames:
                    writer.write(frame)
            except (ConnectionResetError, BrokenPipeError, RuntimeError) as exc:
                logger.debug("fleet owner: viewer of %s went away: %s", label, exc)
                self._unsubscribe(label, writer)

    def _subscribe(self, label: str, writer: asyncio.StreamWriter) -> None:
        self._subscribers.setdefault(label, []).append(writer)
        logger.info(
            "fleet owner: a viewer attached to %s (%d watching)",
            label, len(self._subscribers[label]),
        )

    def _unsubscribe(self, label: str, writer: asyncio.StreamWriter) -> None:
        watchers = self._subscribers.get(label)
        if not watchers or writer not in watchers:
            return
        watchers.remove(writer)
        if not watchers:
            self._subscribers.pop(label, None)
        logger.info("fleet owner: a viewer detached from %s (%d left)", label, len(watchers))

    #: Every per-label store this daemon keeps. Named ONCE, so that a rename and
    #: a forget cannot disagree about what "everything about this label" is —
    #: and so that a store added later is a one-line change here rather than a
    #: silent omission in two places. `_rekey` and the rename test both read it.
    LABEL_KEYED = ("_tails", "_dropped", "_drained", "_subscribers")

    def _rekey(self, label: str, new_label: str) -> None:
        """Carry every per-label store from one name to the other.

        The viewers move rather than being dropped: a rename must be invisible to
        the process, and a browser whose terminal went silent because the name
        changed underneath it would be exactly the opposite of invisible.
        """
        for name in self.LABEL_KEYED:
            store = getattr(self, name)
            if label in store:
                store[new_label] = store.pop(label)

    def _forget(self, label: str) -> None:
        self._tails.pop(label, None)
        self._dropped.pop(label, None)
        self._drained.pop(label, None)
        # The viewers are told by their stream ending, not by a message: a
        # terminal that stopped and a connection that dropped look the same from
        # the browser, and both mean "reattach or give up".
        for writer in self._subscribers.pop(label, []):
            if not writer.is_closing():
                writer.close()

    # -- dispatch --------------------------------------------------------- #

    #: Methods whose meaning depends on WHICH connection asked. Everything else
    #: is a fact about the owner and answers the same on any connection.
    CONNECTION_SCOPED = frozenset({"attach", "detach"})

    async def dispatch(
        self, request: Request, writer: Optional[asyncio.StreamWriter] = None
    ) -> Response:
        if request.method not in SUPPORTED_METHODS:
            return make_error(
                request.id,
                f"unknown method {request.method!r}; this owner answers "
                + ", ".join(sorted(SUPPORTED_METHODS)),
            )
        if request.method in self.CONNECTION_SCOPED and writer is None:
            return make_error(
                request.id,
                f"{request.method} is meaningless without a connection to attach; "
                "it cannot be issued out of band",
            )
        handler = getattr(self, f"_do_{request.method}")
        try:
            if request.method in self.CONNECTION_SCOPED:
                result = await handler(request.params, writer)
            else:
                result = await handler(request.params)
        except OwnerError as exc:
            # An expected refusal — a label already owned, a scope that will not
            # die, a terminal this owner does not hold. Not a daemon fault.
            #
            # One kind travels as a kind rather than as prose: a command the child
            # could not execute needs a DIFFERENT act from the caller (install it,
            # fix the service's PATH) than every other refusal here, and a caller
            # that has to grep the sentence to tell them apart breaks the moment
            # the sentence is improved.
            kind = ("command-not-resolvable"
                    if isinstance(exc, CommandNotResolvable) else None)
            if kind is None and isinstance(exc, EnvironmentNotDelivered):
                kind = "environment-not-delivered"
            logger.info("fleet owner: refused %s: %s", request.method, exc)
            return make_error(request.id, str(exc), kind)
        except ProviderError as exc:
            # A configuration fault, reported AS ONE. Without this branch a
            # resolution refusal fell through to the generic handler below, lost
            # its class, and reached the surface as an unclassified refusal —
            # which the API answers with a 409, the status for "somebody else
            # holds it". Measured as B-105 one layer along: a true sentence about
            # a symptom that sends the reader to systemd instead of to a file.
            #
            # The split is by WHOSE act fixes it, which is also which status the
            # API can answer with: a name the catalogue does not declare is this
            # request's mistake and the next request may succeed; an unreadable
            # or incomplete configuration is an operator's file and every request
            # will fail the same way until it is fixed.
            kind = _PROVIDER_ERROR_KINDS.get(type(exc), "provider-config")
            logger.info("fleet owner: %s refused by configuration: %s",
                        request.method, exc)
            return make_error(request.id, str(exc), kind)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("fleet owner: bad %s request: %s", request.method, exc)
            return make_error(request.id, f"bad request: {exc}")
        except Exception as exc:  # pragma: no cover - the unexpected, logged not swallowed
            logger.exception("fleet owner: %s failed", request.method)
            return make_error(request.id, f"{type(exc).__name__}: {exc}")
        return make_result(request.id, result)

    async def _do_health(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ok": True,
            "pid": os.getpid(),
            "uptime_seconds": round(time.time() - self.started_at, 1),
            "socket": self.socket_path,
            # The number that matters operationally: restarting this service
            # ends this many agents.
            "held": len(self.owner.owned()),
            # What this owner can be ASKED for, declared rather than inferred
            # from a version string. A caller cannot tell an owner that ignores
            # a parameter from one that honours it — measured as B-110, where a
            # daemon nineteen hours older than its caller dropped `provider`
            # without a word and started the agent on the machine default. The
            # answer to an unknown parameter has to come from the owner, and the
            # only owner that can answer is one new enough to know the question:
            # so absence IS the answer, and the client treats it as a refusal.
            "features": sorted(FEATURES),
        }

    async def _do_list(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Every held agent, each carrying the provider it was RECORDED on.

        ⚠ An agent with no record gets `provider: null` and
        `provider_recorded: false` — never the machine default. The two facts are
        different and only one of them is known: an agent started before this
        record existed, or started by something that did not name a provider, is
        UNRECORDED. Filling it in from the configuration would make the screen
        state confidently who is paying for a run nobody wrote down.
        """
        rows = []
        for a in self.owner.owned():
            payload = _agent_payload(
                a,
                tail_len=len(self._tails.get(a.label, b"")),
                dropped=self._dropped.get(a.label, False),
            )
            recorded = provider_record.get(a.unit)
            payload["provider_recorded"] = recorded is not None
            payload["provider"] = (recorded or {}).get("provider")
            payload["model"] = (recorded or {}).get("model")
            payload["provenance"] = (recorded or {}).get("provenance") or {}
            rows.append(payload)
        return rows

    async def _do_orphans(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        orphans = await asyncio.to_thread(self.owner.orphans)
        return [
            {"unit": s.unit, "label": s.label, "pid": s.pid, "cgroup": s.cgroup}
            for s in orphans
        ]

    async def _do_start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start an agent, resolving its provider HERE rather than at the caller.

        The resolution runs on this side of the socket on purpose. The caller
        names a provider and a model; the credential is read from a file only
        this service's user can read, and never travels the wire, never reaches
        the browser, and cannot appear in a request log kept by anything in
        between. The alternative — resolving at the API layer and sending an
        environment mapping — would put a live key into every layer it crosses,
        and each of those layers has its own logging.
        """
        label = params["label"]
        cwd = params["cwd"]
        argv = list(params.get("argv") or DEFAULT_AGENT_ARGV)
        env = params.get("env")
        unset: Sequence[str] = ()
        plan = None

        if params.get("provider") or params.get("model") or params.get("project"):
            # Resolve on a thread: `load()` reads a file and stats it.
            plan = await asyncio.to_thread(
                providers.resolve,
                project=params.get("project"),
                provider=params.get("provider"),
                model=params.get("model"),
            )
            # The resolver's values outrank a caller-supplied mapping rather than
            # merging with it. A merge would let the two disagree about the same
            # key with nothing saying which won — and the losing half is a
            # credential or an endpoint, so "nothing saying which won" means an
            # agent billed to an account no record names.
            env = {**(env or {}), **plan.env}
            unset = plan.unset
            argv = argv + list(plan.args)
            logger.info("fleet owner: %s -> %s", label, plan.describe())

        # Blocking: `start` waits for systemd to report the scope active. Off the
        # loop, or every other agent's drain stalls behind it.
        agent = await asyncio.to_thread(
            self.owner.start,
            argv,
            label=label,
            cwd=cwd,
            env=env,
            unset=unset,
            rows=int(params.get("rows", 40)),
            cols=int(params.get("cols", 120)),
            requested_by=params.get("requested_by"),
        )
        self._attach_drain(agent)
        payload = _agent_payload(agent)
        if plan is not None:
            # THE single point. Recorded after the start succeeded and before the
            # answer is returned: recording earlier would leave an entry for an
            # agent that never ran, and recording at each caller is how one
            # caller ends up not recording at all.
            try:
                provider_record.record(
                    agent.unit, provider=plan.provider, model=plan.model,
                    provenance=plan.provenance,
                )
            except OSError as exc:
                # The agent IS running. Failing the start here would report a
                # failure that did not happen and leave a live agent nobody
                # holds — a worse outcome than an unrecorded one, which the
                # readers already have to handle.
                logger.warning("fleet providers: could not record %s: %s", agent.unit, exc)
            # The provenance travels with the answer, never the environment: the
            # caller needs to SHOW which level decided, and showing that must not
            # require holding what it decided.
            payload["provider"] = plan.provider
            payload["model"] = plan.model
            payload["provenance"] = dict(plan.provenance)
        return payload

    async def _do_stop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        label = params["label"]
        agent = next((a for a in self.owner.owned() if a.label == label), None)
        if agent is not None:
            self._detach_drain(agent.master_fd)
        unit = agent.unit if agent is not None else scopes.unit_name(label)
        result = await asyncio.to_thread(self.owner.stop, label)
        self._forget(label)
        # Only for an agent that was actually stopped. A `stop` that found
        # nothing must not delete a record — the unit may belong to a live agent
        # this owner does not hold, and losing its provenance would turn a
        # recorded agent into an unrecorded one for no reason.
        if result.get("found"):
            await asyncio.to_thread(provider_record.forget, unit)
        return result

    async def _do_rename(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Rename a held agent. Nothing is stopped, started or resumed.

        Not run on a thread: this touches dictionaries only, and the owner's map
        must not be mutated from a thread while the loop reads it.
        """
        label = params["label"]
        new_label = params["new_label"]
        agent = self.owner.rename(label, new_label)
        if agent.label != label:
            self._rekey(label, agent.label)
        return _agent_payload(
            agent,
            tail_len=len(self._tails.get(agent.label, b"")),
            dropped=self._dropped.get(agent.label, False),
        )

    async def _do_recover(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Resume an orphan on the provider it was STARTED on, not on the default.

        The record is read here rather than passed in by the caller: the caller
        is a screen, and a screen that supplies the provider can supply a
        different one by accident. What the session was started on is a recorded
        fact, and a resume is not the moment to revise it.
        """
        unit = params["unit"]
        env = None
        unset: Sequence[str] = ()
        resume_argv = params.get("resume_argv")
        plan = None
        # Which record this resume continues. Defaults to the unit being
        # started; a restore that had to rename supplies the ORIGINAL unit,
        # because the record is keyed on what the agent was started under and a
        # renamed resume would otherwise look unrecorded and silently fall back
        # to the ambient default — the exact defect 6.7 fixed, reappearing
        # through the one path that legitimately changes the name.
        record_unit = params.get("provider_unit") or unit
        recorded = await asyncio.to_thread(provider_record.get, record_unit)
        if recorded and recorded.get("provider"):
            plan = await asyncio.to_thread(
                providers.resolve,
                provider=recorded["provider"], model=recorded.get("model"),
            )
            env, unset = plan.env, plan.unset
            if plan.args:
                base = list(resume_argv or [
                    "claude", "--dangerously-skip-permissions",
                    "--resume", params["session_id"]])
                resume_argv = base + list(plan.args)
            logger.info("fleet owner: recovering %s (record %s) -> %s",
                        unit, record_unit, plan.describe())

        agent = await asyncio.to_thread(
            recover,
            self.owner,
            unit=unit,
            session_id=params["session_id"],
            cwd=params["cwd"],
            label=params.get("label"),
            resume_argv=resume_argv,
            env=env,
            unset=unset,
        )
        self._attach_drain(agent)
        payload = _agent_payload(agent)
        if plan is not None:
            payload["provider"] = plan.provider
            payload["model"] = plan.model
            payload["provenance"] = dict(plan.provenance)
        return payload

    async def _do_write(self, params: Dict[str, Any]) -> Dict[str, Any]:
        import base64
        data = base64.b64decode(params["data_b64"])
        written = self.owner.write(params["label"], data)
        return {"written": written}

    async def _do_resize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self.owner.resize(params["label"], int(params["rows"]), int(params["cols"]))
        return {"ok": True}

    async def _do_attach(
        self, params: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> Dict[str, Any]:
        """Turn this connection full-duplex for one terminal.

        After this the owner pushes frames as output arrives, and the same
        connection keeps accepting `write`/`resize`/`detach` — one socket for
        both directions, because a terminal split across two connections can
        deliver a keystroke before the output that prompted it.

        The buffered tail is sent first and **marked as replay**, so the viewer
        sees the screen as it already is rather than starting blank halfway
        through a session. A viewer that cannot tell replay from live output has
        no way to know whether what it is looking at is happening now.
        """
        label = params["label"]
        if label not in self._tails:
            raise OwnerError(f"no terminal owned here for {label}")
        self._subscribe(label, writer)
        tail = bytes(self._tails[label])
        if tail:
            for frame in self._frames(label, tail, replay=True):
                writer.write(frame)
        # THE GEOMETRY THE REPLAY WAS DRAWN AT — B-16.
        #
        # A terminal is a fixed-grid device: the buffered tail is bytes a program
        # laid out for a specific number of columns. A viewer that renders it at
        # a different width does not adapt the screen, it destroys it — and the
        # damage is silent, because the result still looks like a terminal. The
        # viewer had no way to know the width: this ack carried how MUCH was
        # replayed and never what shape it was.
        #
        # Sent as `null` rather than a guess when the fd cannot answer. A wrong
        # geometry here is worse than an absent one, because the viewer would
        # apply it.
        window = None
        try:
            window = self.owner.window(label)
        except OwnerError:  # pragma: no cover - the label was checked above
            logger.debug("fleet owner: no window geometry for %s", label)
        return {
            "attached": label,
            "replayed_bytes": len(tail),
            # A replay that begins mid-stream says so; the viewer's first screen
            # is then honestly incomplete rather than silently so.
            "replay_truncated": self._dropped.get(label, False),
            "viewers": len(self._subscribers.get(label, [])),
            "rows": window[0] if window else None,
            "cols": window[1] if window else None,
        }

    async def _do_detach(
        self, params: Dict[str, Any], writer: asyncio.StreamWriter
    ) -> Dict[str, Any]:
        """Stop watching. Never stops the AGENT — that is `stop`, and it is a
        different act with a different consequence (task 5.4: stopping is
        deliberate, never a side effect of closing a view)."""
        label = params["label"]
        self._unsubscribe(label, writer)
        return {"detached": label, "viewers": len(self._subscribers.get(label, []))}

    async def _do_tail(self, params: Dict[str, Any]) -> Dict[str, Any]:
        import base64
        label = params["label"]
        if label not in self._tails:
            raise OwnerError(f"no terminal owned here for {label}")
        tail = bytes(self._tails[label])
        limit = int(params.get("max_bytes", self.tail_bytes))
        # The SAME resynchronisation as the ring buffer's own cut — B-82. This
        # clip is a second place that starts a byte stream at an arbitrary
        # offset, so it can decapitate an escape sequence in exactly the same
        # way, and a caller rendering this answer would draw `55;1H` as text.
        # Two cuts that must agree, made to agree by calling one function.
        clipped = bytes(tail[_resync(tail, len(tail) - limit):]) if limit < len(tail) else tail
        return {
            "data_b64": base64.b64encode(clipped).decode("ascii"),
            "bytes": len(clipped),
            "drained_total": self._drained.get(label, 0),
            # True when bytes were lost before this tail begins — either the ring
            # wrapped or this answer clipped it. A tail that silently starts
            # mid-stream is the false-absence class.
            "truncated": self._dropped.get(label, False) or len(clipped) < len(tail),
        }

    # -- the socket ------------------------------------------------------- #

    async def _serve_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._clients.add(task)
        try:
            while True:
                line = await reader.readline()
                if not line:
                    return
                try:
                    request = Request.from_json(line.decode("utf-8"))
                except (ValueError, UnicodeDecodeError) as exc:
                    response: Response = make_error("", f"unparseable request: {exc}")
                else:
                    response = await self.dispatch(request, writer)
                writer.write((response.to_json() + "\n").encode("utf-8"))
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            logger.debug("fleet owner: client went away mid-request")
        finally:
            if task is not None:
                self._clients.discard(task)
            # A connection that goes away is a viewer that went away. Nothing
            # else reports it, and a subscriber list that only grows would push
            # into dead transports for the life of the service.
            for label in list(self._subscribers):
                self._unsubscribe(label, writer)
            # `close()` schedules a callback on the loop, so a transport closed
            # after the loop is gone raises `RuntimeError: Event loop is closed`
            # — and this `finally` may be running inside the garbage collector,
            # where nothing can catch it. Python reports that as an *unraisable*
            # exception: the traceback is printed, the interpreter carries on,
            # and no caller ever sees a failure. Measured 2026-08-19: four per
            # test session, and the symptom that finally surfaced was a
            # `KeyError` in an unrelated import lock (task 10.3).
            try:
                writer.close()
            except RuntimeError as exc:
                logger.debug(
                    "fleet owner: closing a client transport after the loop: %s", exc
                )

    def _claim_socket(self) -> None:
        """Take the socket path, or refuse — never clobber a live owner.

        Two owners on one path is the worst failure this service has: the second
        answers `list` with agents it does not hold, and a `write` addressed to a
        real agent lands nowhere. Unlinking a socket is cheap and irreversible,
        so the question asked first is whether anything is listening — not
        whether a file is present, which a crashed owner leaves behind too.
        """
        if not os.path.exists(self.socket_path):
            return
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        probe.settimeout(1.0)
        try:
            probe.connect(self.socket_path)
        except OSError as exc:
            if exc.errno in (errno.ECONNREFUSED, errno.ENOENT):
                logger.warning(
                    "fleet owner: removing the stale socket at %s (nothing listening: %s)",
                    self.socket_path, exc.strerror,
                )
                os.unlink(self.socket_path)
                return
            raise
        finally:
            probe.close()
        raise OwnerError(
            f"another agent owner is already listening on {self.socket_path}; "
            "refusing to start a second one — it would answer for terminals it does not hold"
        )

    async def serve(self) -> None:
        self._claim_socket()
        self._server = await asyncio.start_unix_server(self._serve_client, path=self.socket_path)
        os.chmod(self.socket_path, 0o600)
        logger.info(
            "fleet owner: listening on %s (pid %s)", self.socket_path, os.getpid()
        )
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._request_stop, sig)
        async with self._server:
            await self._stopping.wait()
        await self.shutdown()

    def _request_stop(self, sig: signal.Signals) -> None:
        held = len(self.owner.owned())
        # Not a warning about a mistake — the mechanism. Stated with the number
        # because "the service stopped" and "eleven agents ended" are the same
        # event and only one of them is obvious from the outside.
        logger.info(
            "fleet owner: %s received; %d held agent(s) will end with this process, "
            "because a pty master cannot outlive the process holding it",
            sig.name, held,
        )
        self._stopping.set()

    async def shutdown(self) -> None:
        if self._server is not None:
            # Stop accepting, but do NOT wait here — see the ordering note below.
            self._server.close()

        # Cancelling the handlers runs each one's cleanup while the loop is
        # still alive, which is the only moment it can do its job. Left to the
        # runtime, the `finally` in the handler runs from the garbage collector
        # after the loop is gone: the unsubscribe is skipped and the close
        # raises where nothing can catch it.
        #
        # THE ORDER IS LOAD-BEARING, and it used to be the other way round. This
        # awaited `wait_closed()` first, on the documented-at-the-time behaviour
        # that it "answers about the LISTENING sockets, not about the handlers"
        # and returns with client coroutines still suspended on `readline()`.
        # That stopped being true in Python 3.12, where `wait_closed()` waits
        # for the handlers and the connections as well — so it blocked on the
        # very tasks the lines below exist to cancel, and the cancellation was
        # never reached.
        #
        # Measured 2026-08-27 on Python 3.12.13: one attached client, `close()`
        # then `wait_closed()`, and `wait_closed()` had not returned after four
        # seconds. In production that is an owner that never exits cleanly while
        # a terminal is open — killed by its service manager's stop timeout, with
        # the drain detach and the socket unlink below never run.
        clients = list(self._clients)
        for task in clients:
            task.cancel()
        if clients:
            await asyncio.gather(*clients, return_exceptions=True)
            logger.debug("fleet owner: %d client handler(s) cancelled", len(clients))

        # Now it can be awaited: the handlers are done and their transports are
        # closed, so this returns on every version rather than only on the ones
        # where it answered a narrower question.
        if self._server is not None:
            await self._server.wait_closed()
        for agent in self.owner.owned():
            self._detach_drain(agent.master_fd)
        try:
            os.unlink(self.socket_path)
        except OSError as exc:
            logger.debug("fleet owner: unlinking %s: %s", self.socket_path, exc)
        logger.info("fleet owner: stopped")


# --------------------------------------------------------------------------- #
# entry point — installed as `set-agent-owner` (pyproject `[project.scripts]`)
# --------------------------------------------------------------------------- #

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="set-agent-owner",
        description="Holds the terminals of agents started from the fleet screen.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    serve_cmd = sub.add_parser("serve", help="run the owner service")
    serve_cmd.add_argument("--socket", default=None, help="socket path")
    serve_cmd.add_argument("--tail-bytes", type=int, default=DEFAULT_TAIL_BYTES)
    serve_cmd.add_argument("--log-level", default="INFO")

    health_cmd = sub.add_parser("health", help="ask a running owner how it is")
    health_cmd.add_argument("--socket", default=None, help="socket path")

    args = parser.parse_args(argv)
    # Only `serve` brings the directory into being. `health` is a client, and a
    # client that creates the runtime directory as a side effect of asking where
    # the socket is makes "the owner is not running" indistinguishable from
    # "nothing has ever run here".
    socket_path = args.socket or default_socket_path(create=args.command == "serve")

    if args.command == "health":
        from .owner_client import OwnerClient, OwnerUnavailable
        try:
            print(json.dumps(OwnerClient(socket_path).health(), indent=2))
        except OwnerUnavailable as exc:
            print(str(exc), file=sys.stderr)
            return 3
        return 0

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    daemon = OwnerDaemon(socket_path, tail_bytes=args.tail_bytes)
    try:
        asyncio.run(daemon.serve())
    except OwnerError as exc:
        logger.error("%s", exc)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
