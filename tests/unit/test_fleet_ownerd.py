"""The owner service and the socket the dashboard reaches it through — task 5.8.

What is asserted here is the *decision logic*: what the daemon refuses, what the
client refuses to do on the caller's behalf, and whether the tail admits to
having lost bytes. The mechanism itself — that a real agent starts in a sibling
scope and does not freeze — was measured end to end on 2026-08-18 and is not
reproducible in a unit test:

    with the drain:     the child wrote 400 000 bytes and exited
    with it disabled:   the child wrote 0 and blocked, and had to be killed

That mutation is why `_attach_drain` exists at all, and it is stated here because
a unit test cannot hold it: nothing short of a real pty and a real writer
distinguishes "drained" from "never had to be".

The load-bearing test in this file is `test_a_live_socket_is_never_clobbered`.
The rest guard mistakes that announce themselves; that one guards a mistake that
does not — two owners on one path, the second answering `list` with agents it
does not hold and losing every keystroke addressed to a real one.
"""

from __future__ import annotations

import asyncio
import base64
import os
import socket

import pytest

from set_orch.fleet import ownerd as ownerd_mod
from set_orch.fleet.owner import OwnedAgent, OwnerError
from set_orch.fleet.owner_client import (
    START_COMMAND,
    OwnerClient,
    OwnerClientError,
    OwnerUnavailable,
    owner_available,
)
from set_orch.fleet.ownerd import OwnerDaemon
from set_orch.fleet.protocol import (
    SUPPORTED_METHODS, Request, Response, make_frame,
)


