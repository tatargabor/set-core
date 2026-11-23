"""The mandate on the fleet routes: start, inventory, stop, rename.

Every test redirects the mandate store into `tmp_path` and replaces the owner client, so
nothing here starts a process or touches the machine's own records.
"""

from __future__ import annotations

import os

import pytest
from fastapi import HTTPException

from set_orch.api import fleet as fleet_api
from set_orch.api.fleet import MandateBody, RenameAgentBody, StartAgentBody
from set_orch.fleet import mandate
from set_orch.fleet.mandate import MandateStore
from set_orch.fleet.owner_client import OwnerClientError, OwnerUnavailable

MARKER = "ZZ-GOAL-MARKER-ZZ"


class _Owner:
    """Records what the routes asked the owner for."""

    def __init__(self, features=("provider-selection", "unit-origin", "mandate"),
                 start_raises=None, renamed_to=None):
        self.features = set(features)
        self.calls = []
        self.start_raises = start_raises
        self.renamed_to = renamed_to
        self.stopped = []

    def has_feature(self, name):
        return name in self.features

    def start(self, **kw):
        self.calls.append(kw)
        if self.start_raises:
            raise self.start_raises
        return {"label": kw["label"], "pid": 4242, "unit": f"set-agent-{kw['label']}.scope"}

    def stop(self, label):
        self.stopped.append(label)
        return {"found": True, "gone": True, "population": "started-here"}

    def rename(self, label, new_label):
        return {"label": self.renamed_to or new_label, "pid": None}


@pytest.fixture
def world(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    root = tmp_path / "proj"
    root.mkdir()
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: {os.path.realpath(str(root))})
    monkeypatch.setattr(fleet_api, "_project_for", lambda cwd: "proj-a")
    monkeypatch.setattr(fleet_api, "_safe_registry",
                        lambda: [{"name": "proj-a", "path": str(root)}, {"name": "proj-b", "path": "/x/b"}])
    owner = _Owner()
    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: owner)
    return owner, str(root), MandateStore()


def _start(root, **over):
    args = dict(label="proj-a-1200", cwd=root)
    args.update(over)
    return fleet_api.fleet_start_agent(StartAgentBody(**args))


# -- start ----------------------------------------------------------------------------


def test_a_start_with_a_goal_records_the_mandate_and_hands_the_owner_its_id(world):
    owner, root, store = world
    out = _start(root, requested_by="proj-b#12ab34cd",
                 mandate=MandateBody(goal="ship the importer", paths=["src/import/"],
                                     change="importer", done_when="tests pass"))
    call = owner.calls[0]
    record = store.get(call["mandate_id"])
    assert record["goal"] == "ship the importer"
    assert record["kind"] == "work" and record["source"] == "start" and record["carrier"] is True
    assert record["requested_by"] == "proj-b#12ab34cd"
    assert record["scope"] == {"paths": ["src/import/"], "change": "importer"}
    assert record["done_when"] == "tests pass"
    assert record["project"] == "proj-a" and record["label"] == "proj-a-1200"
    # The unit the owner answered with is recorded: it is the join after an owner restart.
    assert record["unit"] == "set-agent-proj-a-1200.scope"
    assert call["mandate_kind"] == "work"
    assert out["mandate"]["goal"] == "ship the importer" and out["mandate_absent"] is None


def test_the_goal_is_never_sent_to_the_owner(world):
    owner, root, _store = world
    _start(root, mandate=MandateBody(goal=f"do the {MARKER} thing", done_when=MARKER, paths=[MARKER]))
    assert MARKER not in repr(owner.calls[0])


def test_an_agent_asking_for_a_peer_without_a_goal_is_refused_and_nothing_starts(world):
    owner, root, store = world
    for body_mandate in (None, MandateBody(goal=None), MandateBody(goal="   ")):
        with pytest.raises(HTTPException) as err:
            _start(root, requested_by="proj-b#12ab34cd", mandate=body_mandate)
        assert err.value.status_code == 400 and "goal" in err.value.detail
    assert owner.calls == [] and store.all() == {}


def test_the_person_may_start_a_terminal_without_a_goal(world):
    owner, root, store = world
    out = _start(root)
    call = owner.calls[0]
    # Still an id in the environment: a mandate declared later takes it.
    assert call["mandate_id"].startswith("m-")
    assert store.all() == {}
    assert out["mandate"] is None and out["mandate_absent"] == {"reason": "not-declared"}


