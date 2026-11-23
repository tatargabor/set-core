"""The engagement record: who asked which project for what, and whether it was answered.

The fixtures for the bus are built from the bus's own writer output (measurements.md M5):
the sender is the file name, a reply carries `(re: <ts>)` and may carry no addressee.
"""

from __future__ import annotations

import json
import logging

import pytest

from set_orch.fleet import engagement
from set_orch.fleet.engagement import BusUnreadable, EngagementError, EngagementStore

MARKER = "ZZ-BODY-MARKER-ZZ"
REQ_TS = "2026-11-23T19:12:21.902+01:00"
ANS_TS = "2026-11-23T19:12:22.005+01:00"


@pytest.fixture
def store(tmp_path):
    return EngagementStore(str(tmp_path / "state" / "fleet-engagements.json"))


def _bus(tmp_path, entries):
    """Write a bus store: {room: {seat: [(heading, body), …]}} → the store root."""
    root = tmp_path / "bus"
    for room, seats in entries.items():
        d = root / "channels" / room
        d.mkdir(parents=True, exist_ok=True)
        for seat, items in seats.items():
            text = "".join(f"{heading}\n{body}\n\n" for heading, body in items)
            (d / f"{seat}.md").write_text(text, encoding="utf-8")
    return root


def _opened(store, **over):
    args = dict(asker="alpha#aaaaaaaa", project="beta", kind="REQUEST", subject="the export format",
                limit=5)
    args.update(over)
    return store.open(**args)


def _sent(store, **over):
    rec = _opened(store, **over)
    return store.mark_sent(rec["id"], room="dm-alpha--beta", ts=REQ_TS)


# -- the record -----------------------------------------------------------------------


def test_an_engagement_stores_a_pointer_and_no_field_for_text(store):
    rec = _sent(store)
    stored = json.loads(open(store.path).read())["engagements"][rec["id"]]
    assert stored["room"] == "dm-alpha--beta" and stored["ts"] == REQ_TS
    assert stored["state"] == "open"
    # No field that could hold the request or a reply.
    assert not ({"text", "body", "request", "reply", "message", "content"} & set(stored))


def test_text_smuggled_into_the_record_is_dropped_on_read(store):
    rec = _sent(store)
    raw = json.loads(open(store.path).read())
    raw["engagements"][rec["id"]]["text"] = MARKER
    raw["engagements"][rec["id"]]["body"] = MARKER
    open(store.path, "w").write(json.dumps(raw))
    again = store.get(rec["id"])
    assert MARKER not in json.dumps(again)


def test_the_subject_is_short_and_single_line(store):
    rec = _opened(store, subject="a\nvery " + "long " * 40 + "subject")
    assert "\n" not in rec["subject"] and len(rec["subject"]) <= engagement.SUBJECT_MAX


def test_the_store_is_owner_only(store):
    import os
    import stat

    _opened(store)
    assert stat.S_IMODE(os.stat(store.path).st_mode) == 0o600


# -- states ---------------------------------------------------------------------------


def test_sent_needs_the_pointer(store):
    rec = _opened(store)
    with pytest.raises(EngagementError):
        store.mark_sent(rec["id"], room="", ts=REQ_TS)
    assert store.get(rec["id"])["state"] == "resolving"


def test_a_failure_carries_a_class_and_only_a_known_one(store):
    rec = _opened(store)
    with pytest.raises(EngagementError):
        store.mark_failed(rec["id"], "the desk seemed busy")
    failed = store.mark_failed(rec["id"], "not-on-bus")
    assert failed["state"] == "failed" and failed["reason"] == "not-on-bus"


def test_a_late_report_does_not_reopen_a_decided_engagement(store):
    rec = _opened(store)
    store.mark_failed(rec["id"], "desk-not-ready")
    after = store.mark_sent(rec["id"], room="dm-alpha--beta", ts=REQ_TS)
    assert after["state"] == "failed"
    assert store.get(rec["id"])["room"] is None


def test_only_an_open_engagement_can_be_answered(store):
    rec = _opened(store)
    assert store.mark_answered(rec["id"], ANS_TS)["state"] == "resolving"


# -- the bound ------------------------------------------------------------------------