def _run(coro):
    """Run a coroutine WITHOUT disturbing the thread's ambient event loop.

    `asyncio.run()` would be the obvious call and it is the wrong one here: it
    closes the loop it created *and* clears the thread's current loop, so every
    later test that reaches for `asyncio.get_event_loop()` gets a `RuntimeError`
    rather than a loop.

    Measured 2026-08-18, and the direction is what makes it worth a comment: an
    earlier version of this file used `asyncio.run` and turned **10 tests in
    `test_status_follow_stream.py` red** — none of which touch the fleet, and all
    of which pass when that file is run on its own. The failure surfaces far from
    its cause, in a full-suite run, and reads as a regression in unrelated code.

    `new_event_loop()` does not call `set_event_loop`, so the ambient state is
    left exactly as it was found.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _daemon(tmp_path, **kwargs) -> OwnerDaemon:
    return OwnerDaemon(str(tmp_path / "owner.sock"), **kwargs)


def test_this_file_leaves_the_ambient_event_loop_alone():
    """Holds the pattern that was WRONG, so a later simplification back to
    `asyncio.run()` fails HERE instead of in ten unrelated streaming tests that
    only fail in a full-suite run. A comment asks to be believed; a test refuses
    to be reverted.
    """
    try:
        previous = asyncio.get_event_loop()
    except RuntimeError:
        previous = None
    marker = asyncio.new_event_loop()
    asyncio.set_event_loop(marker)
    try:
        _run(asyncio.sleep(0))
        assert asyncio.get_event_loop() is marker, (
            "running a coroutine here replaced or cleared the thread's event loop"
        )
    finally:
        asyncio.set_event_loop(previous)
        marker.close()


# --------------------------------------------------------------------------- #
# the protocol
# --------------------------------------------------------------------------- #

def test_bytes_travel_base64_so_a_split_utf8_sequence_survives():
    """A pty read can end in the middle of a multi-byte character — that is
    normal, not corruption. Carrying terminal bytes as a JSON string would force
    a decode at the boundary and lose them silently, which is the direction that
    looks like data.
    """
    half = "á".encode()[:1]                       # a lone continuation-less lead byte
    with pytest.raises(UnicodeDecodeError):
        half.decode("utf-8")                      # it genuinely cannot be a string
    wire = base64.b64encode(half).decode("ascii")
    assert base64.b64decode(wire) == half


def test_an_unknown_method_is_refused_and_the_answer_names_what_exists(tmp_path):
    daemon = _daemon(tmp_path)
    resp = _run(daemon.dispatch(Request(method="exec", params={})))
    assert not resp.ok
    assert "exec" in resp.error
    # An error that only says "no" makes the caller guess the surface.
    for method in ("start", "stop", "health"):
        assert method in resp.error


def test_every_supported_method_has_a_handler(tmp_path):
    """A name in the protocol with no handler behind it fails as `AttributeError`
    at request time — a shape error reported as a crash.
    """
    daemon = _daemon(tmp_path)
    missing = [m for m in SUPPORTED_METHODS if not hasattr(daemon, f"_do_{m}")]
    assert missing == []


# --------------------------------------------------------------------------- #
# the drain and its tail
# --------------------------------------------------------------------------- #

class _FakeOwner:
    """Enough of `AgentOwner` to drive the daemon without systemd or a pty."""

    def __init__(self, chunks=()):
        self._chunks = list(chunks)
        self.agents = []
        self.stopped = []

    def read(self, label, size=65536):
        return self._chunks.pop(0) if self._chunks else b""

    def owned(self):
        return list(self.agents)

    def stop(self, label):
        self.stopped.append(label)
        return True


def test_the_tail_is_bounded_and_admits_when_it_lost_its_head(tmp_path):
    """A tail that silently starts mid-stream reads as the whole stream. The
    same false-absence class as a count taken from a declaration.
    """
    daemon = _daemon(tmp_path, owner=_FakeOwner([b"a" * 100, b"b" * 100]), tail_bytes=150)
    daemon._tails["x"] = bytearray()
    daemon._dropped["x"] = False
    daemon._drained["x"] = 0

    daemon._drain("x", -1)
    assert daemon._dropped["x"] is False           # 100 bytes still fit
    daemon._drain("x", -1)

    assert len(daemon._tails["x"]) == 150          # bounded
    assert daemon._dropped["x"] is True            # and it says so
    assert daemon._drained["x"] == 200             # while the true total is kept
    assert bytes(daemon._tails["x"]).endswith(b"b" * 100)


def test_the_tail_answer_reports_truncation_it_caused_itself(tmp_path):
    """Clipping to `max_bytes` is also a lost head, even when the ring never
    wrapped — the flag is about the answer, not only about the buffer.
    """
    daemon = _daemon(tmp_path, owner=_FakeOwner(), tail_bytes=1000)
    daemon._tails["x"] = bytearray(b"z" * 500)
    daemon._dropped["x"] = False
    daemon._drained["x"] = 500

    whole = _run(daemon.dispatch(Request(method="tail", params={"label": "x"})))
    assert whole.result["truncated"] is False

    clipped = _run(daemon.dispatch(Request(method="tail", params={"label": "x", "max_bytes": 10})))
    assert clipped.result["bytes"] == 10
    assert clipped.result["truncated"] is True
    assert clipped.result["drained_total"] == 500


def test_a_tail_for_an_unheld_terminal_is_a_refusal_not_an_empty_answer(tmp_path):
    """An empty tail and no terminal at all must not look alike."""
    daemon = _daemon(tmp_path, owner=_FakeOwner())
    resp = _run(daemon.dispatch(Request(method="tail", params={"label": "nobody"})))
    assert not resp.ok
    assert "nobody" in resp.error


def test_an_owner_refusal_comes_back_as_an_error_not_as_a_crash(tmp_path):
    class _Refusing(_FakeOwner):
        def stop(self, label):
            raise OwnerError("this owner does not hold that")

    daemon = _daemon(tmp_path, owner=_Refusing())
    resp = _run(daemon.dispatch(Request(method="stop", params={"label": "x"})))
    assert not resp.ok and "does not hold" in resp.error


def test_a_missing_parameter_is_a_bad_request_not_a_daemon_fault(tmp_path):
    daemon = _daemon(tmp_path, owner=_FakeOwner())
    resp = _run(daemon.dispatch(Request(method="stop", params={})))
    assert not resp.ok and "bad request" in resp.error


# --------------------------------------------------------------------------- #
# the socket — the load-bearing part
# --------------------------------------------------------------------------- #

def test_a_live_socket_is_never_clobbered(tmp_path):
    """Two owners on one path is the worst failure this service has: the second
    answers for terminals it does not hold, and every keystroke addressed to a
    real agent lands nowhere. Unlinking is irreversible, so the question asked
    first is whether anything is *listening* — not whether a file is there.
    """
    path = str(tmp_path / "owner.sock")
    live = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    live.bind(path)
    live.listen(1)
    try:
        daemon = OwnerDaemon(path)
        with pytest.raises(OwnerError) as excinfo:
            daemon._claim_socket()
        assert "already listening" in str(excinfo.value)
        assert os.path.exists(path), "the live owner's socket must survive the refusal"
    finally:
        live.close()


def test_a_stale_socket_file_is_removed_rather_than_refused(tmp_path):
    """The other direction, and it matters as much: a crashed owner leaves the
    file behind, and refusing on file-presence would make every crash need a
    manual `rm` before the service could start again.
    """
    path = str(tmp_path / "owner.sock")
    dead = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    dead.bind(path)
    dead.close()                                   # bound, never listened, now gone
    assert os.path.exists(path)

    OwnerDaemon(path)._claim_socket()
    assert not os.path.exists(path)


def test_a_file_presence_check_would_not_have_told_the_two_apart(tmp_path):
    """Holds the pattern that was WRONG, so a later simplification back to
    `os.path.exists` fails instead of looking identical and checking nothing.
    """
    live_path = str(tmp_path / "live.sock")
    stale_path = str(tmp_path / "stale.sock")
    live = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    live.bind(live_path)
    live.listen(1)
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(stale_path)
    stale.close()
    try:
        assert os.path.exists(live_path) == os.path.exists(stale_path) is True
        # The two need opposite handling, and file presence is identical for both.
        with pytest.raises(OwnerError):
            OwnerDaemon(live_path)._claim_socket()
        OwnerDaemon(stale_path)._claim_socket()
    finally:
        live.close()


# --------------------------------------------------------------------------- #
# the client — what it refuses to do FOR you
# --------------------------------------------------------------------------- #

def test_the_client_does_not_start_the_owner_and_says_which_command_does(tmp_path):
    """The one place this client departs from `set_memoryd.client`, which
    auto-starts its daemon. An owner started from inside the web service joins
    its control group and dies with it (CB-1) — the exact defect the second
    service exists to remove. Convenience here would rebuild it silently.
    """
    path = str(tmp_path / "nothing.sock")
    with pytest.raises(OwnerUnavailable) as excinfo:
        OwnerClient(path).health()
    message = str(excinfo.value)
    assert START_COMMAND in message
    assert not os.path.exists(path), "an absent owner must not be started by the caller"


def test_availability_is_asked_by_connecting_not_by_file_presence(tmp_path):
    """A crashed owner leaves its socket file behind. Reading presence as
    availability is the proxy-instead-of-the-thing class, and it fails toward
    'yes' — the screen would offer a start that cannot work.
    """
    path = str(tmp_path / "owner.sock")
    dead = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    dead.bind(path)
    dead.close()
    assert os.path.exists(path)
    assert owner_available(path) is False


def test_a_refusal_from_the_owner_is_not_reported_as_unavailability(tmp_path):
    """"The owner said no" and "the owner is not there" need opposite responses
    from the surface — a 409 and a 503 — so the client must not collapse them
    into one error. Driven over a real socket, because the distinction is made
    on the wire and a type-level assertion would not exercise it.
    """
    path = str(tmp_path / "owner.sock")

    class _Refusing(_FakeOwner):
        def stop(self, label):
            raise OwnerError("label already owned here")

    daemon = OwnerDaemon(path, owner=_Refusing())

    async def scenario():
        daemon._claim_socket()
        server = await asyncio.start_unix_server(daemon._serve_client, path=path)
        async with server:
            return await asyncio.to_thread(_call)

    def _call():
        try:
            OwnerClient(path).stop("x")
        except BaseException as exc:  # noqa: BLE001 - the type IS the assertion
            return exc
        return None

    error = _run(scenario())
    assert isinstance(error, OwnerClientError)
    assert not isinstance(error, OwnerUnavailable), (
        "a reachable owner that refused must not be reported as an absent one"
    )
    assert "already owned" in str(error)


# --------------------------------------------------------------------------- #
# round trip over a real socket
# --------------------------------------------------------------------------- #

def test_a_request_crosses_the_socket_and_comes_back(tmp_path):
    path = str(tmp_path / "owner.sock")
    daemon = OwnerDaemon(path, owner=_FakeOwner())

    async def scenario():
        daemon._claim_socket()
        server = await asyncio.start_unix_server(daemon._serve_client, path=path)
        async with server:
            result = await asyncio.to_thread(OwnerClient(path).health)
        return result

    health = _run(scenario())
    assert health["ok"] is True
    assert health["held"] == 0
    assert health["socket"] == path


def test_an_unparseable_line_is_answered_rather_than_dropped(tmp_path):
    """A client that gets no answer waits for its read timeout — 30 seconds of
    looking like a slow owner instead of one second of a clear error.
    """
    path = str(tmp_path / "owner.sock")
    daemon = OwnerDaemon(path, owner=_FakeOwner())

    async def scenario():
        daemon._claim_socket()
        server = await asyncio.start_unix_server(daemon._serve_client, path=path)

        def talk():
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(path)
            sock.sendall(b"{not json at all\n")
            data = sock.recv(65536)
            sock.close()
            return data

        async with server:
            return await asyncio.to_thread(talk)

    answer = Response.from_json(_run(scenario()).decode())
    assert not answer.ok and "unparseable" in answer.error


# --------------------------------------------------------------------------- #
# the stream — two bugs an end-to-end probe found that unit tests had not
# --------------------------------------------------------------------------- #

class _Streamable(_FakeOwner):
    """An owner with one held agent whose terminal we can feed by hand."""

    def __init__(self):
        super().__init__()
        self.written = []

    def write(self, label, data):
        self.written.append((label, data))
        return len(data)

    def resize(self, label, rows, cols):
        self.resized = (label, rows, cols)


def _daemon_with_terminal(path, tail=b"SCREEN-AS-IT-WAS"):
    daemon = OwnerDaemon(path, owner=_Streamable())
    daemon._tails["term"] = bytearray(tail)
    daemon._dropped["term"] = False
    daemon._drained["term"] = len(tail)
    return daemon


def test_the_replayed_screen_is_not_eaten_by_the_attach_response(tmp_path):
    """The first of two bugs the end-to-end probe found, and the reason the
    client may not read its own answers.

    The owner writes the buffered screen BEFORE the attach response. A client
    that reads lines until one carries an `id`, skipping what it passes, throws
    that screen away — measured live: **1752 bytes sent, 44 arrived**, and the
    terminal's first screen was wrong rather than absent, which is the direction
    nobody investigates.
    """
    path = str(tmp_path / "owner.sock")
    daemon = _daemon_with_terminal(path)

    async def scenario():
        from set_orch.fleet.owner_client import OwnerStream
        daemon._claim_socket()
        server = await asyncio.start_unix_server(daemon._serve_client, path=path)
        async with server:
            stream = OwnerStream("term", path)
            ack = await asyncio.wait_for(stream.open(), timeout=5)
            # Bounded on purpose. A regression here makes this WAIT rather than
            # fail — measured: the mutation that drops frames turned this test
            # into a hang, and a hanging test burns a CI budget and reads as an
            # infrastructure flake, which is how a real guard gets disabled.
            frame, replay = await asyncio.wait_for(stream.frames().__anext__(), timeout=5)
            await stream.close()
            return ack, frame, replay

    ack, frame, replay = _run(scenario())
    assert ack["replayed_bytes"] == len(b"SCREEN-AS-IT-WAS")
    assert frame == b"SCREEN-AS-IT-WAS", "the replayed screen was consumed by the response reader"
    assert replay is True, "a viewer that cannot tell replay from live output cannot know what is now"


def test_a_keystroke_while_streaming_does_not_kill_the_connection(tmp_path):
    """The second bug, and it produced a terminal that showed output until you
    touched it: with the output pump and a keystroke's request both reading the
    same stream, the connection died on the first keystroke.

    Exactly one loop may read. This drives the failing shape — write WHILE
    consuming frames — because a test that writes with nothing pumping would
    pass on the broken version too.
    """
    path = str(tmp_path / "owner.sock")
    daemon = _daemon_with_terminal(path)

    async def scenario():
        from set_orch.fleet.owner_client import OwnerStream
        daemon._claim_socket()
        server = await asyncio.start_unix_server(daemon._serve_client, path=path)
        async with server:
            stream = OwnerStream("term", path)
            await asyncio.wait_for(stream.open(), timeout=5)

            seen = []

            async def pump():
                async for data, _replay in stream.frames():
                    seen.append(data)

            pumping = asyncio.create_task(pump())
            await asyncio.sleep(0.05)
            # Bounded: the two-readers bug makes this hang rather than raise.
            written = await asyncio.wait_for(
                stream.write(b"keystroke"), timeout=5                 # while the pump reads
            )
            daemon._drain_from(b"echo")                          # live output after it
            await asyncio.sleep(0.05)
            await asyncio.wait_for(stream.resize(30, 100), timeout=5)   # still live
            await asyncio.sleep(0.05)
            pumping.cancel()
            await stream.close()
            return written, seen

    written, seen = _run(scenario())
    assert written == len(b"keystroke")
    assert daemon.owner.written == [("term", b"keystroke")]
    assert daemon.owner.resized == ("term", 30, 100)
    assert b"echo" in b"".join(seen), "live output after a keystroke never arrived"


def test_a_frame_and_a_response_are_told_apart_by_the_id_not_by_the_result(tmp_path):
    """Drives the discriminator instead of asserting about shapes.

    A first version of this test compared a frame dict with a response dict and
    passed on the broken client too — mutating `if request_id is not None` to
    `if payload.get("result") is not None` changed nothing it could see, because
    no method in this protocol currently returns a null result. That made it a
    test of today's method list rather than of the rule.

    So the server here answers with `result: null` on purpose. If the client
    branches on the result instead of on the id, that answer is taken for a
    terminal frame, the request never resolves, and the `wait_for` below fails
    instead of the whole suite hanging.
    """
    import json as _json
    path = str(tmp_path / "owner.sock")

    async def scenario():
        from set_orch.fleet.owner_client import OwnerStream

        async def handle(reader, writer):
            line = await reader.readline()                 # the attach
            request_id = _json.loads(line)["id"]
            writer.write((make_frame("term", base64.b64encode(b"SCREEN").decode()) + "\n").encode())
            # A response whose result IS null — the shape the mutation confuses.
            writer.write((_json.dumps({"id": request_id, "result": None}) + "\n").encode())
            await writer.drain()

        server = await asyncio.start_unix_server(handle, path=path)
        async with server:
            stream = OwnerStream("term", path)
            ack = await asyncio.wait_for(stream.open(), timeout=5)
            frame, _replay = await asyncio.wait_for(stream.frames().__anext__(), timeout=5)
            return ack, frame

    ack, frame = _run(scenario())
    assert ack is None, "a null result is a real answer, not an absent one"
    assert frame == b"SCREEN", "the frame was consumed as though it were the response"


def test_a_viewer_detaching_leaves_the_agent_held_and_running(tmp_path):
    """Task 5.4: stopping is a deliberate act, never a consequence of closing a
    view. Driven through the real attach/detach path rather than asserted about
    it, because the hazard is a future "tidy up on disconnect" — which would look
    reasonable and would live exactly where this test drives.

    Verified end to end on 2026-08-19 too: after the WebSocket closed, the agent
    was still in the fleet listing. This holds the code path so the live check
    does not have to be the only guard.
    """
    path = str(tmp_path / "owner.sock")
    daemon = _daemon_with_terminal(path)
    daemon.owner.agents = [
        OwnedAgent(label="term", unit="set-agent-term.scope", pid=7, cwd="/tmp", master_fd=-1)
    ]

    async def scenario():
        from set_orch.fleet.owner_client import OwnerStream
        daemon._claim_socket()
        server = await asyncio.start_unix_server(daemon._serve_client, path=path)
        async with server:
            stream = OwnerStream("term", path)
            await asyncio.wait_for(stream.open(), timeout=5)
            await stream.close()
            await asyncio.sleep(0.05)
            return len(daemon._subscribers.get("term", [])), [a.label for a in daemon.owner.owned()]

    viewers, still_held = _run(scenario())
    assert viewers == 0, "the viewer was not forgotten"
    assert still_held == ["term"], "closing a view stopped the agent"
    assert daemon.owner.stopped == [], "detach must never reach the stop path"


def test_a_second_viewer_attaches_to_the_same_terminal(tmp_path):
    """Reattachable, and by more than one reader: the terminal belongs to the
    owner, not to whoever is looking at it. Each arrival is sent the buffered
    screen, so a viewer that joins late does not start blank halfway through.
    """
    path = str(tmp_path / "owner.sock")
    daemon = _daemon_with_terminal(path, tail=b"ALREADY-ON-SCREEN")

    async def scenario():
        from set_orch.fleet.owner_client import OwnerStream
        daemon._claim_socket()
        server = await asyncio.start_unix_server(daemon._serve_client, path=path)
        async with server:
            first = OwnerStream("term", path)
            second = OwnerStream("term", path)
            ack1 = await asyncio.wait_for(first.open(), timeout=5)
            ack2 = await asyncio.wait_for(second.open(), timeout=5)
            f1, _ = await asyncio.wait_for(first.frames().__anext__(), timeout=5)
            f2, _ = await asyncio.wait_for(second.frames().__anext__(), timeout=5)
            daemon._drain_from(b"-LIVE")
            l1, _ = await asyncio.wait_for(first.frames().__anext__(), timeout=5)
            l2, _ = await asyncio.wait_for(second.frames().__anext__(), timeout=5)
            await first.close()
            await second.close()
            return ack1["viewers"], ack2["viewers"], (f1, f2), (l1, l2)

    v1, v2, replays, lives = _run(scenario())
    assert (v1, v2) == (1, 2)
    assert replays == (b"ALREADY-ON-SCREEN", b"ALREADY-ON-SCREEN")
    assert lives == (b"-LIVE", b"-LIVE"), "live output must reach every viewer, not just the first"


def test_a_full_screen_replay_survives_the_wire(tmp_path):
    """The third bug the live probe found, and the only one that was CERTAIN
    rather than merely likely.

    Measured 2026-08-19 in a browser: the first attach to a freshly started
    agent worked (0 bytes replayed), and the reattach a minute later reported
    *the agent owner closed the terminal connection* — with the owner's own log
    showing a clean attach at the same second. The owner had closed nothing.

    A frame is one JSON line and its payload is base64, so N raw bytes go out as
    4N/3. `asyncio.StreamReader` refuses a line over 64 KiB and raises
    `LimitOverrunError`; that is not a short read and not a closed socket, so
    the read loop died with an exception nobody retrieved and every waiter was
    told the owner had hung up.

    The two sizes in this file made it deterministic, not a race: `tail_bytes`
    is 64 KiB and `owner.read()` takes 64 KiB at once, so any terminal that had
    produced ~48 KiB could never be reattached to again. The failure direction
    is what hid it — an EMPTY terminal is exactly the case that works, so every
    quick check passed.

    Sized at 60 KiB: over the 48 KiB where the old code starts failing, under
    the 64 KiB tail cap so nothing here is testing truncation instead.
    """
    path = str(tmp_path / "owner.sock")
    screen = bytes(bytearray((i * 7 + 33) % 94 + 32 for i in range(60 * 1024)))
    daemon = _daemon_with_terminal(path, tail=screen)

    async def scenario():
        from set_orch.fleet.owner_client import OwnerStream
        daemon._claim_socket()
        server = await asyncio.start_unix_server(daemon._serve_client, path=path)
        async with server:
            stream = OwnerStream("term", path)
            ack = await asyncio.wait_for(stream.open(), timeout=5)
            got = bytearray()
            frames = stream.frames()
            while len(got) < len(screen):
                chunk, replay = await asyncio.wait_for(frames.__anext__(), timeout=5)
                assert replay is True, "a replayed chunk that claims to be live misdates the screen"
                got.extend(chunk)
            await stream.close()
            return ack, bytes(got)

    ack, got = _run(scenario())
    assert ack["replayed_bytes"] == len(screen)
    # Whole and in order. A split that loses or reorders a piece renders as
    # garbage rather than as a gap, because escape sequences do not survive
    # being cut — so equality is the only assertion worth making here.
    assert got == screen, "the replayed screen did not arrive intact"


def test_no_single_frame_exceeds_the_readers_line_limit(tmp_path):
    """The rule stated as a size, so a later change cannot quietly re-cross it.

    The test above proves the client survives today's owner. This one proves the
    OWNER stays inside the limit that any default `StreamReader` enforces —
    including one in a different process, an older client, or a consumer written
    against the protocol rather than against this class.
    """
    daemon = OwnerDaemon(str(tmp_path / "owner.sock"), owner=_Streamable())
    frames = daemon._frames("term", b"x" * (64 * 1024), replay=True)
    assert len(frames) > 1, "a 64 KiB chunk must not go out as one line"
    assert max(len(f) for f in frames) < 64 * 1024, (
        "a frame at or over 64 KiB kills a default StreamReader with LimitOverrunError"
    )
    # The split is the only thing allowed to change the shape; the bytes are not.
    import base64 as _b64, json as _json
    rebuilt = b"".join(_b64.b64decode(_json.loads(f)["data_b64"]) for f in frames)
    assert rebuilt == b"x" * (64 * 1024)
