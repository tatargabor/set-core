"""The routes that join mandates, desks and engagements to the live fleet, and the map.

The mandate and engagement stores live in `tmp_path`, the bus store is a directory the test
writes, and the inventory, the owner and the resolver are replaced — so each test decides
exactly what the fleet looks like.
"""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from set_orch.api import fleet as fleet_api
from set_orch.api import fleet_mandate as fm
from set_orch.fleet import desk as desk_mod
from set_orch.fleet import engagement, mandate
from set_orch.fleet.engagement import EngagementStore
from set_orch.fleet.mandate import MandateStore

REQ_TS = "2026-11-23T19:12:21.902+01:00"
ANS_TS = "2026-11-23T19:12:22.005+01:00"
MARKER = "ZZ-BODY-MARKER-ZZ"


@pytest.fixture(autouse=True)
def _no_listing_carried_between_tests():
    """The map's inventory cache is module state; a test must not read another test's fleet."""
    fm._MAP_LISTING[:] = []
    yield
    fm._MAP_LISTING[:] = []


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("SET_AGENT_COMM_DIR", str(tmp_path / "bus"))
    monkeypatch.setenv("SET_CONFIG_DIR", str(tmp_path / "cfg"))
    (tmp_path / "bus" / "channels").mkdir(parents=True)
    monkeypatch.setattr(fm, "_registry", lambda: [
        {"name": "alpha", "root": "/x/alpha", "archived": False},
        {"name": "beta", "root": "/x/beta", "archived": False},
        {"name": "idle", "root": "/x/idle", "archived": False},
    ])
    return tmp_path


def _row(pid, *, project, label, seat=None, mandate_rec=None, absent=None, population="started-here",
         state="quiet", moved=4000, parent=None, session_id=None):
    return {"pid": pid, "project": project, "cwd": f"/x/{project}", "terminal_label": label,
            "name": label, "seat": seat, "session_id": session_id or f"sess-{pid}",
            "population": population, "state": state, "last_movement_seconds": moved,
            "mandate": mandate.public(mandate_rec) if mandate_rec else None,
            "mandate_absent": None if mandate_rec else (absent or {"reason": "not-declared"}),
            "parent": parent}


def _listing(*rows, extra_projects=()):
    groups = {}
    for row in rows:
        groups.setdefault(row["project"], []).append(row)
    out = [{"name": name, "archived": False, "agents": agents} for name, agents in groups.items()]
    out += [{"name": name, "archived": False, "agents": []} for name in extra_projects]
    return {"projects": out}


def _bus_reply(tmp_path, room, seat, heading, body="x"):
    d = tmp_path / "bus" / "channels" / room
    d.mkdir(parents=True, exist_ok=True)
    with open(d / f"{seat}.md", "a", encoding="utf-8") as handle:
        handle.write(f"{heading}\n{body}\n\n")


# -- declaring ------------------------------------------------------------------------


def test_declaring_for_a_framework_started_agent_takes_the_id_it_already_carries(env, monkeypatch):
    monkeypatch.setattr(fm, "_live_rows", lambda: [_row(7, project="alpha", label="alpha-1200")])
    monkeypatch.setattr(mandate, "mandate_id_of_pid", lambda pid, **kw: "m-carried00001")
    out = fm.fleet_declare_mandate(fm.DeclareBody(goal="ship the importer", label="alpha-1200",
                                                  done_when="tests pass"))
    assert out["id"] == "m-carried00001" and out["carrier"] is True
    record = MandateStore().get("m-carried00001")
    assert record["source"] == "declared" and record["delivered"] is False
    assert record["session_ids"] == ["sess-7"] and record["label"] == "alpha-1200"


def test_declaring_for_a_hand_opened_agent_is_a_record_for_the_screen_only(env, monkeypatch):
    monkeypatch.setattr(fm, "_live_rows", lambda: [
        _row(8, project="alpha", label=None, population="foreign",
             absent={"reason": "not-started-here"}, session_id="sess-hand")])
    monkeypatch.setattr(mandate, "mandate_id_of_pid", lambda pid, **kw: None)
    out = fm.fleet_declare_mandate(fm.DeclareBody(goal="tidy the docs", session_id="sess-hand"))
    assert out["carrier"] is False and out["delivered"] is False
    assert out["id"].startswith("m-")
    assert MandateStore().get(out["id"])["carrier"] is False