def test_one_request_too_many_is_refused_with_the_open_list(store):
    made = [_opened(store, limit=2) for _ in range(2)]
    with pytest.raises(EngagementError) as err:
        _opened(store, limit=2)
    assert err.value.kind == "bound"
    assert [r["id"] for r in err.value.open] == [r["id"] for r in made]
    assert len(store.all()) == 2


def test_closed_engagements_do_not_count_against_the_bound(store):
    a = _opened(store, limit=2)
    b = _sent(store, limit=2)
    store.mark_failed(a["id"], "not-on-bus")
    store.mark_answered(b["id"], ANS_TS)
    assert _opened(store, limit=2)["state"] == "resolving"
    assert _opened(store, limit=2)["state"] == "resolving"


def test_the_bound_is_per_asker(store):
    _opened(store, limit=1)
    assert _opened(store, asker="gamma#cccccccc", limit=1)["state"] == "resolving"


def test_live_for_desk_counts_resolving_and_open_only(store):
    a = _opened(store)
    b = _sent(store)
    c = _sent(store)
    store.mark_answered(c["id"], ANS_TS)
    _opened(store, project="other")
    assert store.live_for_desk("beta") == 2
    store.withdraw(a["id"])
    store.withdraw(b["id"])
    assert store.live_for_desk("beta") == 0


# -- closure from the bus -------------------------------------------------------------


def test_a_linked_reply_from_the_addressed_project_answers(tmp_path, store):
    root = _bus(tmp_path, {"dm-alpha--beta": {
        "alpha#aaaaaaaa": [(f"## {REQ_TS} — REQUEST → beta", "please")],
        "beta#bbbbbbbb": [(f"## {ANS_TS} — ANSWER (re: {REQ_TS})", "done")],
    }})
    rec = _sent(store)
    out = engagement.refresh(store, store_root=root)
    assert out == {"measured": True, "answered": [rec["id"]], "unreadable": []}
    after = store.get(rec["id"])
    assert after["state"] == "answered" and after["answer_ts"] == ANS_TS


def test_an_unlinked_entry_from_the_project_does_not_answer(tmp_path, store):
    root = _bus(tmp_path, {"dm-alpha--beta": {
        "alpha#aaaaaaaa": [(f"## {REQ_TS} — REQUEST → beta", "please")],
        "beta#bbbbbbbb": [("## 2026-11-23T19:12:22.090+01:00 — FACT", "something else"),
                          ("## 2026-11-23T19:13:00.000+01:00 — ANSWER → alpha#aaaaaaaa", "unlinked")],
    }})
    rec = _sent(store)
    assert engagement.refresh(store, store_root=root)["answered"] == []
    assert store.get(rec["id"])["state"] == "open"


def test_a_linked_entry_from_another_project_does_not_answer(tmp_path, store):
    root = _bus(tmp_path, {"dm-alpha--beta": {
        "gamma#cccccccc": [(f"## {ANS_TS} — ANSWER (re: {REQ_TS})", "not mine to answer")],
        # A project whose NAME merely starts with the addressed one is another project.
        "beta-tools#dddddddd": [(f"## {ANS_TS} — ANSWER (re: {REQ_TS})", "nor mine")],
        # The asker replying to its own request is not an answer either.
        "alpha#aaaaaaaa": [(f"## {REQ_TS} — REQUEST → beta", "please"),
                           (f"## {ANS_TS} — FACT (re: {REQ_TS})", "any news?")],
    }})
    rec = _sent(store)
    assert engagement.refresh(store, store_root=root)["answered"] == []
    assert store.get(rec["id"])["state"] == "open"


def test_a_reply_from_the_project_on_another_machine_answers(tmp_path, store):
    root = _bus(tmp_path, {"dm-alpha--beta": {
        "beta@macmini#eeeeeeee": [(f"## {ANS_TS} — ANSWER (re: {REQ_TS})", "done")],
    }})
    rec = _sent(store)
    assert engagement.refresh(store, store_root=root)["answered"] == [rec["id"]]


