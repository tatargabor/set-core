"""Channel-graph derivation — the pure core of the wire view.

Written against the RESULT payloads: the join order, the direction parse, the
degradation markers. The store is faked as a real directory tree in tmp_path,
because the mtimes and file names under `channels/` ARE the mechanism.
"""

from __future__ import annotations

import os
import time

import pytest

from set_orch.fleet import channels
from set_orch.fleet.channels import LiveAgent, derive_channel_graph, resolve_store_root


# --------------------------------------------------------------------------- #
# fixtures — a seat roster in the shape read_seats returns, and a store tree
# --------------------------------------------------------------------------- #


class Seat:
    """Duck-typed stand-in for instruct.Seat — only what the join reads."""

    def __init__(self, seat, session, rooms=(), project=None):
        self.seat = seat
        self.agent = seat.split("#")[0]
        self.session = session
        self.rooms = tuple(rooms)
        self.project = project


def _store(tmp_path):
    root = tmp_path / "store"
    (root / "channels").mkdir(parents=True)
    return root


def _channel(root, room, seat_name, age_seconds=10.0, body="secret partner content"):
    """One sender file in one channel. `body` is deliberately sensitive-ish:
    the confidentiality assertion greps the payload for exactly this string."""
    room_dir = root / "channels" / room
    room_dir.mkdir(parents=True, exist_ok=True)
    path = room_dir / f"{seat_name}.md"
    if body:
        path.write_text(
            f"## 2026-08-30T10:00:00 — ANSWER → other#aabbcc (re: x)\n\n{body}\n")
    old = NOW - age_seconds
    os.utime(path, (old, old))
    return path


SEATS = {
    "sess-a": Seat("alpha#111111", "sess-a", rooms=("war-room", "dm-alpha-bravo"),
                   project="/proj/a"),
    "sess-b": Seat("bravo#222222", "sess-b", rooms=("war-room", "dm-alpha-bravo")),
    "sess-c": Seat("charlie#333333", "sess-c", rooms=("war-room",)),
    "sess-d": Seat("delta#444444", "sess-d", rooms=("lonely-room",)),
}

AGENTS = [
    LiveAgent(pid=1, session_id="sess-a", project_root="/proj/a", name="a"),
    LiveAgent(pid=2, session_id="sess-b", project_root="/proj/b", name="b"),
    LiveAgent(pid=3, session_id="sess-c", project_root="/proj/c", name="c"),
    LiveAgent(pid=4, session_id="sess-d", project_root="/proj/d", name="d"),
    # A live agent with no seat at all — the not-enrolled case.
    LiveAgent(pid=5, session_id="sess-e", project_root="/proj/e", name="e"),
]

NOW = 1_750_000_000.0


def _graph(tmp_path, seats=SEATS, agents=AGENTS, store=None):
    return derive_channel_graph(seats, store if store is not None else _store(tmp_path),
                                agents, now=NOW)


def _edge(payload, room):
    return next(e for e in payload["edges"] if e["room"] == room)


# --------------------------------------------------------------------------- #
# join
# --------------------------------------------------------------------------- #


def test_session_join_marks_enrolled(tmp_path):
    payload = _graph(tmp_path)
    node = next(n for n in payload["nodes"] if n["sessionId"] == "sess-a")
    assert node["enrolled"] is True
    assert node["seat"] == "alpha#111111"


def test_unenrolled_live_agent_still_gets_a_node(tmp_path):
    payload = _graph(tmp_path)
    node = next(n for n in payload["nodes"] if n["sessionId"] == "sess-e")
    assert node["enrolled"] is False
    assert node["seat"] is None


def test_unique_project_root_fallback_joins(tmp_path):
    agents = [LiveAgent(pid=9, session_id=None, project_root="/proj/a")]
    payload = _graph(tmp_path, agents=agents)
    assert payload["nodes"][0]["enrolled"] is True
    assert payload["nodes"][0]["seat"] == "alpha#111111"


