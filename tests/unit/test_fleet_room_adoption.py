"""fleet-room-request-adoption: a request posted straight into a relation room is watched too.

Measured 2026-11-24 over three days of relation rooms: of 66 untracked project-addressed
requests, 21 got a linked reply, 36 an UNLINKED answer, and 8 nothing. Each test holds one
case of that, on a fake bus directory with the bus's own heading shapes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from set_orch.fleet import engagement as eng_mod
from set_orch.fleet import mandate_delivery
from set_orch.fleet import takeover as tk
from set_orch.fleet.desk import Desk
from set_orch.fleet.mandate import MandateStore

B = tk.Bounds(stall_seconds=300.0, ceiling_seconds=1800.0, cpu_percent=5.0, max_handovers=2)
TZ = timezone(timedelta(hours=1))
NOW_DT = datetime(2026, 11, 24, 14, 30, tzinfo=TZ)
NOW = NOW_DT.timestamp()
ROOM = "dm-alpha--beta"


def iso(seconds_ago: float) -> str:
    return (NOW_DT - timedelta(seconds=seconds_ago)).isoformat(timespec="milliseconds")


def post(root, room, seat, heading, body="text the record must never hold"):
    room_dir = root / "channels" / room
    room_dir.mkdir(parents=True, exist_ok=True)
    with open(room_dir / f"{seat}.md", "a", encoding="utf-8") as handle:
        handle.write(f"{heading}\n{body}\n\n")


def request(root, ago, *, to="", kind="REQUEST", room=ROOM, seat="alpha#aaaaaaaa"):
    ts = iso(ago)
    post(root, room, seat, f"## {ts} — {kind}" + (f" → {to}" if to else ""))
    return ts


def store(tmp_path, now=NOW):
    return eng_mod.EngagementStore(str(tmp_path / "state" / "e.json"), clock=lambda: now)


def adopt(tmp_path, s, *, since=NOW - 3600):
    return eng_mod.adopt_room_requests(s, store_root=tmp_path, since=since, now=NOW)


# -- adoption -----------------------------------------------------------------------------


def test_an_unaddressed_request_in_a_relation_room_is_adopted(tmp_path):
    ts = request(tmp_path, 120)
    s = store(tmp_path)
    ids = adopt(tmp_path, s)
    assert len(ids) == 1
    rec = s.get(ids[0])
    assert (rec["source"], rec["state"], rec["asker"], rec["project"], rec["room"], rec["ts"]) == \
        ("room", "open", "alpha#aaaaaaaa", "beta", ROOM, ts)
    assert rec["desk_seat"] is None and rec["handovers"] == 0
    assert abs(rec["sent_at"] - (NOW - 120)) < 1
    # A pointer, never a copy: no field holds the entry's text.
    assert "never hold" not in repr(rec)


def test_a_request_addressed_to_the_project_by_name_is_adopted(tmp_path):
    request(tmp_path, 120, to="beta")
    assert len(adopt(tmp_path, store(tmp_path))) == 1


def test_the_addressed_project_is_the_other_side_of_the_room(tmp_path):
    request(tmp_path, 120, seat="beta#bbbbbbbb")
    s = store(tmp_path)
    assert s.get(adopt(tmp_path, s)[0])["project"] == "alpha"


def test_a_tracked_request_is_not_adopted_twice(tmp_path):
    ts = request(tmp_path, 120)
    s = store(tmp_path)
    asked = s.open(asker="alpha#aaaaaaaa", project="beta")
    s.mark_sent(asked["id"], room=ROOM, ts=ts)
    assert adopt(tmp_path, s) == []
    request(tmp_path, 200)
    assert len(adopt(tmp_path, s)) == 1
    assert adopt(tmp_path, s) == []        # a second round adopts nothing new


def test_a_request_to_one_session_is_not_adopted(tmp_path):
    request(tmp_path, 120, to="beta#bbbbbbbb")
    assert adopt(tmp_path, store(tmp_path)) == []


def test_a_request_older_than_adoption_is_not_adopted(tmp_path):
    request(tmp_path, 7200)
    assert adopt(tmp_path, store(tmp_path), since=NOW - 3600) == []


def test_a_request_older_than_a_day_is_not_adopted_even_after_the_watermark(tmp_path):
    request(tmp_path, 25 * 3600)
    assert adopt(tmp_path, store(tmp_path), since=NOW - 30 * 24 * 3600) == []


def test_a_fresh_request_waits_a_round_for_set_fleet_ask_to_record_it(tmp_path):
    request(tmp_path, 30)
    assert adopt(tmp_path, store(tmp_path)) == []


def test_other_rooms_and_other_entry_types_are_not_adopted(tmp_path):
    request(tmp_path, 120, room="beta")                         # a project room
    request(tmp_path, 120, room="dm-beta-1234-alpha-5678")     # a room of two sessions
    request(tmp_path, 120, kind="FACT")
    request(tmp_path, 120, seat="gamma#cccccccc")               # not a party of the room
    assert adopt(tmp_path, store(tmp_path)) == []


def test_a_question_is_adopted_as_a_question(tmp_path):
    request(tmp_path, 120, kind="QUESTION")
    s = store(tmp_path)
    assert s.get(adopt(tmp_path, s)[0])["kind"] == "QUESTION"


def test_the_watermark_is_created_once_and_then_kept(tmp_path):
    path = str(tmp_path / "adopt.json")
    first = eng_mod.adoption_since(path=path, now=1000.0)
    assert first == 1000.0
    assert eng_mod.adoption_since(path=path, now=2000.0) == 1000.0


def test_on_first_use_nothing_already_posted_is_adopted(tmp_path):
    """Forward only: switching adoption on must not start desks for yesterday's requests."""
    request(tmp_path, 600)
    s = store(tmp_path)
    assert eng_mod.adopt_room_requests(s, store_root=tmp_path, now=NOW) == []


