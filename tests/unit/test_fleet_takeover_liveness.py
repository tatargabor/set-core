"""The three liveness defects behind the 2026-11-24 stopped requests (fleet-engagement-takeover §1).

Each test holds the case that was measured, in the direction it failed:

- a listing that missed a live desk ended its mandate (a gap read as an absence);
- the running desk then kept its label, so the next request could neither start a desk nor
  find one and failed `desk-not-ready`;
- a desk waiting on its own request to another project was swept as quiet.
"""

from __future__ import annotations

import pytest

from set_orch.fleet import desk as desk_mod
from set_orch.fleet import engagement as eng_mod
from set_orch.fleet import mandate
from set_orch.fleet.mandate import MandateStore

from test_fleet_desk import World  # noqa: F401 — the shared fake fleet


def _make(store, **over):
    args = dict(kind="desk", goal="Answer requests", project="beta", cwd="/x/beta",
                label="beta-desk", unit="set-agent-beta-desk.scope")
    args.update(over)
    return store.create(**args)


# -- 1.1 a mandate ends for a missing agent only when its unit is measured gone ---------


def _aged_store(tmp_path):
    now = [1000.0]
    store = MandateStore(str(tmp_path / "m.json"), clock=lambda: now[0])
    made = _make(store)
    now[0] += 600
    return store, made


def test_a_listing_that_misses_a_running_desk_does_not_end_its_mandate(tmp_path):
    store, made = _aged_store(tmp_path)
    ended = store.end_missing([], unit_alive=lambda unit: True)
    assert ended == []
    assert store.get(made["id"])["ended"] is None


def test_an_unmeasurable_unit_keeps_the_mandate(tmp_path):
    store, made = _aged_store(tmp_path)
    assert store.end_missing([], unit_alive=lambda unit: None) == []
    assert store.get(made["id"])["ended"] is None


def test_a_unit_measurement_that_raises_keeps_the_mandate(tmp_path):
    store, made = _aged_store(tmp_path)

    def boom(unit):
        raise OSError("systemctl gone")

    assert store.end_missing([], unit_alive=boom) == []
    assert store.get(made["id"])["ended"] is None


def _aged_unitless(tmp_path, **over):
    now = [1000.0]
    store = MandateStore(str(tmp_path / "m.json"), clock=lambda: now[0])
    made = _make(store, unit=None, **over)
    now[0] += 600
    return store, made


def test_a_mandate_without_a_unit_is_measured_through_its_label(tmp_path):
    """B-224: a started mandate with no unit was ended without any measurement."""
    store, made = _aged_unitless(tmp_path)
    asked = []

    def alive(unit):
        asked.append(unit)
        return True

    assert store.end_missing([], unit_alive=alive) == []
    assert store.get(made["id"])["ended"] is None
    assert asked == ["set-agent-beta-desk.scope"]


def test_a_mandate_without_a_unit_whose_label_scope_is_gone_is_ended(tmp_path):
    store, made = _aged_unitless(tmp_path)
    assert store.end_missing([], unit_alive=lambda unit: False) == [made["id"]]
    assert store.get(made["id"])["ended"]["reason"] == "ended"


def test_a_mandate_with_neither_unit_nor_label_is_unmeasurable_and_kept(tmp_path):
    store, made = _aged_unitless(tmp_path, label=None)
    assert store.end_missing([], unit_alive=lambda unit: False) == []
    assert store.get(made["id"])["ended"] is None


def test_a_kept_mandate_costs_the_store_no_write(tmp_path):
    """The listing is polled: keeping a mandate must not rewrite the store every round."""
    store, made = _aged_store(tmp_path)
    before = (tmp_path / "m.json").stat().st_mtime_ns
    import os
    os.utime(tmp_path / "m.json", ns=(before - 10_000_000, before - 10_000_000))
    stamp = (tmp_path / "m.json").stat().st_mtime_ns
    assert store.end_missing([], unit_alive=lambda unit: True) == []
    assert (tmp_path / "m.json").stat().st_mtime_ns == stamp