@pytest.mark.parametrize("body,rows,status", [
    (dict(goal="  ", label="a"), [], 400),
    (dict(goal="g"), [], 400),
    (dict(goal="g", label="nobody"), [], 404),
])
def test_a_declaration_that_names_nothing_usable_is_refused(env, monkeypatch, body, rows, status):
    monkeypatch.setattr(fm, "_live_rows", lambda: rows)
    with pytest.raises(HTTPException) as err:
        fm.fleet_declare_mandate(fm.DeclareBody(**body))
    assert err.value.status_code == status


def test_an_agent_that_has_a_mandate_is_not_given_a_second(env, monkeypatch):
    held = MandateStore().create(kind="work", goal="first", project="alpha", cwd="/x", label="a")
    monkeypatch.setattr(fm, "_live_rows", lambda: [_row(7, project="alpha", label="a", mandate_rec=held)])
    with pytest.raises(HTTPException) as err:
        fm.fleet_declare_mandate(fm.DeclareBody(goal="second", label="a"))
    assert err.value.status_code == 409
    assert len(MandateStore().all()) == 1


def test_an_unreadable_inventory_or_store_is_a_503_and_not_a_declaration(env, monkeypatch):
    monkeypatch.setattr(fm, "_live_rows", lambda: None)
    with pytest.raises(HTTPException) as err:
        fm.fleet_declare_mandate(fm.DeclareBody(goal="g", label="a"))
    assert err.value.status_code == 503
    monkeypatch.setattr(fm, "_live_rows", lambda: [
        _row(7, project="alpha", label="a", absent={"reason": "unmeasured"})])
    with pytest.raises(HTTPException) as err:
        fm.fleet_declare_mandate(fm.DeclareBody(goal="g", label="a"))
    assert err.value.status_code == 503


# -- resolving a desk -------------------------------------------------------------------


class _Resolver:
    def __init__(self, result=None, raises=None):
        self.result, self.raises, self.calls = result, raises, []

    def resolve(self, project, *, requested_by):
        self.calls.append((project, requested_by))
        if self.raises:
            raise self.raises
        return self.result


def _desk(started=True):
    return desk_mod.Desk(project="beta", label="beta-desk", seat="beta#0000dddd",
                         mandate_id="m-desk00000001", started=started, pid=900)


def test_resolving_opens_an_engagement_and_returns_the_desk(env, monkeypatch):
    resolver = _Resolver(result=_desk())
    monkeypatch.setattr(fm, "_resolver", lambda: resolver)
    out = fm.fleet_resolve_desk(fm.ResolveBody(project="beta", requested_by="alpha#aaaaaaaa",
                                               subject="the export format"))
    assert out["desk"]["seat"] == "beta#0000dddd" and out["desk"]["started"] is True
    record = EngagementStore().get(out["engagement_id"])
    assert record["state"] == "resolving"   # open only once the asker reports its send
    assert record["desk_seat"] == "beta#0000dddd" and record["desk_label"] == "beta-desk"
    assert record["asker"] == "alpha#aaaaaaaa" and record["subject"] == "the export format"
    assert resolver.calls == [("beta", "alpha#aaaaaaaa")]


@pytest.mark.parametrize("reason", ["archived", "not-on-bus", "not-trusted", "unmeasured", "desk-not-ready"])
def test_a_refused_resolution_is_a_409_and_a_failed_engagement(env, monkeypatch, reason):
    monkeypatch.setattr(fm, "_resolver", lambda: _Resolver(raises=desk_mod.DeskRefused(reason, "why")))
    with pytest.raises(HTTPException) as err:
        fm.fleet_resolve_desk(fm.ResolveBody(project="beta", requested_by="alpha#aaaaaaaa"))
    assert err.value.status_code == 409 and err.value.detail["reason"] == reason
    record = EngagementStore().get(err.value.detail["engagement_id"])
    assert record["state"] == "failed" and record["reason"] == reason