def test_an_old_owner_refuses_a_goal_and_still_starts_a_plain_terminal(world, monkeypatch):
    _owner, root, store = world
    old = _Owner(features=("provider-selection", "unit-origin"))
    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: old)
    with pytest.raises(HTTPException) as err:
        _start(root, mandate=MandateBody(goal="ship the importer"))
    assert err.value.status_code == 503 and "restart" in err.value.detail
    assert old.calls == [] and store.all() == {}
    # Without a goal the request is exactly what it was before mandates existed.
    _start(root)
    assert "mandate_id" not in old.calls[0] and "mandate_kind" not in old.calls[0]


@pytest.mark.parametrize("raised,status", [
    (OwnerClientError("label already held"), 409),
    (OwnerUnavailable("the owner is down"), 503),
])
def test_a_start_that_did_not_happen_leaves_no_mandate(world, monkeypatch, raised, status):
    _owner, root, store = world
    refusing = _Owner(start_raises=raised)
    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: refusing)
    with pytest.raises(HTTPException) as err:
        _start(root, mandate=MandateBody(goal="ship the importer"))
    assert err.value.status_code == status
    assert store.all() == {}


def test_a_desk_label_cannot_be_taken_by_an_ordinary_start(world):
    owner, root, store = world
    with pytest.raises(HTTPException) as err:
        _start(root, label="proj-b-desk", mandate=MandateBody(goal="pretend to be a desk"))
    assert err.value.status_code == 400 and "desk" in err.value.detail
    assert owner.calls == [] and store.all() == {}
    # A label that only LOOKS like one — no such project is registered — is an ordinary label.
    _start(root, label="nobody-desk")
    assert owner.calls[0]["label"] == "nobody-desk"


# -- the inventory --------------------------------------------------------------------


class _Agent:
    def __init__(self, pid, session_id=None):
        self.pid = pid
        self.name = self.project_name = self.project_root = self.cwd = "x"
        self.branch = None
        self.session_id = session_id
        self.session_log = None
        self.binding_confirmed = True
        self.sources = ["process"]
        self.sources_missing = ["session-record", "registry"]
        self.kind = "interactive"
        self.record = None


def _state():
    from set_orch.fleet.state import AgentState
    return AgentState(state="quiet", last_movement_age=1.0)


@pytest.fixture
def carried(monkeypatch):
    """Which mandate id each fake pid 'carries in its environment'."""
    table = {}
    monkeypatch.setattr(mandate.join, "__kwdefaults__",
                        {**mandate.join.__kwdefaults__, "env_reader": lambda pid: table.get(pid)})
    return table


def test_an_agent_with_a_mandate_reports_it(world, carried):
    _owner, _root, store = world
    made = store.create(kind="work", goal="ship the importer", project="proj-a", cwd="/x",
                        label="mine", requested_by="proj-b#12ab34cd")
    carried[7] = made["id"]
    row = fleet_api._agent_payload(_Agent(7), _state(), {7: {"label": "mine"}}, mandates=store.all())
    assert row["mandate"]["goal"] == "ship the importer" and row["mandate"]["kind"] == "work"
    assert row["mandate_absent"] is None
    # No store internals on the wire.
    assert "session_ids" not in row["mandate"] and "unit" not in row["mandate"]


def test_an_agent_without_a_mandate_reports_a_reason_and_never_a_goal(world, carried):
    _owner, _root, store = world
    store.create(kind="work", goal="somebody else's goal", project="proj-a", cwd="/x", label="other")
    ours = fleet_api._agent_payload(_Agent(7), _state(), {7: {"label": "fix-the-login-bug"}},
                                    mandates=store.all())
    hand = fleet_api._agent_payload(_Agent(8), _state(), {}, mandates=store.all())
    assert ours["mandate"] is None and ours["mandate_absent"] == {"reason": "not-declared"}
    assert hand["mandate"] is None and hand["mandate_absent"] == {"reason": "not-started-here"}
    # The label reads like a goal. It is not one.
    assert "login" not in repr(ours["mandate"]) and "login" not in repr(ours["mandate_absent"])


def test_an_unreadable_store_is_unmeasured_and_not_no_mandate(world, carried):
    row = fleet_api._agent_payload(_Agent(7), _state(), {7: {"label": "mine"}}, mandates=None)
    assert row["mandate"] is None and row["mandate_absent"] == {"reason": "unmeasured"}


def test_a_payload_built_without_the_question_claims_nothing(world, carried):
    row = fleet_api._agent_payload(_Agent(7), _state(), {7: {"label": "mine"}})
    assert row["mandate"] is None and row["mandate_absent"] is None


