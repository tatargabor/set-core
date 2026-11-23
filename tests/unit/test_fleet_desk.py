"""The desk: one session that answers for a project, found or started — never guessed.

Every dependency of resolution is a callable, so these tests drive the DECISION and nothing
else: no owner, no bus, no registry. What must hold is what a requester relies on blind —
a working session is never handed a stranger's request, two requests never produce two desks,
and a start that would leave a silent agent behind is refused before it happens.
"""

from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from set_orch.fleet import desk as desk_mod
from set_orch.fleet import mandate
from set_orch.fleet.desk import DeskRefused, DeskResolver, LabelHeld, StartFailed
from set_orch.fleet.mandate import MandateStore

ROOT = "/x/beta"


class World:
    """A fake fleet: a registry, live agents, and an owner that starts on request."""

    def __init__(self, tmp_path):
        self.mandates = MandateStore(str(tmp_path / "state" / "fleet-mandates.json"))
        self.projects = [{"name": "beta", "root": ROOT, "archived": False}]
        self.agents = []
        self.inventory_readable = True
        self.starts = []
        self.start_error = None
        self.seat_after_polls = 0   # how many polls until a started desk has a seat
        self.enrolled = True
        self.trusted = True
        self.location_ok = True
        self.now = 0.0
        self.sleeps = 0
        self._pid = 5000
        self._env = {}              # pid -> mandate id (what the process carries)

    # dependencies -------------------------------------------------------------
    def live_agents(self):
        if not self.inventory_readable:
            return None
        for row in self.agents:
            if row.get("_seat_in", 0) > 0:
                row["_seat_in"] -= 1
                if row["_seat_in"] == 0:
                    row["seat"] = row["_future_seat"]
        return [dict(r) for r in self.agents]

    def start(self, **kw):
        self.starts.append(kw)
        if self.start_error is not None:
            raise self.start_error
        self._pid += 1
        pid = self._pid
        self._env[pid] = kw["mandate_id"]
        row = {"pid": pid, "population": "started-here", "terminal_label": kw["label"],
               "unit": f"set-agent-{kw['label']}.scope", "session_id": f"sess-{pid}",
               "seat": None, "state": "working"}
        if self.seat_after_polls == 0:
            row["seat"] = f"beta#{pid:08x}"
        elif self.seat_after_polls > 0:
            row["_seat_in"] = self.seat_after_polls
            row["_future_seat"] = f"beta#{pid:08x}"
        self.agents.append(row)
        return {"label": kw["label"], "pid": pid, "unit": row["unit"]}

    def add_agent(self, *, kind=None, project="beta", label="beta-1200", population="started-here",
                  seat="beta#0000aaaa", goal="do some work"):
        self._pid += 1
        pid = self._pid
        if kind:
            rec = self.mandates.create(kind=kind, goal=goal, project=project, cwd=ROOT, label=label,
                                       unit=f"set-agent-{label}.scope")
            self._env[pid] = rec["id"]
        self.agents.append({"pid": pid, "population": population, "terminal_label": label,
                            "unit": f"set-agent-{label}.scope", "session_id": f"sess-{pid}",
                            "seat": seat, "state": "working"})
        return pid

    def resolver(self, **over):
        args = dict(
            mandates=self.mandates, live_agents=self.live_agents, projects=lambda: self.projects,
            start=self.start, start_location_ok=lambda root: self.location_ok,
            enrolled=lambda project: self.enrolled, trusted=lambda root: self.trusted,
            clock=lambda: self.now, sleep=self._sleep, ready_timeout=60.0,
        )
        args.update(over)
        return DeskResolver(**args)

    def _sleep(self, seconds):
        self.sleeps += 1
        self.now += seconds


@pytest.fixture
def world(tmp_path, monkeypatch):
    w = World(tmp_path)
    # The join reads the id a process carries; here "the process" is the fake's table.
    monkeypatch.setattr(mandate, "mandate_id_of_pid", lambda pid, **kw: w._env.get(pid))
    monkeypatch.setattr(mandate.join, "__kwdefaults__",
                        {**mandate.join.__kwdefaults__, "env_reader": lambda pid: w._env.get(pid)})
    return w


# -- finding ---------------------------------------------------------------------------


def test_a_live_desk_is_returned_and_nothing_is_started(world):
    pid = world.add_agent(kind="desk", label="beta-desk", seat="beta#0000dddd",
                          goal="Answer requests")
    found = world.resolver().resolve("beta", requested_by="alpha#aaaaaaaa")
    assert found.seat == "beta#0000dddd" and found.pid == pid
    assert found.started is False and found.label == "beta-desk"
    assert world.starts == []


