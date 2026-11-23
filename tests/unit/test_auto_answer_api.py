"""The fleet's automatic-answer routes (fleet-auto-answer, task 4.1).

Driven through the route functions with the real state layout in a tmp tree: the machine
config (`SET_CONFIG_DIR`), the relay's state (`SET_QUESTION_RELAY_DIR`) and the decision
log (`XDG_DATA_HOME`) — the same three places the worker and the hook use.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from set_orch.fleet import auto_answer as aa
from set_orch.fleet import auto_answer_worker as aw
from set_orch.fleet import question_relay as qr

CID = "relay-47f1763f-0123456789ab"
SID = "47f1763f-c5c5-4f3a-9aae-850d27d41dae"


@pytest.fixture
def world(tmp_path, monkeypatch):
    for var, sub in (("SET_CONFIG_DIR", "cfg"), ("SET_QUESTION_RELAY_DIR", "state"), ("XDG_DATA_HOME", "data")):
        (tmp_path / sub).mkdir()
        monkeypatch.setenv(var, str(tmp_path / sub))
    for key in (aa.KEY_ENABLED, qr.KEY_COMMAND):
        monkeypatch.delenv(aa.local_config.env_key(key), raising=False)
    monkeypatch.setattr(qr, "_hook_alive", lambda pid: True)
    return tmp_path


def propose(base, write_at, state="proposed", outcome="allowed"):
    aw._private_write(aw.pending_path(base, CID), {
        "id": CID, "session_id": SID, "kind": "ask", "source": "proj · 47f1763f", "project": "proj",
        "created": write_at - 60, "write_at": write_at, "state": state, "cancelled": False,
        "questions": [{"key": "Q1", "question": "Which colour?", "options": ["TEAL", "ORANGE"],
                       "outcome": outcome, "choice": "TEAL", "tier": "decided", "confidence": 0.9,
                       "references": [{"kind": "operator", "quote": "TEAL it is, always", "checked": True},
                                      {"kind": "file", "path": "x.md", "quote": "made up", "checked": False}]}]})


def test_switch_round_trip_and_wiring(world):
    from set_orch.api import fleet as api
    s = api.fleet_auto_answer()
    assert s["enabled"] is False and s["wired"] is False and s["pending_count"] == 0
    s = api.fleet_auto_answer_toggle(api.AutoAnswerToggleBody(enabled=True))
    assert s["enabled"] is True
    assert aa.enabled(), "the switch is the machine config every decision reads"
    aa.local_config.set_value(qr.KEY_COMMAND, "set-auto-answer")
    assert api.fleet_auto_answer()["wired"] is True
    aa.local_config.set_value(qr.KEY_COMMAND, "/opt/x/bin/set-auto-answer --flag")
    assert api.fleet_auto_answer()["wired"] is True
    aa.local_config.set_value(qr.KEY_COMMAND, "bridge be --json -")
    assert api.fleet_auto_answer()["wired"] is False
    assert api.fleet_auto_answer_toggle(api.AutoAnswerToggleBody(enabled=False))["enabled"] is False


def test_pending_proposal_is_listed_with_checked_references_only(world):
    """AC-20's data: the count, and what the panel shows for each pending proposal."""
    from set_orch.api import fleet as api
    propose(world / "state", time.time() + 42)
    s = api.fleet_auto_answer()
    assert s["pending_count"] == 1
    p = s["pending"][0]
    assert p["choice"] == "TEAL" and p["tier"] == "decided" and p["agent"] == "proj · 47f1763f"
    assert 40 <= p["seconds_left"] <= 42.5
    assert [r["quote"] for r in p["references"]] == ["TEAL it is, always"]


def test_forwarded_and_cancelled_records_are_not_pending(world):
    from set_orch.api import fleet as api
    propose(world / "state", time.time() + 42, state="forwarded", outcome="excluded")
    assert api.fleet_auto_answer()["pending_count"] == 0


def test_cancel_route(world):
    """AC-18 at the route: the record is marked, a second cancel is a 404."""
    from fastapi import HTTPException
    from set_orch.api import fleet as api
    propose(world / "state", time.time() + 42)
    s = api.fleet_auto_answer_cancel(CID)
    assert s["pending_count"] == 0 and aw.read_pending(world / "state", CID)["cancelled"] is True
    with pytest.raises(HTTPException) as exc:
        api.fleet_auto_answer_cancel("relay-nope")
    assert exc.value.status_code == 404


def test_decisions_route_reads_newest_first_without_caching(world):
    from set_orch.api import fleet as api
    aw.append_log([{"ts": time.time(), "id": "a"}, {"ts": time.time(), "id": "b"}])
    assert [d["id"] for d in api.fleet_auto_answer_decisions(limit=10)["decisions"]] == ["b", "a"]
    aw.append_log([{"ts": time.time(), "id": "c"}])
    assert [d["id"] for d in api.fleet_auto_answer_decisions(limit=2)["decisions"]] == ["c", "b"]


def test_the_waiting_listing_carries_the_proposal(world):
    from set_orch.api import fleet as api
    base = world / "state"
    qr._write_json(qr.waiting_path(SID, base), {"session_id": SID, "id": CID, "project": "proj", "questions": 1,
                                                 "target": "command", "started": time.time(), "pid": os.getpid()})
    propose(base, time.time() + 30)
    row = next(w for w in api.fleet_question_relay()["waiting"] if w["session_id"] == SID)
    assert row["auto_answer"]["choice"] == "TEAL" and row["auto_answer"]["tier"] == "decided"
    assert 0 < row["auto_answer"]["seconds_left"] <= 30
    aw.pending_path(base, CID).unlink()
    row = next(w for w in api.fleet_question_relay()["waiting"] if w["session_id"] == SID)
    assert row["auto_answer"] is None