def test_a_link_quoted_in_a_body_is_not_a_reply(tmp_path, store):
    root = _bus(tmp_path, {"dm-alpha--beta": {
        "beta#bbbbbbbb": [("## 2026-11-23T19:14:00.000+01:00 — FACT",
                           f"I saw an entry that said (re: {REQ_TS}) somewhere\n"
                           f"quote: ## {ANS_TS} — ANSWER (re: {REQ_TS}) and more words")],
    }})
    rec = _sent(store)
    assert engagement.refresh(store, store_root=root)["answered"] == []
    assert store.get(rec["id"])["state"] == "open"


def test_the_earliest_linked_reply_is_recorded(tmp_path, store):
    later = "2026-11-23T19:20:00.000+01:00"
    root = _bus(tmp_path, {"dm-alpha--beta": {
        "beta#bbbbbbbb": [(f"## {later} — ANSWER (re: {REQ_TS})", "again")],
        "beta#ffffffff": [(f"## {ANS_TS} — ANSWER (re: {REQ_TS})", "first")],
    }})
    assert engagement.linked_reply("dm-alpha--beta", REQ_TS, "beta", store_root=root) == ANS_TS


def test_a_room_that_cannot_be_read_is_unmeasured_and_not_open(tmp_path, store):
    root = tmp_path / "bus"  # no channels directory at all
    rec = _sent(store)
    with pytest.raises(BusUnreadable):
        engagement.linked_reply("dm-alpha--beta", REQ_TS, "beta", store_root=root)
    out = engagement.refresh(store, store_root=root)
    assert out["measured"] is False and out["unreadable"] == [rec["id"]]
    shown = engagement.view(store.get(rec["id"]), now=10**12, waiting_after=60, unmeasured=True)
    assert shown["state"] == "unmeasured" and shown["waiting"] is False
    assert shown["stored_state"] == "open"


def test_body_text_reaches_no_payload_and_no_log(tmp_path, store, caplog):
    caplog.set_level(logging.DEBUG)
    root = _bus(tmp_path, {"dm-alpha--beta": {
        "alpha#aaaaaaaa": [(f"## {REQ_TS} — REQUEST → beta", f"secret {MARKER} request")],
        "beta#bbbbbbbb": [(f"## {ANS_TS} — ANSWER (re: {REQ_TS})", f"secret {MARKER} reply")],
    }})
    rec = _sent(store, subject="export format")
    out = engagement.refresh(store, store_root=root)
    after = store.get(rec["id"])
    shown = engagement.view(after, now=after["opened_at"] + 5, waiting_after=60)
    assert after["state"] == "answered"
    for blob in (json.dumps(out), json.dumps(after), json.dumps(shown), open(store.path).read()):
        assert MARKER not in blob
    assert caplog.records, "nothing was logged, so this would prove nothing"
    for record in caplog.records:
        assert MARKER not in record.getMessage()


# -- waiting --------------------------------------------------------------------------


def test_an_engagement_open_past_the_bound_is_waiting_and_still_open(store):
    rec = _sent(store)
    opened = rec["opened_at"]
    fresh = engagement.view(rec, now=opened + 59, waiting_after=60)
    late = engagement.view(rec, now=opened + 61, waiting_after=60)
    assert fresh["waiting"] is False
    assert late["waiting"] is True and late["state"] == "open" and late["age_seconds"] == 61.0
    assert store.get(rec["id"])["state"] == "open"


def test_only_an_open_engagement_waits(store):
    rec = _opened(store)
    old = rec["opened_at"] + 10_000
    assert engagement.view(rec, now=old, waiting_after=60)["waiting"] is False
    failed = store.mark_failed(rec["id"], "not-on-bus")
    assert engagement.view(failed, now=old, waiting_after=60)["waiting"] is False


# -- listing --------------------------------------------------------------------------


def test_listing_filters_by_asker_project_and_state(store):
    a = _sent(store)
    b = _opened(store, project="gamma")
    c = _opened(store, asker="delta#dddddddd")
    assert [r["id"] for r in store.list(asker="alpha#aaaaaaaa")] == [a["id"], b["id"]]
    assert [r["id"] for r in store.list(project="gamma")] == [b["id"]]
    assert [r["id"] for r in store.list(state="open")] == [a["id"]]
    assert [r["id"] for r in store.list(asker="delta#dddddddd", state="resolving")] == [c["id"]]