def test_a_crash_in_resolution_does_not_leave_an_engagement_resolving(env, monkeypatch):
    monkeypatch.setattr(fm, "_resolver", lambda: _Resolver(raises=RuntimeError("boom")))
    with pytest.raises(HTTPException) as err:
        fm.fleet_resolve_desk(fm.ResolveBody(project="beta", requested_by="alpha#aaaaaaaa"))
    assert err.value.status_code == 500
    assert EngagementStore().get(err.value.detail["engagement_id"])["state"] == "failed"


def test_an_asker_at_its_bound_is_refused_before_anything_is_resolved(env, monkeypatch):
    resolver = _Resolver(result=_desk())
    monkeypatch.setattr(fm, "_resolver", lambda: resolver)
    monkeypatch.setattr(engagement, "max_open", lambda: 2)
    for _ in range(2):
        fm.fleet_resolve_desk(fm.ResolveBody(project="beta", requested_by="alpha#aaaaaaaa"))
    with pytest.raises(HTTPException) as err:
        fm.fleet_resolve_desk(fm.ResolveBody(project="beta", requested_by="alpha#aaaaaaaa"))
    assert err.value.status_code == 429 and err.value.detail["reason"] == "bound"
    assert len(err.value.detail["open"]) == 2
    assert len(resolver.calls) == 2, "the third request reached the resolver"


def test_the_desk_start_maps_the_owner_s_answers(monkeypatch):
    from set_orch.fleet.owner_client import OwnerClientError, OwnerUnavailable

    class _C:
        def __init__(self, exc):
            self.exc = exc

        def start(self, **kw):
            raise self.exc

    args = dict(label="beta-desk", cwd="/x/beta", project="beta", mandate_id="m-1",
                mandate_kind="desk", requested_by=None)
    monkeypatch.setattr(fm, "OwnerClient", lambda *a, **k: _C(OwnerUnavailable("down")))
    with pytest.raises(desk_mod.StartFailed) as err:
        fm._start_desk(**args)
    assert err.value.reason == "owner-unavailable"
    monkeypatch.setattr(fm, "OwnerClient", lambda *a, **k: _C(OwnerClientError("old", "owner-too-old")))
    with pytest.raises(desk_mod.StartFailed) as err:
        fm._start_desk(**args)
    assert err.value.reason == "start-refused"
    monkeypatch.setattr(fm, "OwnerClient", lambda *a, **k: _C(OwnerClientError("beta-desk is already owned here")))
    with pytest.raises(desk_mod.LabelHeld):
        fm._start_desk(**args)


# -- engagement routes ------------------------------------------------------------------


def _open_engagement(monkeypatch, sent=True):
    monkeypatch.setattr(fm, "_resolver", lambda: _Resolver(result=_desk()))
    eid = fm.fleet_resolve_desk(fm.ResolveBody(project="beta", requested_by="alpha#aaaaaaaa",
                                               subject="the export format"))["engagement_id"]
    if sent:
        fm.fleet_engagement_sent(eid, fm.SentBody(room="dm-alpha--beta", ts=REQ_TS))
    return eid


def test_reporting_the_send_opens_the_engagement(env, monkeypatch):
    eid = _open_engagement(monkeypatch, sent=False)
    out = fm.fleet_engagement_sent(eid, fm.SentBody(room="dm-alpha--beta", ts=REQ_TS))
    assert out["state"] == "open"
    assert EngagementStore().get(eid)["ts"] == REQ_TS


def test_reporting_a_failed_send_fails_it_with_a_class(env, monkeypatch):
    eid = _open_engagement(monkeypatch, sent=False)
    out = fm.fleet_engagement_failed(eid)
    assert out["state"] == "failed" and out["reason"] == "send-failed"
    with pytest.raises(HTTPException) as err:
        fm.fleet_engagement_failed(_open_engagement(monkeypatch, sent=False),
                                   fm.FailedBody(reason="it just did not work"))
    assert err.value.status_code == 400


def test_an_unknown_engagement_is_a_404(env):
    for call in (lambda: fm.fleet_engagement_sent("e-nope", fm.SentBody(room="r", ts=REQ_TS)),
                 lambda: fm.fleet_engagement_failed("e-nope"),
                 lambda: fm.fleet_engagement_withdraw("e-nope")):
        with pytest.raises(HTTPException) as err:
            call()
        assert err.value.status_code == 404