def test_ambiguous_project_root_stays_unjoined(tmp_path):
    seats = {
        "sess-a": Seat("alpha#111111", "sess-a", project="/proj/shared"),
        "sess-b": Seat("bravo#222222", "sess-b", project="/proj/shared"),
    }
    agents = [LiveAgent(pid=9, session_id="sess-other", project_root="/proj/shared")]
    payload = _graph(tmp_path, seats=seats, agents=agents)
    assert payload["nodes"][0]["enrolled"] is False


def test_enrolled_but_not_live_produces_no_node(tmp_path):
    seats = dict(SEATS)
    seats["sess-ghost"] = Seat("ghost#999999", "sess-ghost", rooms=("war-room",))
    payload = _graph(tmp_path, seats=seats)
    assert all(n["sessionId"] != "sess-ghost" for n in payload["nodes"])


# --------------------------------------------------------------------------- #
# edges
# --------------------------------------------------------------------------- #


def test_shared_room_becomes_an_edge(tmp_path):
    payload = _graph(tmp_path)
    edge = _edge(payload, "war-room")
    assert sorted(edge["members"]) == ["sess-a", "sess-b", "sess-c"]


def test_room_with_one_live_member_has_no_edge(tmp_path):
    payload = _graph(tmp_path)
    assert all(e["room"] != "lonely-room" for e in payload["edges"])


def test_direction_from_addressee_heading(tmp_path):
    root = _store(tmp_path)
    _channel(root, "war-room", "alpha#111111")
    payload = _graph(tmp_path, store=root)
    edge = _edge(payload, "war-room")
    assert edge["fromSeat"] == "alpha#111111"
    assert edge["from"] == "sess-a"
    assert "sess-b" in edge["to"] or edge["to"] == []
    # The heading names other#aabbcc, which is no live member — so the
    # addresses resolve to nobody and the edge degrades to broadcast (empty
    # `to`), never to a wire that animates nowhere.
    assert edge["to"] == []


def test_direction_to_a_live_member(tmp_path):
    root = _store(tmp_path)
    path = root / "channels" / "war-room" / "alpha#111111.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("## 2026-08-30T10:00:00 — QUESTION → bravo#222222\n\nbody\n")
    os.utime(path, (NOW - 10, NOW - 10))
    payload = _graph(tmp_path, store=root)
    edge = _edge(payload, "war-room")
    assert edge["from"] == "sess-a"
    assert edge["to"] == ["sess-b"]


def test_unparseable_newest_write_degrades_to_broadcast(tmp_path):
    root = _store(tmp_path)
    path = root / "channels" / "war-room" / "bravo#222222.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("no heading at all, just prose\n")
    os.utime(path, (NOW - 10, NOW - 10))
    payload = _graph(tmp_path, store=root)
    edge = _edge(payload, "war-room")
    assert edge["from"] == "sess-b"
    assert edge["to"] == []


def test_recency_window(tmp_path):
    root = _store(tmp_path)
    _channel(root, "war-room", "alpha#111111", age_seconds=10.0)
    fresh = derive_channel_graph(SEATS, root, AGENTS, now=NOW)
    assert _edge(fresh, "war-room")["recent"] is True
    stale = derive_channel_graph(SEATS, root, AGENTS, now=NOW,
                                 activity_window=5.0)
    assert _edge(stale, "war-room")["recent"] is False


def test_missing_channel_dir_leaves_an_edge_without_activity(tmp_path):
    payload = _graph(tmp_path)  # store exists, channels/ is empty
    edge = _edge(payload, "war-room")
    assert edge["lastActivity"] is None
    assert edge["recent"] is False
    assert edge["from"] is None


# --------------------------------------------------------------------------- #
# degradation + configuration
# --------------------------------------------------------------------------- #


def test_missing_store_sets_source_unavailable(tmp_path):
    payload = derive_channel_graph(SEATS, tmp_path / "absent", AGENTS, now=NOW)
    assert payload["sourceAvailable"] is False
    assert payload["edges"] == []
    # Nodes still travel: the fleet's live agents are real even when the store
    # is not there. (Enrolment flags come from the roster, which does not need
    # the store dir — but with sourceAvailable false the client renders the
    # source-down note instead of any enrolment claim.)
    assert len(payload["nodes"]) == len(AGENTS)