# -- closure ------------------------------------------------------------------------------


def _adopted(tmp_path, ago=900):
    ts = request(tmp_path, ago)
    s = store(tmp_path)
    return s, adopt(tmp_path, s)[0], ts


def test_an_unlinked_answer_closes_an_adopted_request(tmp_path):
    s, eid, ts = _adopted(tmp_path)
    answer = iso(60)
    post(tmp_path, ROOM, "beta#bbbbbbbb", f"## {answer} — ANSWER")
    out = eng_mod.refresh(s, store_root=tmp_path)
    assert out["answered"] == [eid]
    assert s.get(eid)["state"] == "answered" and s.get(eid)["answer_ts"] == answer


def test_a_linked_reply_closes_an_adopted_request(tmp_path):
    s, eid, ts = _adopted(tmp_path)
    post(tmp_path, ROOM, "beta#bbbbbbbb", f"## {iso(60)} — ANSWER → alpha#aaaaaaaa (re: {ts})")
    eng_mod.refresh(s, store_root=tmp_path)
    assert s.get(eid)["state"] == "answered"


def test_an_answer_to_another_request_does_not_close_it(tmp_path):
    s, eid, ts = _adopted(tmp_path)
    post(tmp_path, ROOM, "beta#bbbbbbbb", f"## {iso(60)} — ANSWER (re: {iso(5000)})")
    post(tmp_path, ROOM, "beta#bbbbbbbb", f"## {iso(50)} — FACT")
    eng_mod.refresh(s, store_root=tmp_path)
    assert s.get(eid)["state"] == "open"


def test_an_unlinked_answer_before_the_request_does_not_close_it(tmp_path):
    post(tmp_path, ROOM, "beta#bbbbbbbb", f"## {iso(2000)} — ANSWER")
    s, eid, ts = _adopted(tmp_path)
    eng_mod.refresh(s, store_root=tmp_path)
    assert s.get(eid)["state"] == "open"


def test_an_answer_by_the_asking_side_does_not_close_it(tmp_path):
    s, eid, ts = _adopted(tmp_path)
    post(tmp_path, ROOM, "alpha#a2a2a2a2", f"## {iso(60)} — ANSWER")
    eng_mod.refresh(s, store_root=tmp_path)
    assert s.get(eid)["state"] == "open"