def test_listing_turns_a_linked_reply_into_answered(env, monkeypatch):
    eid = _open_engagement(monkeypatch)
    _bus_reply(env, "dm-alpha--beta", "alpha#aaaaaaaa", f"## {REQ_TS} — REQUEST → beta#0000dddd", MARKER)
    assert fm.fleet_engagements(asker="alpha#aaaaaaaa", project=None, state=None)["engagements"][0]["state"] == "open"
    _bus_reply(env, "dm-alpha--beta", "beta#0000dddd", f"## {ANS_TS} — ANSWER (re: {REQ_TS})", MARKER)
    out = fm.fleet_engagements(asker="alpha#aaaaaaaa", project=None, state=None)
    assert out["measured"] is True and out["engagements"][0]["state"] == "answered"
    assert MARKER not in json.dumps(out)
    assert fm.fleet_engagements(asker=None, project=None, state="open")["engagements"] == []
    assert [e["id"] for e in fm.fleet_engagements(asker=None, project="beta", state=None)["engagements"]] == [eid]


def test_an_unreadable_bus_reports_unmeasured_and_never_open(env, monkeypatch):
    _open_engagement(monkeypatch)   # its room does not exist in the bus store
    out = fm.fleet_engagements(asker=None, project=None, state=None)
    assert out["measured"] is False and out["reason"] == "bus-unreadable"
    assert out["engagements"][0]["state"] == "unmeasured" and out["engagements"][0]["waiting"] is False


# -- the sweep --------------------------------------------------------------------------


class _Stopper:
    def __init__(self):
        self.stopped = []

    def stop(self, label):
        self.stopped.append(label)
        return {"found": True, "gone": True}


def _desk_row(store, **over):
    rec = store.create(kind="desk", goal="Answer requests", project="beta", cwd="/x/beta", label="beta-desk")
    return _row(900, project="beta", label="beta-desk", seat="beta#0000dddd", mandate_rec=rec, **over), rec


def test_a_quiet_desk_with_nothing_open_is_stopped_and_its_mandate_ends(env, monkeypatch):
    row, rec = _desk_row(MandateStore())
    work = _row(901, project="beta", label="beta-1200", mandate_rec=MandateStore().create(
        kind="work", goal="w", project="beta", cwd="/x/beta", label="beta-1200"))
    stopper = _Stopper()
    monkeypatch.setattr(fm, "_live_rows", lambda: [row, work])
    monkeypatch.setattr(fm, "OwnerClient", lambda *a, **k: stopper)
    monkeypatch.setattr(desk_mod, "quiet_seconds", lambda: 1800.0)
    out = fm.sweep_desks()
    assert out["stopped"] == ["beta-desk"] and stopper.stopped == ["beta-desk"]
    assert MandateStore().get(rec["id"])["ended"]["reason"] == "desk-quiet"
    # A quiet WORK agent is not the sweep's business.
    assert "beta-1200" not in stopper.stopped


def test_a_desk_with_an_open_engagement_is_kept(env, monkeypatch):
    row, rec = _desk_row(MandateStore())
    _open_engagement(monkeypatch)
    _bus_reply(env, "dm-alpha--beta", "alpha#aaaaaaaa", f"## {REQ_TS} — REQUEST → beta#0000dddd")
    stopper = _Stopper()
    monkeypatch.setattr(fm, "_live_rows", lambda: [row])
    monkeypatch.setattr(fm, "OwnerClient", lambda *a, **k: stopper)
    monkeypatch.setattr(desk_mod, "quiet_seconds", lambda: 1800.0)
    out = fm.sweep_desks()
    assert stopper.stopped == [] and out["kept"] == [{"label": "beta-desk", "why": "engagement-open"}]
    assert MandateStore().get(rec["id"])["ended"] is None


@pytest.mark.parametrize("over,why", [
    (dict(moved=None), "movement-unmeasured"),
    (dict(state="unknown"), "state-unmeasured"),
    (dict(state="working"), "state-working"),
    (dict(moved=60), "recent-movement"),
])
def test_a_desk_is_kept_when_anything_is_unmeasured_or_busy(env, monkeypatch, over, why):
    row, _rec = _desk_row(MandateStore(), **over)
    stopper = _Stopper()
    monkeypatch.setattr(fm, "_live_rows", lambda: [row])
    monkeypatch.setattr(fm, "OwnerClient", lambda *a, **k: stopper)
    monkeypatch.setattr(desk_mod, "quiet_seconds", lambda: 1800.0)
    assert fm.sweep_desks()["kept"] == [{"label": "beta-desk", "why": why}]
    assert stopper.stopped == []