def test_unaskable_bus_sets_source_unavailable(tmp_path):
    payload = derive_channel_graph(None, _store(tmp_path), AGENTS, now=NOW)
    assert payload["sourceAvailable"] is False


def test_live_store_sets_source_available(tmp_path):
    payload = _graph(tmp_path)
    assert payload["sourceAvailable"] is True


def test_store_root_env_override(monkeypatch):
    monkeypatch.setenv("SET_AGENT_COMM_DIR", "/custom/store")
    assert resolve_store_root() == __import__("pathlib").Path("/custom/store")
    monkeypatch.delenv("SET_AGENT_COMM_DIR")
    monkeypatch.setenv("XDG_DATA_HOME", "/xdg")
    assert resolve_store_root().name == "set-agent-comm"
    monkeypatch.delenv("XDG_DATA_HOME")
    assert resolve_store_root().name == "set-agent-comm"


# --------------------------------------------------------------------------- #
# confidentiality
# --------------------------------------------------------------------------- #


def test_message_body_never_reaches_payload(tmp_path):
    root = _store(tmp_path)
    _channel(root, "war-room", "alpha#111111", body="InvoiceUrgent Corp unpaid 4000 EUR")
    payload = _graph(tmp_path, store=root)
    import json
    blob = json.dumps(payload)
    assert "InvoiceUrgent" not in blob
    assert "4000 EUR" not in blob
    # And the shape that would carry it: no edge field is free prose.
    for edge in payload["edges"]:
        assert set(edge.keys()) == {
            "room", "members", "memberSeats", "from", "fromSeat", "to",
            "lastActivity", "recent"}


def test_addressee_parser_stops_at_back_reference():
    line = "## 2026-08-30T10:00:00 — ANSWER → bravo#222222 (re: alpha#111111)"
    assert channels._parse_addressees(line) == ["bravo#222222"]


@pytest.mark.parametrize("line,expected", [
    ("## t — REQUEST → bravo#222222, charlie#333333", ["bravo#222222", "charlie#333333"]),
    ("no arrow here", []),
    ("→ alpha#111111 → bravo#222222", ["alpha#111111", "bravo#222222"]),  # pathological: both after the first arrow
])
def test_addressee_parser_cases(line, expected):
    assert channels._parse_addressees(line) == expected


# --------------------------------------------------------------------------- #
# the route — degradation through the real FastAPI surface
# --------------------------------------------------------------------------- #


def test_route_answers_200_with_empty_edges_and_marker_when_store_missing(monkeypatch):
    """AC-9 through the HTTP surface, not the function: a store that is not
    there must be a 200 with the marker, never a 500 and never a bare graph
    that reads as 'no communication'."""
    from fastapi.testclient import TestClient
    from set_orch.server import create_app
    from set_orch.api import fleet as fleet_module
    from set_orch.fleet import instruct as instruct_module

    class _Agent:
        pid, session_id, project_root, name = 7, "sess-a", "/proj/a", "a"

    monkeypatch.setattr(fleet_module, "discover_agents", lambda *a, **k: [_Agent()])
    # A fresh, unanswered roster answer (monotonic now) — the route must take
    # the cached None rather than reaching for a real `sac` on this machine.
    import time as _time
    monkeypatch.setattr(instruct_module, "_SEATS_CACHE",
                        [_time.monotonic(), None])
    monkeypatch.setattr(fleet_module.fleet_channels_mod, "resolve_store_root",
                        lambda: __import__("pathlib").Path("/nonexistent/store"))
    client = TestClient(create_app(web_dist_dir=None))
    resp = client.get("/api/fleet/channels")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sourceAvailable"] is False
    assert body["edges"] == []
    assert [n["pid"] for n in body["nodes"]] == [7]
    assert body["nodes"][0]["enrolled"] is False


def test_route_is_registered_before_project_wildcards():
    from set_orch.api import router

    paths = [(i, r.path) for i, r in enumerate(router.routes)]
    fleet = [i for i, p in paths if p == "/api/fleet/channels"]
    wildcards = [i for i, p in paths if "{project" in p and not p.startswith("/api/fleet")]
    assert fleet and wildcards
    assert max(fleet) < min(wildcards)