def test_an_asked_engagement_still_needs_a_linked_reply(tmp_path):
    ts = request(tmp_path, 900)
    s = store(tmp_path)
    asked = s.open(asker="alpha#aaaaaaaa", project="beta")
    s.mark_sent(asked["id"], room=ROOM, ts=ts)
    post(tmp_path, ROOM, "beta#bbbbbbbb", f"## {iso(60)} — ANSWER")
    eng_mod.refresh(s, store_root=tmp_path)
    assert s.get(asked["id"])["state"] == "open"


# -- claiming -----------------------------------------------------------------------------


class Fakes:
    def __init__(self, tmp_path, ago=120):
        self.now = NOW
        self.engagements = store(tmp_path)
        self.mandates = MandateStore(str(tmp_path / "m.json"))
        self.starts, self.interrupts = [], []
        request(tmp_path, ago)
        self.eid = adopt(tmp_path, self.engagements)[0]

    def watch(self, rows, seen=lambda room, ts, asker, seats: None):
        def start_desk(project, *, requested_by, takeover):
            self.starts.append((project, requested_by, takeover))
            made = self.mandates.create(kind="desk", goal="Answer requests", project=project, cwd="/x",
                                        label="beta-desk", takeover=takeover)
            return Desk(project=project, label="beta-desk", seat="beta#0000eeee",
                        mandate_id=made["id"], started=True)

        return tk.TakeoverWatch(
            engagements=self.engagements, mandates=self.mandates, rows=rows,
            cpu=lambda unit, pid: None, interrupt=lambda label, line: self.interrupts.append(label),
            stop=lambda label: None, start_desk=start_desk, b=B, clock=lambda: self.now, seen=seen)


def desk_row(project="beta", **over):
    row = {"terminal_label": f"{project}-desk", "seat": f"{project}#0000dddd", "pid": 1, "unit": None,
           "state": "working", "last_movement_seconds": 5.0,
           "mandate": {"id": "m-live", "kind": "desk", "project": project, "ended": None}}
    row.update(over)
    return row


def test_an_unclaimed_request_gets_the_project_s_live_desk(tmp_path):
    f = Fakes(tmp_path)
    out = f.watch([desk_row("alpha"), desk_row()]).run()
    assert out[0]["decision"] == tk.ASSIGN
    rec = f.engagements.get(f.eid)
    assert (rec["desk_label"], rec["desk_seat"], rec["desk_mandate"], rec["handovers"]) == \
        ("beta-desk", "beta#0000dddd", "m-live", 0)
    assert f.starts == [] and f.interrupts == []


def test_an_ordinary_session_is_not_taken_for_the_desk(tmp_path):
    f = Fakes(tmp_path)
    plain = desk_row(mandate={"id": "m-work", "kind": "work", "project": "beta", "ended": None})
    out = f.watch([plain]).run()
    assert out[0]["decision"] == tk.NONE and f.engagements.get(f.eid)["desk_seat"] is None


def test_without_a_desk_nothing_starts_within_the_grace(tmp_path):
    f = Fakes(tmp_path)
    out = f.watch([]).run()
    assert out[0] == {**out[0], "decision": tk.NONE, "why": "unclaimed-grace"}
    assert f.starts == []


def test_without_a_desk_one_starts_after_the_grace(tmp_path):
    f = Fakes(tmp_path)
    f.now = NOW + 300
    out = f.watch([]).run()
    assert out[0]["decision"] == tk.START
    project, requested_by, takeover = f.starts[0]
    assert (project, requested_by) == ("beta", "alpha#aaaaaaaa")
    assert takeover["from_seat"] is None and takeover["from_session"] is None
    assert takeover["engagement_id"] == f.eid and takeover["room"] == ROOM
    rec = f.engagements.get(f.eid)
    assert rec["desk_seat"] == "beta#0000eeee" and rec["handovers"] == 0 and rec["state"] == "open"


