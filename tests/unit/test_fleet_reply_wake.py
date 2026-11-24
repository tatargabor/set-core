"""Waking the asker once when its request is answered — fleet-reply-wake (B-215 part 2).

The engagement store is the real file in a tmp dir; the inventory rows, the clock and the
typing are injected.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from set_orch.fleet import takeover as tk
from set_orch.fleet.engagement import EngagementStore

NOW = 1_800_000_000.0
ASKER = "itline-ai-plus#a03eae5f"


def iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


@pytest.fixture
def store(tmp_path):
    return EngagementStore(str(tmp_path / "fleet-engagements.json"), clock=lambda: NOW)


def answered(store, *, reply_age=60.0, asker=ASKER):
    rec = store.open(asker=asker, project="aiplus-kereso")
    store.mark_sent(rec["id"], room="dm-a--b", ts=iso(NOW - 600))
    store._transition(rec["id"], ("resolving",), state="open")
    store.mark_answered(rec["id"], iso(NOW - reply_age))
    return rec["id"]


def row(**over):
    base = {"seat": ASKER, "session_id": "a03eae5f-1111", "population": "started-here",
            "terminal_label": "itline-ai-plus-desk", "runtime_status": "idle", "state": "quiet",
            "last_movement_seconds": 400.0, "last_human_input_seconds": 3600.0}
    base.update(over)
    return base


def run(store, rows, **kw):
    typed = []
    out = tk.wake_askers(store, rows, type_line=lambda label, line: typed.append((label, line)),
                         clock=lambda: NOW, **kw)
    return out, typed


def test_an_idle_asker_is_woken_once(store):
    """AC-1."""
    eid = answered(store)
    out, typed = run(store, [row()])
    assert out == [{"id": eid, "wake": "woken"}] and len(typed) == 1
    label, line = typed[0]
    assert label == "itline-ai-plus-desk" and "dm-a--b" in line and "answered" in line
    assert store.get(eid)["asker_wake"] == "woken"
    assert run(store, [row()]) == ([], []), "a reply wakes at most once"


def test_an_asker_that_moved_since_the_reply_is_left_alone(store):
    """AC-2: it moved 10 s ago; the reply is 60 s old."""
    eid = answered(store)
    out, typed = run(store, [row(last_movement_seconds=10.0)])
    assert typed == [] and store.get(eid)["asker_wake"] == "moved"


def test_movement_within_the_slack_is_not_moving_on(store):
    """The stop hook's own write right after the reply does not count as moving on."""
    eid = answered(store, reply_age=60.0)
    out, typed = run(store, [row(last_movement_seconds=45.0)])
    assert len(typed) == 1 and store.get(eid)["asker_wake"] == "woken"


def test_a_working_asker_is_looked_at_again(store):
    """AC-3: busy is not recorded."""
    eid = answered(store)
    out, typed = run(store, [row(runtime_status="busy", state="working")])
    assert typed == [] and store.get(eid)["asker_wake"] is None
    out, typed = run(store, [row()])
    assert len(typed) == 1


@pytest.mark.parametrize("over,off,outcome", [
    ({"last_human_input_seconds": 30.0}, False, "operator-present"),
    ({}, True, "off-here"),
    ({"population": "foreign", "terminal_label": None}, False, "not-fleet-held"),
    ({"state": "asking", "runtime_status": "waiting"}, False, None),
])
def test_what_stops_a_wake(store, over, off, outcome):
    """AC-4, AC-5; an asker with an open question is busy (not recorded)."""
    eid = answered(store)
    out, typed = run(store, [row(**over)], off_here=lambda label: off)
    assert typed == [] and store.get(eid)["asker_wake"] == outcome


def test_a_gone_asker_and_an_old_reply(store):
    eid = answered(store)
    run(store, [row(seat="someone#else", session_id="zzzzzzzz")])
    assert store.get(eid)["asker_wake"] == "gone"
    old = answered(store, reply_age=3 * 3600.0)
    out, typed = run(store, [row()])
    assert typed == [] and store.get(old)["asker_wake"] == "too-old"


def test_the_asker_is_found_by_its_session_suffix_when_the_seat_is_not_on_the_row(store):
    eid = answered(store)
    out, typed = run(store, [row(seat=None)])
    assert len(typed) == 1 and store.get(eid)["asker_wake"] == "woken"


def test_the_line_carries_pointers_only(store):
    eid = answered(store)
    line = tk.wake_line(store.get(eid))
    assert set(line.split()) >= {"[fleet]", "dm-a--b"} and "\n" not in line


def test_typing_without_esc():
    writes = []
    client = type("C", (), {"write": lambda self, label, data: writes.append(data)})()
    tk.owner_type("lbl", "hello  world", client=client, sleep=lambda s: None)
    assert writes == [b"hello world", b"\r"]


def test_the_round_wakes_with_nothing_open(store, monkeypatch):
    """1.4: the round's early return for "nothing open" no longer skips the wake pass."""
    from set_orch.api import fleet_mandate as fm
    from set_orch.fleet import engagement as em
    answered(store)
    monkeypatch.setattr(em, "EngagementStore", lambda *a, **k: store)
    monkeypatch.setattr(fm, "_live_rows", lambda: [row()])
    typed = []
    real = tk.wake_askers
    monkeypatch.setattr(fm.fleet_takeover, "wake_askers",
                        lambda s, rows, off_here: real(s, rows, off_here=off_here, clock=lambda: NOW,
                                                       type_line=lambda l, line: typed.append(l)))
    monkeypatch.setattr(fm, "_auto_answer_off_here", lambda label: False)
    out = fm.takeover_round()
    assert typed == ["itline-ai-plus-desk"] and out["wakes"][0]["wake"] == "woken" and out["open"] == 0
