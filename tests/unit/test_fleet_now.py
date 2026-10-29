"""The Now card's state, merge, focus filter and cue decision (fleet-now-card 1.1–1.4).

Each test names the scenario it holds. The functions under test are pure over a
state dict, so no clock, server or file is involved except where the store itself
is the subject.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.fleet import now as now_mod  # noqa: E402

NOW = 1_800_000_000.0
CFG = {**{k: v for k, v in now_mod.CONFIG_DEFAULTS.items()},
       "now.focus_threshold_minutes": 60.0, "now.offplan_nudge_minutes": 45.0,
       "now.cue_min_interval_minutes": 10.0, "now.cue_backoff_after": 3.0,
       "now.deadline_window_hours": 24.0, "now.stale_ranking_hours": 2.0,
       "now.wind_down_hour": 21.0}


def oq(id_, project="p1", **extra):
    return {"source": "owner-queue", "id": id_, "project": project,
            "sentence": f"S-{id_}", "why": f"W-{id_}", **extra}


def fw(id_, since, project="p1", source="agent-questions"):
    return {"source": source, "id": id_, "project": project, "since": since}


# --------------------------------------------------------------------------- #
# 1.1 the state store
# --------------------------------------------------------------------------- #

def test_state_round_trips_atomically_and_holds_only_ids(tmp_path):
    path = tmp_path / "now" / "state.json"
    state = now_mod.load_state(NOW, path)
    now_mod.snooze(state, "item-1", NOW + 3600)
    now_mod.dismiss(state, "agent:abc", NOW)
    now_mod.count_closed(state)
    now_mod.set_focus(state, ["p1", "p2"], NOW)
    now_mod.save_state(state, path)

    assert not (tmp_path / "now" / "state.json.tmp").exists(), "the temp file must be renamed away"
    again = now_mod.load_state(NOW, path)
    assert again["snoozes"] == {"item-1": NOW + 3600}
    assert "agent:abc" in again["dismissed"]
    assert again["closedToday"] == 1
    assert again["focus"] == ["p1", "p2"]


def test_a_corrupt_state_file_starts_fresh_rather_than_raising(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json")
    state = now_mod.load_state(NOW, path)
    assert state["closedToday"] == 0 and state["snoozes"] == {}


def test_a_new_day_resets_the_closed_count_and_drops_expired_snoozes():
    state = now_mod.empty_state(NOW)
    state["closedToday"] = 5
    state["snoozes"] = {"gone": NOW - 1, "kept": NOW + 999_999}
    later = NOW + 24 * 3600
    now_mod.roll_day(state, later)
    assert state["closedToday"] == 0
    assert state["snoozes"] == {"kept": NOW + 999_999}


def test_state_dir_honours_the_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SET_NOW_DIR", str(tmp_path / "x"))
    assert now_mod.state_path() == tmp_path / "x" / "state.json"


# --------------------------------------------------------------------------- #
# 1.2 merge
# --------------------------------------------------------------------------- #

def test_owner_queue_rank_first_then_framework_oldest_first():
    owner = [oq("b"), oq("a")]
    framework = [fw("f-new", NOW - 10), fw("f-old", NOW - 1000)]
    merged = now_mod.merge(owner, framework, now_mod.empty_state(NOW), NOW)
    assert [i["id"] for i in merged] == ["b", "a", "f-old", "f-new"]


def test_ac4_a_referenced_framework_item_is_shown_once_in_the_owner_position():
    owner = [oq("x"), oq("y", references=[{"source": "agent-questions", "id": "agent:s1"}])]
    framework = [fw("agent:s1", NOW - 5000), fw("agent:s2", NOW - 10)]
    merged = now_mod.merge(owner, framework, now_mod.empty_state(NOW), NOW)
    assert [i["id"] for i in merged] == ["x", "y", "agent:s2"]


def test_a_reference_to_another_source_does_not_drop_a_same_id_item():
    owner = [oq("y", references=[{"source": "bus-owner", "id": "agent:s1"}])]
    framework = [fw("agent:s1", NOW - 5000, source="agent-questions")]
    merged = now_mod.merge(owner, framework, now_mod.empty_state(NOW), NOW)
    assert [i["id"] for i in merged] == ["y", "agent:s1"]


def test_ac5_without_an_owner_queue_framework_items_are_oldest_first():
    framework = [fw("b", NOW - 1), fw("a", NOW - 100), fw("c", "2020-01-01T00:00:00+00:00")]
    merged = now_mod.merge([], framework, now_mod.empty_state(NOW), NOW)
    assert [i["id"] for i in merged] == ["c", "a", "b"]


def test_ac11_a_snoozed_item_leaves_and_returns_after_its_time():
    state = now_mod.empty_state(NOW)
    now_mod.snooze(state, "a", NOW + 2 * 3600)
    owner = [oq("a"), oq("b")]
    assert [i["id"] for i in now_mod.merge(owner, [], state, NOW)] == ["b"]
    assert [i["id"] for i in now_mod.merge(owner, [], state, NOW + 2 * 3600 + 1)] == ["a", "b"]


# --------------------------------------------------------------------------- #
# 1.3 focus
# --------------------------------------------------------------------------- #

def test_non_focus_items_are_held_back_and_counted():
    items = [oq("1", "p1"), oq("2", "p2"), oq("3", "p3")]
    shown, held = now_mod.apply_focus(items, ["p2"], NOW, 3600)
    assert [i["id"] for i in shown] == ["2"]
    assert held == 2


def test_a_near_deadline_breaks_through_the_focus():
    soon = now_mod.utc_iso(NOW + 600)
    items = [oq("1", "p1", deadline=soon), oq("2", "p2")]
    shown, held = now_mod.apply_focus(items, ["p2"], NOW, 3600)
    assert [i["id"] for i in shown] == ["1", "2"]
    assert held == 0


def test_with_no_focus_item_everything_is_shown():
    items = [oq("1", "p1"), oq("2", "p3")]
    shown, held = now_mod.apply_focus(items, ["p9"], NOW, 3600)
    assert len(shown) == 2 and held == 0


def test_ac16_a_fourth_focus_project_is_refused_with_a_swap_question():
    state = now_mod.empty_state(NOW)
    assert now_mod.set_focus(state, ["a", "b", "c"], NOW)["ok"]
    out = now_mod.set_focus(state, ["a", "b", "c", "d"], NOW)
    assert out["ok"] is False and out["swap"] is True
    assert state["focus"] == ["a", "b", "c"]


def test_removing_a_focus_project_reports_it_as_removed():
    state = now_mod.empty_state(NOW)
    now_mod.set_focus(state, ["a", "b"], NOW)
    out = now_mod.set_focus(state, ["a"], NOW)
    assert out["removed"] == ["b"]


# --------------------------------------------------------------------------- #
# 1.4 cues
# --------------------------------------------------------------------------- #

def _cue(state, project, age, first, focus=(), now=NOW):
    return now_mod.decide_cue(state, inputs=[(project, age)], first=first, focus=focus,
                              now=now, cfg=CFG)


def test_ac13_leaving_a_project_plays_one_cue():
    state = now_mod.empty_state(NOW)
    assert _cue(state, "A", 5, oq("1"))["play"] is False      # first sight: no breakpoint
    d = _cue(state, "B", 2, oq("1"), now=NOW + 30)
    assert d["play"] is True and d["reason"] == "switch"
    assert d["variant"] is not None
    # Same first item, another switch: nothing new to say.
    assert _cue(state, "A", 1, oq("1"), now=NOW + 60 * 60)["play"] is False


def test_the_cue_tone_varies_between_cues():
    state = now_mod.empty_state(NOW)
    _cue(state, "A", 5, oq("1"))
    v1 = _cue(state, "B", 1, oq("1"), now=NOW + 10)["variant"]
    v2 = _cue(state, "A", 1, oq("2"), now=NOW + 10 + 700)["variant"]
    assert v1 is not None and v2 is not None and v1 != v2


def test_cues_respect_the_minimum_interval():
    state = now_mod.empty_state(NOW)
    _cue(state, "A", 5, oq("1"))
    assert _cue(state, "B", 1, oq("1"), now=NOW + 10)["play"]
    assert _cue(state, "A", 1, oq("2"), now=NOW + 20)["play"] is False


def test_ac14_no_cue_inside_a_long_block_in_a_focus_project():
    soon = now_mod.utc_iso(NOW + 4 * 3600)

    def run(block_minutes):
        state = now_mod.empty_state(NOW)
        # Continuous input in A, polled every 10 minutes, no deadline in sight.
        for minute in range(0, block_minutes, 10):
            _cue(state, "A", 1, oq("1"), focus=["A"], now=NOW + minute * 60)
        # Then a new first item arrives whose deadline is inside the window.
        return _cue(state, "A", 1, oq("2", deadline=soon), focus=["A"],
                    now=NOW + block_minutes * 60)

    short = run(20)
    assert short["play"] is True and short["reason"] == "deadline", "control: a short block cues"
    long = run(70)
    assert long["blockSeconds"] > 60 * 60
    assert long["play"] is False


def test_an_off_plan_block_nudges_once_a_day():
    state = now_mod.empty_state(NOW)
    played = []
    for minute in range(0, 120, 5):
        d = _cue(state, "X", 1, oq("1"), focus=["A"], now=NOW + minute * 60)
        if d["play"]:
            played.append(d["reason"])
    assert played == ["off-plan"]


def test_ac15_three_ignored_cues_double_the_interval_and_say_so():
    state = now_mod.empty_state(NOW)
    t = NOW
    _cue(state, "A", 1, oq("0"), now=t)
    projects = ["B", "A", "B"]
    for n, p in enumerate(projects, start=1):
        t += 11 * 60
        assert _cue(state, p, 1, oq(str(n)), now=t)["play"], f"cue {n} should play"
    t += 11 * 60
    d = _cue(state, "A", 1, oq("4"), now=t)
    assert d["slowed"] is True
    assert d["intervalSeconds"] == 2 * 10 * 60
    assert d["play"] is False, "11 minutes is under the doubled interval"


def test_an_action_resets_the_backoff():
    state = now_mod.empty_state(NOW)
    state["cue"]["factor"] = 4
    state["cue"]["unacted"] = 2
    state["cue"]["log"] = [{"at": NOW, "reason": "switch", "acted": False}]
    now_mod.mark_action(state)
    assert state["cue"]["factor"] == 1 and state["cue"]["unacted"] == 0
    assert state["cue"]["log"][-1]["acted"] is True


def test_the_cue_log_is_bounded():
    state = now_mod.empty_state(NOW)
    state["cue"]["log"] = [{"at": 0, "reason": "switch", "acted": False}] * (now_mod.CUE_LOG_MAX + 50)
    state["cue"]["inputProject"] = "A"
    state["cue"]["lastInputAt"] = NOW - 5
    state["cue"]["inputSince"] = NOW - 5
    _cue(state, "B", 1, oq("1"), now=NOW)
    assert len(state["cue"]["log"]) == now_mod.CUE_LOG_MAX


def test_wind_down_window():
    import datetime as dt
    evening = dt.datetime(2026, 10, 29, 22, 0).timestamp()
    noon = dt.datetime(2026, 10, 29, 12, 0).timestamp()
    assert now_mod.is_wind_down(evening, 21)
    assert not now_mod.is_wind_down(noon, 21)


def test_config_falls_back_on_a_bad_value():
    cfg = now_mod.config(lambda key, default=None: "nonsense" if key == "now.wind_down_hour" else default)
    assert cfg["now.wind_down_hour"] == 21.0