def test_the_requester_survives_an_owner_that_forgot_it(world, carried):
    _owner, _root, store = world
    made = store.create(kind="work", goal="g", project="proj-a", cwd="/x", label="mine",
                        requested_by="proj-b#12ab34cd")
    carried[7] = made["id"]
    # The owner restarted: it holds the agent again by label but has no `requested_by`.
    row = fleet_api._agent_payload(_Agent(7), _state(), {7: {"label": "mine"}}, mandates=store.all())
    assert row["parent"] == {"seat": "proj-b#12ab34cd", "source": "recorded"}
    # And when the owner DOES still know, its answer is the one used.
    row = fleet_api._agent_payload(
        _Agent(7), _state(), {7: {"label": "mine", "requested_by": "proj-c#00000000"}},
        mandates=store.all())
    assert row["parent"] == {"seat": "proj-c#00000000", "source": "recorded"}


def test_the_listing_appends_a_new_session_and_ends_a_mandate_whose_agent_is_gone(world, monkeypatch):
    _owner, _root, _store = world
    now = [1000.0]
    store = MandateStore(clock=lambda: now[0])
    monkeypatch.setattr(mandate, "MandateStore", lambda *a, **k: MandateStore(clock=lambda: now[0]))
    alive = store.create(kind="work", goal="g1", project="proj-a", cwd="/x", label="a")
    gone = store.create(kind="work", goal="g2", project="proj-a", cwd="/x", label="b")
    now[0] += 500
    grouped = [{"agents": [{"mandate": mandate.public(store.get(alive["id"])), "session_id": "sess-1"},
                           {"mandate": None, "session_id": "sess-x"}]}]
    fleet_api._settle_mandates(grouped, store.all())
    assert store.get(alive["id"])["session_ids"] == ["sess-1"]
    assert store.get(alive["id"])["ended"] is None
    assert store.get(gone["id"])["ended"]["reason"] == "ended"


def test_an_unchanged_fleet_costs_the_store_no_write(world, monkeypatch):
    _owner, _root, store = world
    made = store.create(kind="work", goal="g", project="proj-a", cwd="/x", label="a",
                        session_id="sess-1")
    grouped = [{"agents": [{"mandate": mandate.public(store.get(made["id"])), "session_id": "sess-1"}]}]
    before = os.stat(store.path).st_mtime_ns
    writes = []
    monkeypatch.setattr(mandate, "atomic_write_json", lambda *a, **k: writes.append(a))
    fleet_api._settle_mandates(grouped, store.all())
    assert writes == [] and os.stat(store.path).st_mtime_ns == before


def test_settling_with_an_unreadable_store_does_nothing(world):
    fleet_api._settle_mandates([{"agents": [{"mandate": {"id": "m-x"}, "session_id": "s"}]}], None)


# -- stop and rename --------------------------------------------------------------------


def test_stopping_an_agent_ends_its_mandate_as_stopped(world):
    _owner, root, store = world
    _start(root, mandate=MandateBody(goal="ship the importer"))
    fleet_api.fleet_stop_agent("proj-a-1200")
    record = next(iter(store.all().values()))
    assert record["ended"]["reason"] == "stopped" and record["goal"] == "ship the importer"


def test_a_rename_carries_the_mandate_s_label(world, monkeypatch):
    _owner, root, store = world
    _start(root, mandate=MandateBody(goal="ship the importer"))
    monkeypatch.setattr(fleet_api.fleet_layout, "relabel_dock", lambda *a, **k: {})
    monkeypatch.setattr(fleet_api.fleet_layout, "relabel_agent_order", lambda *a, **k: 0)
    out = fleet_api.fleet_rename_agent("proj-a-1200", RenameAgentBody(new_label="importer"))
    assert out["carried"]["mandate"] == 1
    assert next(iter(store.all().values()))["label"] == "importer"


def test_a_desk_is_not_renamed(world):
    _owner, _root, store = world
    store.create(kind="desk", goal="Answer requests", project="proj-a", cwd="/x", label="proj-a-desk")
    with pytest.raises(HTTPException) as err:
        fleet_api.fleet_rename_agent("proj-a-desk", RenameAgentBody(new_label="something-else"))
    assert err.value.status_code == 400 and "desk" in err.value.detail
    assert next(iter(store.all().values()))["label"] == "proj-a-desk"


def test_nothing_is_renamed_to_a_project_s_desk_label(world):
    _owner, root, _store = world
    _start(root, mandate=MandateBody(goal="ship the importer"))
    with pytest.raises(HTTPException) as err:
        fleet_api.fleet_rename_agent("proj-a-1200", RenameAgentBody(new_label="proj-b-desk"))
    assert err.value.status_code == 400 and "proj-b" in err.value.detail