def test_working_sessions_of_the_project_are_never_returned(world):
    world.add_agent(kind="work", label="beta-1200", seat="beta#0000aaaa")
    world.add_agent(kind=None, label="beta-hand", population="foreign", seat="beta#0000bbbb")
    found = world.resolver().resolve("beta", requested_by="alpha#aaaaaaaa")
    # A desk was started; neither existing session was handed the request.
    assert found.started is True
    assert found.seat not in ("beta#0000aaaa", "beta#0000bbbb")
    assert len(world.starts) == 1


def test_a_desk_of_another_project_is_not_this_project_s_desk(world):
    world.add_agent(kind="desk", project="gamma", label="gamma-desk", seat="gamma#0000dddd")
    found = world.resolver().resolve("beta", requested_by=None)
    assert found.started is True and found.seat != "gamma#0000dddd"


def test_an_agent_the_framework_does_not_hold_cannot_be_the_desk(world):
    pid = world.add_agent(kind="desk", label="beta-desk", population="orphaned", seat="beta#0000dddd")
    found = world.resolver().resolve("beta", requested_by=None)
    assert found.pid != pid and found.started is True


def test_an_ended_desk_mandate_is_not_a_desk(world):
    pid = world.add_agent(kind="desk", label="beta-desk", seat="beta#0000dddd")
    world.mandates.end(world._env[pid], "desk-quiet")
    world._env.pop(pid)  # the process is gone with its environment
    world.agents.clear()
    assert world.resolver().resolve("beta", requested_by=None).started is True


# -- starting --------------------------------------------------------------------------


def test_no_desk_live_starts_one_with_a_desk_mandate(world):
    found = world.resolver().resolve("beta", requested_by="alpha#aaaaaaaa")
    call = world.starts[0]
    assert call["label"] == "beta-desk" and call["cwd"] == ROOT
    assert call["mandate_kind"] == "desk" and call["requested_by"] == "alpha#aaaaaaaa"
    record = world.mandates.get(call["mandate_id"])
    assert record["kind"] == "desk" and record["project"] == "beta"
    assert record["requested_by"] == "alpha#aaaaaaaa"
    assert record["label"] == "beta-desk" and record["unit"] == "set-agent-beta-desk.scope"
    assert found.started is True and found.mandate_id == record["id"]


def test_the_desk_is_returned_only_once_it_has_a_seat(world):
    world.seat_after_polls = 3
    found = world.resolver().resolve("beta", requested_by=None)
    assert found.seat and world.sleeps >= 1


def test_a_desk_that_never_gets_a_seat_fails_as_not_ready(world):
    world.seat_after_polls = -1  # never
    with pytest.raises(DeskRefused) as err:
        world.resolver().resolve("beta", requested_by=None)
    assert err.value.reason == "desk-not-ready"
    assert world.now >= 60.0


def test_two_requests_at_once_lead_to_one_desk(world):
    """The second start is refused by the label invariant and resolves to the first desk."""
    first = world.resolver().resolve("beta", requested_by="alpha#aaaaaaaa")

    # The second resolver looked before the first desk was visible, then tried to start.
    seen = {"calls": 0}
    real = world.live_agents

    def blind_once():
        seen["calls"] += 1
        return [] if seen["calls"] == 1 else real()

    world.start_error = LabelHeld()
    second = world.resolver(live_agents=blind_once).resolve("beta", requested_by="gamma#cccccccc")
    assert second.seat == first.seat and second.started is False
    desks = [r for r in world.mandates.all().values() if r["kind"] == "desk"]
    assert len(desks) == 1, "the losing start left a second desk mandate behind"


def test_a_refused_start_leaves_no_mandate_behind(world):
    world.start_error = StartFailed("owner-unavailable", "the owner is down")
    with pytest.raises(DeskRefused) as err:
        world.resolver().resolve("beta", requested_by=None)
    assert err.value.reason == "owner-unavailable"
    assert world.mandates.all() == {}


# -- refusals, all before any start ----------------------------------------------------


@pytest.mark.parametrize("setup,reason", [
    (lambda w: w.projects.clear(), "unknown-project"),
    (lambda w: w.projects[0].update(archived=True), "archived"),
    (lambda w: setattr(w, "location_ok", False), "start-location"),
    (lambda w: setattr(w, "enrolled", False), "not-on-bus"),
    (lambda w: setattr(w, "enrolled", None), "unmeasured"),
    (lambda w: setattr(w, "trusted", False), "not-trusted"),
    (lambda w: setattr(w, "trusted", None), "unmeasured"),
    (lambda w: setattr(w, "inventory_readable", False), "unmeasured"),
])
def test_a_request_that_cannot_have_a_desk_is_refused_and_nothing_is_started(world, setup, reason):
    setup(world)
    with pytest.raises(DeskRefused) as err:
        world.resolver().resolve("beta", requested_by="alpha#aaaaaaaa")
    assert err.value.reason == reason
    assert reason in desk_mod.REFUSALS
    assert world.starts == [] and world.mandates.all() == {}