def test_once_claimed_the_ordinary_ladder_applies(tmp_path):
    f = Fakes(tmp_path)
    f.watch([desk_row()]).run()
    f.now = NOW + 400
    out = f.watch([desk_row(state="quiet", last_movement_seconds=1000.0)]).run()
    assert out[0]["decision"] == tk.INTERRUPT and f.interrupts == ["beta-desk"]


def test_the_unclaimed_desk_is_told_nobody_picked_the_request_up(tmp_path):
    f = Fakes(tmp_path)
    f.now = NOW + 300
    f.watch([]).run()
    text = mandate_delivery.render_context(f.mandates.get(f.engagements.get(f.eid)["desk_mandate"]))
    assert "Nobody picked this request up" in text
    assert "is now held by you" in text
    assert "stalled or stopped" not in text and "transcript" not in text


def test_a_takeover_desk_is_still_told_about_its_predecessor(tmp_path):
    lines = "\n".join(mandate_delivery._takeover_lines(
        {"room": ROOM, "ts": "t", "asker": "alpha#aaaaaaaa", "from_seat": "beta#0000dddd",
         "from_session": "s-1"}))
    assert "stalled or stopped" in lines and "moved from beta#0000dddd to you" in lines
    assert "Nobody picked" not in lines


# -- a request a live session has already read --------------------------------------------


def _cursors(root, data):
    import json
    (root / "cursors.json").write_text(json.dumps(data), encoding="utf-8")


def test_seen_by_reads_the_bus_cursor_of_a_live_seat(tmp_path):
    ts = iso(600)
    _cursors(tmp_path, {f"{ROOM}::beta#bbbbbbbb": {"alpha#aaaaaaaa": ts},
                        f"{ROOM}::beta#cccccccc": {"alpha#aaaaaaaa": iso(900)}})
    seats = ["beta#cccccccc", "beta#bbbbbbbb"]
    assert eng_mod.seen_by(ROOM, ts, "alpha#aaaaaaaa", seats, store_root=tmp_path) == "beta#bbbbbbbb"
    assert eng_mod.seen_by(ROOM, ts, "alpha#aaaaaaaa", ["beta#cccccccc"], store_root=tmp_path) is None
    assert eng_mod.seen_by(ROOM, ts, "alpha#zzzzzzzz", seats, store_root=tmp_path) is None


def test_unreadable_cursors_count_as_unseen(tmp_path):
    (tmp_path / "cursors.json").write_text("{not json", encoding="utf-8")
    assert eng_mod.seen_by(ROOM, iso(60), "alpha#aaaaaaaa", ["beta#bbbbbbbb"], store_root=tmp_path) is None
    assert eng_mod.seen_by(ROOM, iso(60), "alpha#aaaaaaaa", ["beta#bbbbbbbb"],
                           store_root=tmp_path / "missing") is None


def test_no_desk_starts_for_a_request_a_live_session_has_read(tmp_path):
    """Measured: 81 of 108 answered room requests took more than five minutes."""
    f = Fakes(tmp_path)
    f.now = NOW + 300
    asked = []

    def seen(room, ts, asker, seats):
        asked.append(seats)
        return "beta#bbbbbbbb"

    plain = {"terminal_label": "beta-2", "seat": "beta#bbbbbbbb", "mandate": None}
    other = {"terminal_label": "gamma-1", "seat": "gamma#cccccccc", "mandate": None}
    out = f.watch([plain, other], seen=seen).run()
    assert out[0]["decision"] == tk.NONE and out[0]["why"] == "read-by-a-live-session"
    assert f.starts == [] and asked == [["beta#bbbbbbbb"]]


def test_the_desk_that_answered_first_is_still_recorded(tmp_path):
    """Measured live: the started desk answered before the round recorded it."""
    f = Fakes(tmp_path)
    f.now = NOW + 300
    w = f.watch([])
    real_start = w.start_desk

    def start_and_answer(project, *, requested_by, takeover):
        desk = real_start(project, requested_by=requested_by, takeover=takeover)
        f.engagements.mark_answered(f.eid, iso(1))
        return desk

    w.start_desk = start_and_answer
    w.run()
    rec = f.engagements.get(f.eid)
    assert rec["state"] == "answered" and rec["desk_seat"] == "beta#0000eeee"