def test_a_desk_the_framework_does_not_hold_is_not_stopped(env, monkeypatch):
    row, _rec = _desk_row(MandateStore(), population="orphaned")
    stopper = _Stopper()
    monkeypatch.setattr(fm, "_live_rows", lambda: [row])
    monkeypatch.setattr(fm, "OwnerClient", lambda *a, **k: stopper)
    monkeypatch.setattr(desk_mod, "quiet_seconds", lambda: 1800.0)
    assert fm.sweep_desks()["stopped"] == [] and stopper.stopped == []


def test_the_sweep_does_nothing_when_the_inventory_cannot_be_read(env, monkeypatch):
    stopper = _Stopper()
    monkeypatch.setattr(fm, "_live_rows", lambda: None)
    monkeypatch.setattr(fm, "OwnerClient", lambda *a, **k: stopper)
    assert fm.sweep_desks() == {"stopped": [], "kept": [], "measured": False}


# -- the map ----------------------------------------------------------------------------


def _map(monkeypatch, *rows, extra_projects=("idle",)):
    monkeypatch.setattr(fleet_api, "fleet_agents",
                        lambda include_oneshot=False: _listing(*rows, extra_projects=extra_projects))
    return fm.fleet_map()


def test_the_map_carries_agents_with_mandates_and_collapses_idle_projects(env, monkeypatch):
    work = MandateStore().create(kind="work", goal="ship the importer", project="alpha", cwd="/x", label="alpha-1200")
    out = _map(monkeypatch,
               _row(7, project="alpha", label="alpha-1200", seat="alpha#aaaaaaaa", mandate_rec=work),
               _row(8, project="alpha", label="alpha-term"))
    by_name = {p["name"]: p for p in out["projects"]}
    assert by_name["alpha"]["expanded"] is True and by_name["idle"]["expanded"] is False
    nodes = {a["label"]: a for a in by_name["alpha"]["agents"]}
    assert nodes["alpha-1200"]["mandate"]["goal"] == "ship the importer"
    assert nodes["alpha-term"]["mandate"] is None
    assert nodes["alpha-term"]["mandate_absent"] == {"reason": "not-declared"}
    assert out["counts"]["no_mandate"] == 1


def test_the_map_draws_an_engagement_between_the_asker_and_the_desk(env, monkeypatch):
    eid = _open_engagement(monkeypatch)
    _bus_reply(env, "dm-alpha--beta", "alpha#aaaaaaaa", f"## {REQ_TS} — REQUEST → beta#0000dddd")
    desk_rec = MandateStore().create(kind="desk", goal="Answer", project="beta", cwd="/x", label="beta-desk")
    out = _map(monkeypatch,
               _row(7, project="alpha", label="alpha-1200", seat="alpha#aaaaaaaa"),
               _row(900, project="beta", label="beta-desk", seat="beta#0000dddd", mandate_rec=desk_rec))
    rel = [r for r in out["relations"] if r["type"] == "engagement"]
    assert len(rel) == 1 and rel[0]["id"] == eid
    assert rel[0]["from_pid"] == 7 and rel[0]["to_pid"] == 900
    assert rel[0]["state"] == "open" and rel[0]["subject"] == "the export format"
    assert rel[0]["age_seconds"] is not None and rel[0]["waiting"] is False
    assert out["sources"]["bus"] is True


def test_a_waiting_engagement_and_a_failed_one_are_counted(env, monkeypatch):
    _open_engagement(monkeypatch)
    _bus_reply(env, "dm-alpha--beta", "alpha#aaaaaaaa", f"## {REQ_TS} — REQUEST → beta#0000dddd")
    monkeypatch.setattr(engagement, "waiting_seconds", lambda: 0.0)   # everything open is overdue
    monkeypatch.setattr(fm, "_resolver", lambda: _Resolver(raises=desk_mod.DeskRefused("not-on-bus")))
    with pytest.raises(HTTPException):
        fm.fleet_resolve_desk(fm.ResolveBody(project="idle", requested_by="alpha#aaaaaaaa"))
    out = _map(monkeypatch, _row(7, project="alpha", label="alpha-1200", seat="alpha#aaaaaaaa"))
    assert out["counts"]["waiting"] == 1 and out["counts"]["failed"] == 1
    states = sorted(r["state"] for r in out["relations"] if r["type"] == "engagement")
    assert states == ["failed", "open"]
    # A project with a failed request to it is not collapsed away.
    assert {p["name"]: p["expanded"] for p in out["projects"]}["idle"] is True