def test_a_live_desk_is_used_even_if_the_prechecks_would_refuse_a_start(world):
    """Enrolment and trust gate a START. A desk that is already up and seated is the proof."""
    world.add_agent(kind="desk", label="beta-desk", seat="beta#0000dddd")
    world.enrolled = None
    world.trusted = None
    assert world.resolver().resolve("beta", requested_by=None).seat == "beta#0000dddd"


# -- the two outside measurements ------------------------------------------------------


def _doctor(payload, returncode=0):
    return lambda argv, **kw: SimpleNamespace(returncode=returncode, stdout=json.dumps(payload))


def test_enrolment_is_read_from_the_bus_doctor_s_hooks():
    wired = {"projects": [{"project": "beta", "hooks": {"session-start": ["settings.json:portable"]},
                           "verdict": "warn"}]}
    bare = {"projects": [{"project": "beta", "hooks": {}, "verdict": "off"}]}
    other = {"projects": [{"project": "beta-tools", "hooks": {"session-start": ["x"]}}]}
    assert desk_mod.enrolled_on_bus("beta", runner=_doctor(wired)) is True   # a warn verdict is not "off"
    assert desk_mod.enrolled_on_bus("beta", runner=_doctor(bare)) is False
    assert desk_mod.enrolled_on_bus("beta", runner=_doctor(other)) is False  # a neighbour's hooks are not ours


def test_enrolment_is_unmeasured_when_the_doctor_cannot_answer():
    def missing(argv, **kw):
        raise FileNotFoundError("sac")

    def slow(argv, **kw):
        raise subprocess.TimeoutExpired(argv, 20)

    assert desk_mod.enrolled_on_bus("beta", runner=missing) is None
    assert desk_mod.enrolled_on_bus("beta", runner=slow) is None
    assert desk_mod.enrolled_on_bus("beta", runner=_doctor({}, returncode=1)) is None
    assert desk_mod.enrolled_on_bus("beta", runner=lambda a, **k: SimpleNamespace(returncode=0, stdout="not json")) is None


def test_trust_is_read_from_the_runtime_s_record(tmp_path):
    record = tmp_path / "claude.json"
    record.write_text(json.dumps({"projects": {
        "/x/beta": {"hasTrustDialogAccepted": True},
        "/x/gamma": {"hasTrustDialogAccepted": False},
    }}))
    assert desk_mod.trusted_by_runtime("/x/beta", record_path=str(record)) is True
    assert desk_mod.trusted_by_runtime("/x/gamma", record_path=str(record)) is False
    assert desk_mod.trusted_by_runtime("/x/never-opened", record_path=str(record)) is False
    assert desk_mod.trusted_by_runtime("/x/beta", record_path=str(tmp_path / "missing.json")) is None
    record.write_text("{ truncated")
    assert desk_mod.trusted_by_runtime("/x/beta", record_path=str(record)) is None


# -- the quiet sweep -------------------------------------------------------------------


QUIET = {"state": "quiet", "last_movement_seconds": 4000}


def test_a_desk_with_nothing_open_and_measured_quiet_is_stopped():
    assert desk_mod.sweep_decision(QUIET, live_engagements=0, quiet_after=1800) == ("stop", "desk-quiet")


def test_a_desk_with_an_open_engagement_is_kept():
    assert desk_mod.sweep_decision(QUIET, live_engagements=1, quiet_after=1800)[0] == "keep"


@pytest.mark.parametrize("row,engagements,why", [
    (QUIET, None, "engagements-unmeasured"),
    ({"state": None, "last_movement_seconds": 4000}, 0, "state-unmeasured"),
    ({"state": "unknown", "last_movement_seconds": 4000}, 0, "state-unmeasured"),
    ({"state": "quiet", "last_movement_seconds": None}, 0, "movement-unmeasured"),
    ({"state": "quiet"}, 0, "movement-unmeasured"),
    ({"state": "quiet", "last_movement_seconds": True}, 0, "movement-unmeasured"),
])
def test_anything_unmeasured_keeps_the_desk(row, engagements, why):
    assert desk_mod.sweep_decision(row, live_engagements=engagements, quiet_after=1800) == ("keep", why)


@pytest.mark.parametrize("row", [
    {"state": "working", "last_movement_seconds": 4000},
    {"state": "asking", "last_movement_seconds": 4000},
    {"state": "quiet", "last_movement_seconds": 1800},
    {"state": "quiet", "last_movement_seconds": 10},
])
def test_a_busy_or_recently_moved_desk_is_kept(row):
    assert desk_mod.sweep_decision(row, live_engagements=0, quiet_after=1800)[0] == "keep"