def test_a_unit_measured_gone_ends_the_mandate(tmp_path):
    store, made = _aged_store(tmp_path)
    seen = []
    assert store.end_missing([], unit_alive=lambda unit: seen.append(unit) or False) == [made["id"]]
    assert seen == ["set-agent-beta-desk.scope"]
    assert store.get(made["id"])["ended"]["reason"] == "ended"


# -- 1.2 a live desk whose mandate ended as missing is re-adopted -------------------------


@pytest.fixture
def world(tmp_path, monkeypatch):
    w = World(tmp_path)
    monkeypatch.setattr(mandate, "mandate_id_of_pid", lambda pid, **kw: w._env.get(pid))
    monkeypatch.setattr(mandate.join, "__kwdefaults__",
                        {**mandate.join.__kwdefaults__, "env_reader": lambda pid: w._env.get(pid)})
    return w


def test_a_running_desk_whose_mandate_ended_as_missing_is_the_desk_again(world):
    """The measured failure: the desk ran, its mandate said `ended`, the label was held."""
    pid = world.add_agent(kind="desk", label="beta-desk", seat="beta#0000dddd", goal="Answer requests")
    held = world.mandates.all()
    mandate_id = next(iter(held))
    world.mandates.end(mandate_id, "ended")
    from set_orch.fleet.desk import LabelHeld
    world.start_error = LabelHeld("beta-desk is already owned here")

    found = world.resolver().resolve("beta", requested_by="alpha#aaaaaaaa")

    assert found.pid == pid and found.seat == "beta#0000dddd" and found.started is False
    assert world.mandates.get(mandate_id)["ended"] is None
    assert world.starts == []


@pytest.mark.parametrize("reason", ["replaced", "stopped", "desk-quiet", "agent-done"])
def test_a_desk_ended_by_an_act_is_not_revived(world, reason):
    world.add_agent(kind="desk", label="beta-desk", seat="beta#0000dddd", goal="Answer requests")
    mandate_id = next(iter(world.mandates.all()))
    world.mandates.end(mandate_id, reason)
    assert world.resolver().find("beta") is None
    assert world.mandates.get(mandate_id)["ended"]["reason"] == reason


# -- 1.3 a desk waiting on its own request is not swept ----------------------------------


QUIET = {"state": "quiet", "last_movement_seconds": 4000}


def test_a_quiet_desk_with_its_own_request_open_is_kept():
    assert desk_mod.sweep_decision(QUIET, live_engagements=0, quiet_after=300, asking=1) == (
        "keep", "asking-open")
    assert desk_mod.close_forecast(QUIET, live_engagements=0, quiet_after=300, asking=1) is None


def test_an_unmeasured_asking_count_keeps_the_desk():
    assert desk_mod.sweep_decision(QUIET, live_engagements=0, quiet_after=300, asking=None) == (
        "keep", "engagements-unmeasured")


def test_a_quiet_desk_asking_nothing_is_still_stopped():
    assert desk_mod.sweep_decision(QUIET, live_engagements=0, quiet_after=300, asking=0)[0] == "stop"


def test_live_asked_by_counts_only_live_requests_of_that_seat(tmp_path):
    store = eng_mod.EngagementStore(str(tmp_path / "e.json"))
    a = store.open(asker="alpha#aaaaaaaa", project="beta")
    b = store.open(asker="alpha#aaaaaaaa", project="gamma")
    store.open(asker="delta#dddddddd", project="beta")
    store.mark_failed(b["id"], "not-on-bus")
    assert store.live_asked_by("alpha#aaaaaaaa") == 1
    store.mark_sent(a["id"], room="r", ts="2026-11-24T08:00:00.000+01:00")
    assert store.live_asked_by("alpha#aaaaaaaa") == 1
    assert store.live_asked_by(None) == 0
    assert store.live_asked_by("nobody#00000000") == 0