def test_an_answered_engagement_leaves_the_map(env, monkeypatch):
    _open_engagement(monkeypatch)
    _bus_reply(env, "dm-alpha--beta", "beta#0000dddd", f"## {ANS_TS} — ANSWER (re: {REQ_TS})")
    out = _map(monkeypatch, _row(7, project="alpha", label="alpha-1200", seat="alpha#aaaaaaaa"))
    assert [r for r in out["relations"] if r["type"] == "engagement"] == []


def test_a_start_relation_is_drawn_and_marked_as_a_claim(env, monkeypatch):
    out = _map(monkeypatch,
               _row(7, project="alpha", label="alpha-1200", seat="alpha#aaaaaaaa"),
               _row(9, project="beta", label="beta-helper", seat="beta#0000bbbb",
                    parent={"seat": "alpha#aaaaaaaa", "source": "recorded"}),
               _row(10, project="beta", label="beta-child", seat="beta#0000cccc",
                    parent={"seat": "beta#0000bbbb", "source": "ancestry"}))
    started = [r for r in out["relations"] if r["type"] == "started"]
    # Only the RECORDED requester is this relation; process ancestry is a different fact.
    assert len(started) == 1
    assert started[0]["from_pid"] == 7 and started[0]["to_pid"] == 9 and started[0]["is_claim"] is True


def test_declared_flows_are_drawn_and_a_missing_role_file_says_so(env, monkeypatch):
    out = _map(monkeypatch, _row(7, project="alpha", label="alpha-1200"))
    assert out["sources"]["roles"] == "none"
    assert [r for r in out["relations"] if r["type"] == "flow"] == []

    (env / "cfg").mkdir()
    (env / "cfg" / "project-roles.yaml").write_text(
        "version: 1\nprojects:\n  alpha:\n    flows:\n"
        "      - {to: beta, what: a new field, how: over the bus}\n"
        "      - {to: ghost, what: nothing}\n")
    out = _map(monkeypatch, _row(7, project="alpha", label="alpha-1200"))
    flows = [r for r in out["relations"] if r["type"] == "flow"]
    assert out["sources"]["roles"] == "ok"
    assert flows == [{"type": "flow", "from_project": "alpha", "to_project": "beta",
                      "what": "a new field", "how": "over the bus"}]


def test_an_unreadable_bus_and_store_are_named_in_sources(env, monkeypatch):
    _open_engagement(monkeypatch)   # no room in the bus store
    out = _map(monkeypatch,
               _row(7, project="alpha", label="alpha-1200", absent={"reason": "unmeasured"}))
    assert out["sources"]["bus"] is False and out["sources"]["mandates"] is False
    # An agent whose mandate could not be READ is not counted as having none.
    assert out["counts"]["no_mandate"] == 0
    assert [r["state"] for r in out["relations"] if r["type"] == "engagement"] == ["unmeasured"]
    assert out["counts"]["waiting"] == 0


def test_a_map_with_no_inventory_says_so(env, monkeypatch):
    def boom(include_oneshot=False):
        raise RuntimeError("no inventory")

    monkeypatch.setattr(fleet_api, "fleet_agents", boom)
    out = fm.fleet_map()
    assert out["sources"]["inventory"] is False and out["projects"] == []


def test_the_map_reuses_one_inventory_read_for_a_few_seconds_and_no_longer(env, monkeypatch):
    reads = []
    clock = [100.0]

    def listing(include_oneshot=False):
        reads.append(1)
        return _listing(_row(len(reads), project="alpha", label=f"alpha-{len(reads)}"))

    monkeypatch.setattr(fleet_api, "fleet_agents", listing)
    monkeypatch.setattr(fm.time, "monotonic", lambda: clock[0])
    first = fm.fleet_map()
    clock[0] += fm.MAP_LISTING_MAX_AGE - 1
    again = fm.fleet_map()
    assert len(reads) == 1
    assert again["projects"][0]["agents"][0]["label"] == first["projects"][0]["agents"][0]["label"] == "alpha-1"
    clock[0] += 2
    assert fm.fleet_map()["projects"][0]["agents"][0]["label"] == "alpha-2" and len(reads) == 2


def test_a_failed_inventory_read_is_not_kept_as_the_map_s_answer(env, monkeypatch):
    def boom(include_oneshot=False):
        raise RuntimeError("no inventory")

    monkeypatch.setattr(fleet_api, "fleet_agents", boom)
    assert fm.fleet_map()["sources"]["inventory"] is False
    monkeypatch.setattr(fleet_api, "fleet_agents",
                        lambda include_oneshot=False: _listing(_row(7, project="alpha", label="alpha-1200")))
    out = fm.fleet_map()
    assert out["sources"]["inventory"] is True and out["projects"][0]["name"] == "alpha"


def test_a_decision_never_reads_the_map_s_cached_inventory(env, monkeypatch):
    """Declaring, resolving and sweeping act on the fleet as it is NOW."""
    monkeypatch.setattr(fleet_api, "fleet_agents",
                        lambda include_oneshot=False: _listing(_row(7, project="alpha", label="old")))
    fm.fleet_map()
    monkeypatch.setattr(fleet_api, "fleet_agents",
                        lambda include_oneshot=False: _listing(_row(8, project="alpha", label="new")))
    assert [r["terminal_label"] for r in fm._live_rows()] == ["new"]


# -- the close forecast on the listing (task 10.3) ------------------------------------


def test_the_listing_carries_a_countdown_on_a_quiet_desk_with_nothing_open(env, monkeypatch):
    row, _rec = _desk_row(MandateStore(), moved=60)
    work = _row(901, project="beta", label="beta-1200", mandate_rec=MandateStore().create(
        kind="work", goal="w", project="beta", cwd="/x/beta", label="beta-1200"))
    monkeypatch.setattr(desk_mod, "quiet_seconds", lambda: 300.0)
    grouped = _listing(row, work)["projects"]
    fleet_api._attach_desk_forecasts(grouped)
    assert row["desk_close"] == {"closes_in_seconds": 240.0, "bound_seconds": 300.0}
    assert "desk_close" not in work, "only a desk carries a forecast"


def test_the_listing_carries_no_countdown_while_an_engagement_is_open(env, monkeypatch):
    row, _rec = _desk_row(MandateStore(), moved=60)
    _open_engagement(monkeypatch)
    monkeypatch.setattr(desk_mod, "quiet_seconds", lambda: 300.0)
    fleet_api._attach_desk_forecasts(_listing(row)["projects"])
    assert row["desk_close"] is None


def test_an_answered_engagement_is_settled_before_the_forecast(env, monkeypatch):
    """The reply is on the bus but the store still says open: the listing settles it, as the
    sweep would, so a desk that has answered shows its countdown now, not a round later."""
    row, _rec = _desk_row(MandateStore(), moved=60)
    _open_engagement(monkeypatch)
    _bus_reply(env, "dm-alpha--beta", "beta#0000dddd",
               f"## {ANS_TS} — ANSWER → alpha#aaaaaaaa (re: {REQ_TS})")
    monkeypatch.setattr(desk_mod, "quiet_seconds", lambda: 300.0)
    fleet_api._attach_desk_forecasts(_listing(row)["projects"])
    assert row["desk_close"] == {"closes_in_seconds": 240.0, "bound_seconds": 300.0}


def test_an_unreadable_engagement_store_yields_no_forecast(env, monkeypatch):
    row, _rec = _desk_row(MandateStore(), moved=60)
    monkeypatch.setattr(desk_mod, "quiet_seconds", lambda: 300.0)
    def boom(self, **kw):
        raise engagement.EngagementStoreUnreadable("x")
    monkeypatch.setattr(EngagementStore, "list", boom)
    fleet_api._attach_desk_forecasts(_listing(row)["projects"])
    assert "desk_close" not in row
