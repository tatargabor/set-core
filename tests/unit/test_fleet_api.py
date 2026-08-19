"""The fleet routes — ordering, and what starting an agent refuses (tasks 5.8, 6.1).

**This file exists because its own absence was a defect.** `api/fleet.py`'s
docstring stated that "the unit test `test_fleet_api.py` fails if that ordering
is lost" while no such file existed — a guard asserted in prose and held by
nothing. The claim is now true.

The ordering it guards (finding CB-16) is not cosmetic: the dashboard serves 53
`/api/{project}/...` routes, FastAPI resolves in registration order, and a
wildcard registered first answers `/api/fleet/agents` as a project named
"fleet" — a 200 with the wrong body, which is worse than a 404.
"""

from __future__ import annotations

import json
import os

import pytest
from fastapi import HTTPException

from set_orch.api import fleet as fleet_api
from set_orch.api.fleet import StartAgentBody
from set_orch.fleet.owner_client import OwnerClientError, OwnerUnavailable


# --------------------------------------------------------------------------- #
# route ordering — CB-16
# --------------------------------------------------------------------------- #

def test_every_fleet_route_is_registered_before_the_project_wildcards():
    from set_orch.api import router

    paths = [(i, r.path) for i, r in enumerate(router.routes)]
    fleet = [i for i, p in paths if p.startswith("/api/fleet")]
    wildcards = [i for i, p in paths if "{project" in p]

    assert fleet, "the fleet router is not mounted at all"
    assert wildcards, "no project wildcard found — this test would pass vacuously"
    assert max(fleet) < min(wildcards), (
        "a project wildcard is registered ahead of a fleet route; "
        "/api/fleet/... would be answered as a project named 'fleet'"
    )


def test_the_start_and_stop_routes_are_reachable_and_distinct():
    """A POST and a GET on the same path are one route in prose and two here.

    `methods` is read defensively because a WebSocket route has none — an earlier
    version of this test read it unconditionally and broke the moment the
    terminal stream was added, which is the whole-surface enumeration finding a
    shape it did not expect rather than a defect in the route.
    """
    from set_orch.api.fleet import router

    surface = {
        (tuple(sorted(getattr(r, "methods", None) or ["WEBSOCKET"])), r.path)
        for r in router.routes
    }
    assert (("POST",), "/api/fleet/agents") in surface
    assert (("GET",), "/api/fleet/agents") in surface
    assert (("POST",), "/api/fleet/agents/{label}/stop") in surface
    assert (("GET",), "/api/fleet/owner") in surface
    assert (("GET",), "/api/fleet/layout") in surface
    assert (("PUT",), "/api/fleet/layout") in surface
    assert (("WEBSOCKET",), "/ws/fleet/agents/{label}/terminal") in surface


def test_the_terminal_route_is_registered_before_the_project_ws_wildcard():
    """The same hazard as CB-16, one path family over: `server.py` includes the
    api router before the ws router, and `/ws/{project}/stream` would otherwise
    be a candidate for anything under `/ws/`. The shapes differ in depth today,
    so this is a guard against a future wildcard rather than a live bug — and it
    says so, because a test whose reason is not written down gets deleted as
    redundant.
    """
    from set_orch.server import create_app

    paths = [getattr(r, "path", "") for r in create_app().routes]
    terminal = [i for i, p in enumerate(paths) if p == "/ws/fleet/agents/{label}/terminal"]
    wildcards = [i for i, p in enumerate(paths) if p.startswith("/ws/") and "{project" in p]
    assert terminal, "the terminal route is not mounted on the app at all"
    assert wildcards, "no /ws wildcard found — this test would pass vacuously"
    assert max(terminal) < min(wildcards)


# --------------------------------------------------------------------------- #
# starting — what it refuses, and with which status
# --------------------------------------------------------------------------- #

def test_a_directory_that_does_not_exist_is_refused_before_the_owner_is_asked(monkeypatch):
    monkeypatch.setattr(
        fleet_api, "OwnerClient",
        lambda *a, **k: pytest.fail("the owner must not be asked about a bad path"),
    )
    with pytest.raises(HTTPException) as excinfo:
        fleet_api.fleet_start_agent(StartAgentBody(label="x", cwd="/no/such/place"))
    assert excinfo.value.status_code == 400


def test_a_real_directory_outside_every_known_project_is_still_refused(monkeypatch, tmp_path):
    """Not choosing here chooses the permissive option: an endpoint that takes
    any existing directory starts an agent anywhere on the machine, and nothing
    on the screen ever offers that.
    """
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: set())
    monkeypatch.setattr(
        fleet_api, "OwnerClient",
        lambda *a, **k: pytest.fail("the owner must not be asked about an unknown root"),
    )
    with pytest.raises(HTTPException) as excinfo:
        fleet_api.fleet_start_agent(StartAgentBody(label="x", cwd=str(tmp_path)))
    assert excinfo.value.status_code == 400
    assert "not a project this screen knows" in excinfo.value.detail


def test_an_absent_owner_is_503_and_never_a_local_fallback(monkeypatch, tmp_path):
    """The 503 is the correct answer, not a degraded one. Starting the agent
    here instead would put it in the dashboard's control group, which is the
    defect (CB-1) the owner service exists to remove.
    """
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: {os.path.realpath(str(tmp_path))})

    class _Down:
        def start(self, **kwargs):
            raise OwnerUnavailable("the agent owner is not running")

    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: _Down())
    with pytest.raises(HTTPException) as excinfo:
        fleet_api.fleet_start_agent(StartAgentBody(label="x", cwd=str(tmp_path)))
    assert excinfo.value.status_code == 503


def test_an_owner_that_refuses_is_409_not_503(monkeypatch, tmp_path):
    """"Already owned" and "not there" need different answers: one is the
    caller's problem to fix by choosing another label, the other is an operator's
    to fix by starting a service. Collapsing them sends the reader to the wrong
    remedy.
    """
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: {os.path.realpath(str(tmp_path))})

    class _Refusing:
        def start(self, **kwargs):
            raise OwnerClientError("x is already owned here")

    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: _Refusing())
    with pytest.raises(HTTPException) as excinfo:
        fleet_api.fleet_start_agent(StartAgentBody(label="x", cwd=str(tmp_path)))
    assert excinfo.value.status_code == 409


def test_the_body_does_not_accept_a_command_to_run():
    """The socket takes an `argv`; this endpoint does not. An HTTP route that
    runs an arbitrary command list is a different thing from a button that
    starts an agent, and only the second one was asked for. Task 5.10 adds the
    engine's entry point as its own, separately-labelled act.
    """
    assert "argv" not in StartAgentBody.model_fields
    body = StartAgentBody(label="x", cwd="/tmp", argv=["rm", "-rf", "/"])  # type: ignore[call-arg]
    assert not hasattr(body, "argv")


# --------------------------------------------------------------------------- #
# the owner-availability route
# --------------------------------------------------------------------------- #

def test_an_unavailable_owner_answers_200_with_the_reason_not_an_error(monkeypatch):
    """The screen asks this to decide whether to OFFER a start. An error status
    here would make "cannot start" indistinguishable from "could not ask", and
    the screen would render a dead button in both cases.
    """
    class _Down:
        def health(self):
            raise OwnerUnavailable("not running; start it with systemctl --user start ...")

    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: _Down())
    answer = fleet_api.fleet_owner()
    assert answer["available"] is False
    assert "systemctl" in answer["reason"]


def test_an_available_owner_reports_how_many_agents_a_restart_would_end(monkeypatch):
    class _Up:
        def health(self):
            return {"ok": True, "pid": 42, "held": 3, "uptime_seconds": 9.0, "socket": "/s"}

    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: _Up())
    answer = fleet_api.fleet_owner()
    assert answer["available"] is True
    assert answer["held"] == 3


def test_stopping_something_that_is_not_running_is_404_not_a_reported_stop(monkeypatch):
    """Measured 2026-08-18 through the live route: it answered `{"gone": true}`
    with a 200 for a label that had never existed. A success for a no-op is the
    false-value class — the screen would confirm an agent was stopped when there
    had never been one.
    """
    class _Nothing:
        def stop(self, label):
            return {"label": label, "unit": "x", "found": False, "gone": True, "population": None}

    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: _Nothing())
    with pytest.raises(HTTPException) as excinfo:
        fleet_api.fleet_stop_agent("never-existed")
    assert excinfo.value.status_code == 404


def test_stopping_an_orphan_succeeds_and_the_answer_says_it_was_one(monkeypatch):
    class _Orphan:
        def stop(self, label):
            return {"label": label, "unit": "u", "found": True, "gone": True, "population": "foreign"}

    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: _Orphan())
    answer = fleet_api.fleet_stop_agent("stray")
    assert answer["gone"] is True
    assert answer["population"] == "foreign", "the surface must be able to say which act it performed"


# --------------------------------------------------------------------------- #
# reading one agent must not read the fleet — task 6.2
# --------------------------------------------------------------------------- #

def test_opening_one_log_does_not_enumerate_the_whole_fleet(monkeypatch):
    """Holds the pattern that was WRONG. This route used to call
    `discover_agents()` to find one pid, and `discover_agents` asks git for the
    project root and the branch of EVERY agent — two subprocesses each, ~44 on
    the machine this was measured on — while the surface polls an open log every
    5 seconds. Measured 2026-08-19: **202 ms for the fleet against 3.5 ms for one
    agent**.

    The cost is invisible from the outside: the endpoint answers correctly either
    way, so nothing fails and nothing looks slow until there are enough agents.
    A comment would not survive a refactor; this does.
    """
    class _Agent:
        pid, name, project_name, binding_confirmed = 4242, "a", "p", True
        session_log = record = None

    monkeypatch.setattr(
        fleet_api, "discover_agents",
        lambda *a, **k: pytest.fail("the per-agent route must not enumerate the fleet"),
    )
    monkeypatch.setattr(fleet_api, "discover_agent", lambda pid, **k: _Agent())
    monkeypatch.setattr(fleet_api, "read_conversation", lambda log, **k: {"turns": []})

    answer = fleet_api.fleet_agent_log(4242, limit=10)
    assert answer["pid"] == 4242


def test_the_state_route_also_stays_off_the_fleet_path(monkeypatch):
    class _Agent:
        pid, name, session_id, binding_confirmed, sources = 7, "a", "s", True, ["process"]
        sources_missing = ["session-record", "registry"]
        session_log = record = None

    monkeypatch.setattr(
        fleet_api, "discover_agents",
        lambda *a, **k: pytest.fail("the per-agent route must not enumerate the fleet"),
    )
    monkeypatch.setattr(fleet_api, "discover_agent", lambda pid, **k: _Agent())
    answer = fleet_api.fleet_agent_state(7)
    assert answer["pid"] == 7
    # `unknown` here is honest: no session log is bound, and the reason says so.
    assert answer["state"] == "unknown"
    assert answer["unknown_reason"]


def test_a_pid_that_is_not_an_agent_is_404_rather_than_someone_elses_log(monkeypatch):
    """A pid is reused. Answering with whatever log a stale pid maps to would
    serve one session's conversation under another's name.
    """
    monkeypatch.setattr(fleet_api, "discover_agent", lambda pid, **k: None)
    for route in (fleet_api.fleet_agent_state, lambda p: fleet_api.fleet_agent_log(p, limit=5)):
        with pytest.raises(HTTPException) as excinfo:
            route(999999)
        assert excinfo.value.status_code == 404


# --------------------------------------------------------------------------- #
# population is a carried fact — task 5.1
# --------------------------------------------------------------------------- #

class _Agent:
    def __init__(self, pid):
        self.pid = pid
        self.name = self.project_name = self.project_root = self.cwd = "x"
        self.branch = self.session_id = None
        # Added when the instruct route needed it. `_Agent` is a hand-written
        # stand-in for a dataclass — the drift the comment on `_State` warns
        # about, one class up — and this field was simply missing.
        self.session_log = None
        self.binding_confirmed = True
        self.sources = ["process"]
        self.sources_missing = ["session-record", "registry"]
        self.kind = "interactive"
        self.record = None


# The REAL dataclass, not a hand-written stand-in.
#
# It used to be a class listing the fields by hand, which is a second copy of
# `AgentState` — and it drifted the moment the dataclass gained a field: four
# tests failed with `AttributeError` on a product that was correct. A stand-in
# that must be maintained in step with the thing it stands in for is a
# maintenance burden pretending to be a test fixture.
def _State(**over):
    from set_orch.fleet.state import AgentState
    return AgentState(state="quiet", last_movement_age=1.0, **over)


def test_an_agent_the_owner_holds_is_started_here_and_names_its_terminal():
    payload = fleet_api._agent_payload(_Agent(7), _State(), {7: {"label": "mine"}})
    assert payload["population"] == "started-here"
    assert payload["terminal_label"] == "mine"


def test_an_agent_the_owner_does_not_hold_has_no_terminal():
    payload = fleet_api._agent_payload(_Agent(7), _State(), {})
    assert payload["population"] == "foreign"
    assert payload["terminal_label"] is None


def test_an_unreachable_owner_is_UNKNOWN_and_never_foreign():
    """The third value, and the reason this is not a boolean.

    `foreign` is a claim — "the framework did not start this, so there is no
    terminal and cannot be". When the owner is merely restarting that claim is
    false for every agent it was holding, and the screen would say "no terminal"
    about agents that have one. An empty answer and no answer are different
    facts; collapsing them is the false-absence class.
    """
    payload = fleet_api._agent_payload(_Agent(7), _State(), None)
    assert payload["population"] == "unknown"
    assert payload["terminal_label"] is None


def test_the_reason_a_terminal_is_unavailable_is_said_once_not_per_row(monkeypatch):
    """A screen that cannot offer a terminal anywhere has ONE cause. Naming it
    once is the difference between "there are no terminals" and "we could not
    ask" — and the second is not a fact about any agent.
    """
    monkeypatch.setattr(fleet_api, "_load_projects", lambda: [])
    monkeypatch.setattr(fleet_api, "discover_agents", lambda **k: [])
    monkeypatch.setattr(fleet_api, "discover_projects", lambda a, registered=None: [])
    monkeypatch.setattr(fleet_api, "_owned_by_pid", lambda: None)
    assert fleet_api.fleet_agents()["owner_reachable"] is False

    monkeypatch.setattr(fleet_api, "_owned_by_pid", lambda: {})
    assert fleet_api.fleet_agents()["owner_reachable"] is True


def test_the_session_record_never_reaches_the_payload(monkeypatch):
    """The confidentiality boundary is a PERSISTENCE boundary, and an API
    response is a place data leaves the machine from.

    `Agent.record` carries the runtime's session record verbatim — cwd, session
    name, and a messaging socket path — because `read_state` needs the declared
    status. None of that was asked for by the surface, and a payload that
    included it would be a leak nobody decided on: it would arrive through a
    field added for an unrelated reason.
    """
    class _WithRecord:
        pid, name, project_name, project_root, cwd = 7, "n", "p", "/r", "/r"
        branch = session_id = None
        binding_confirmed = True
        sources = ["process"]
        sources_missing = ["session-record", "registry"]
        kind = "interactive"
        record = {
            "sessionId": "s", "cwd": "/home/someone/private-consumer",
            "messagingSocketPath": "/run/user/1000/cc-socks/7.sock",
            "name": "private-consumer-12", "status": "idle",
        }


    payload = fleet_api._agent_payload(_WithRecord(), _State(), {})
    assert "record" not in payload
    flattened = json.dumps(payload)
    for secret in ("private-consumer", "cc-socks", "messagingSocketPath"):
        assert secret not in flattened, f"{secret} reached the payload"


# --------------------------------------------------------------------------- #
# instruction and waiters — tasks 6.3 and 6.6
# --------------------------------------------------------------------------- #

from set_orch.fleet import instruct as fleet_instruct
from set_orch.api.fleet import InstructBody


def _seat(session="s-1"):
    return fleet_instruct.Seat(seat="proj#aaaa", agent="proj", session=session,
                               liveness="live")


def test_an_agent_with_no_seat_is_409_with_the_reason_not_a_generic_failure(monkeypatch):
    """4.4 — the reason travels in the body so the surface can put it where the
    input would be. A bare 500 or a 400 would render as "something broke"."""
    agent = _Agent(7)
    agent.session_id = "s-1"
    monkeypatch.setattr(fleet_api, "discover_agent", lambda pid, **k: agent)
    monkeypatch.setattr(fleet_instruct, "read_seats", lambda **k: {})
    with pytest.raises(HTTPException) as excinfo:
        fleet_api.fleet_instruct_agent(7, InstructBody(text="csináld"))
    assert excinfo.value.status_code == 409
    assert excinfo.value.detail["reason"] == fleet_instruct.NO_SEAT


def test_an_unreadable_bus_is_a_different_reason_from_an_unenrolled_agent(monkeypatch):
    """Per CLAUDE.md the answer to *not enrolled* is enrolment, never a second
    transport — so the surface must be able to tell the two apart."""
    agent = _Agent(7)
    agent.session_id = "s-1"
    monkeypatch.setattr(fleet_api, "discover_agent", lambda pid, **k: agent)
    monkeypatch.setattr(fleet_instruct, "read_seats", lambda **k: None)
    with pytest.raises(HTTPException) as excinfo:
        fleet_api.fleet_instruct_agent(7, InstructBody(text="csináld"))
    assert excinfo.value.detail["reason"] == fleet_instruct.BUS_UNREADABLE


def test_a_pid_that_is_not_an_agent_is_404_rather_than_someone_elses_agent(monkeypatch):
    """A pid is recycled. Instructing whatever session it now maps to would
    deliver one person's message to another's agent."""
    monkeypatch.setattr(fleet_api, "discover_agent", lambda pid, **k: None)
    with pytest.raises(HTTPException) as excinfo:
        fleet_api.fleet_instruct_agent(999999, InstructBody(text="x"))
    assert excinfo.value.status_code == 404


def test_the_route_carries_the_outcome_and_never_infers_it_from_the_200(monkeypatch):
    """6.3 — a 200 means the send was made and answered, not that it arrived."""
    agent = _Agent(7)
    agent.session_id = "s-1"
    monkeypatch.setattr(fleet_api, "discover_agent", lambda pid, **k: agent)
    monkeypatch.setattr(fleet_instruct, "read_seats", lambda **k: {"s-1": _seat()})
    monkeypatch.setattr(fleet_instruct, "live_waiters", lambda **k: [])
    monkeypatch.setattr(fleet_api, "read_state", lambda *a, **k: _State())
    monkeypatch.setattr(fleet_instruct, "send_instruction",
                        lambda *a, **k: fleet_instruct.DeliveryReport(
                            outcome=fleet_instruct.SITS_UNREAD, accepted=True,
                            seat="proj#aaaa", wakes=["proj#aaaa"]))
    out = fleet_api.fleet_instruct_agent(7, InstructBody(text="csináld"))
    assert out["accepted"] is True
    assert out["outcome"] == fleet_instruct.SITS_UNREAD
    assert out["delivered_to_agent"] is False
    assert out["waiters_here"] == 0


def test_a_refusal_from_the_bus_is_409_and_is_not_retried_as_a_broadcast(monkeypatch):
    agent = _Agent(7)
    agent.session_id = "s-1"
    sends = []
    monkeypatch.setattr(fleet_api, "discover_agent", lambda pid, **k: agent)
    monkeypatch.setattr(fleet_instruct, "read_seats", lambda **k: {"s-1": _seat()})
    monkeypatch.setattr(fleet_instruct, "live_waiters", lambda **k: [])
    monkeypatch.setattr(fleet_api, "read_state", lambda *a, **k: _State())

    def _send(*a, **k):
        sends.append(k)
        return fleet_instruct.DeliveryReport(
            outcome=fleet_instruct.REFUSED, seat="proj#aaaa", reason="nobody is called that")

    monkeypatch.setattr(fleet_instruct, "send_instruction", _send)
    with pytest.raises(HTTPException) as excinfo:
        fleet_api.fleet_instruct_agent(7, InstructBody(text="csináld"))
    assert excinfo.value.status_code == 409
    assert len(sends) == 1, "the route retried after a refusal"


def test_an_empty_instruction_is_refused_before_the_bus_is_touched(monkeypatch):
    agent = _Agent(7)
    agent.session_id = "s-1"
    asked = []
    monkeypatch.setattr(fleet_api, "discover_agent", lambda pid, **k: agent)
    monkeypatch.setattr(fleet_instruct, "read_seats", lambda **k: asked.append(1) or {})
    with pytest.raises(HTTPException) as excinfo:
        fleet_api.fleet_instruct_agent(7, InstructBody(text="   "))
    assert excinfo.value.status_code == 400
    assert asked == []


def test_a_send_never_uses_the_cached_roster(monkeypatch):
    """The cache exists so a POLL does not spawn a process per tile. An outcome
    depends on who is live at this instant, and a ten-second-old answer to that
    is exactly the stale measurement this screen exists to avoid."""
    agent = _Agent(7)
    agent.session_id = "s-1"
    used = []
    monkeypatch.setattr(fleet_api, "discover_agent", lambda pid, **k: agent)
    monkeypatch.setattr(fleet_instruct, "seats_cached",
                        lambda *a, **k: used.append("cached") or {"s-1": _seat()})
    monkeypatch.setattr(fleet_instruct, "read_seats",
                        lambda **k: used.append("fresh") or {"s-1": _seat()})
    monkeypatch.setattr(fleet_instruct, "live_waiters", lambda **k: [])
    monkeypatch.setattr(fleet_api, "read_state", lambda *a, **k: _State())
    monkeypatch.setattr(fleet_instruct, "send_instruction",
                        lambda *a, **k: fleet_instruct.DeliveryReport(
                            outcome=fleet_instruct.SITS_UNREAD, accepted=True))
    fleet_api.fleet_instruct_agent(7, InstructBody(text="x"))
    assert used == ["fresh"]


def test_the_listing_carries_why_an_agent_cannot_be_instructed():
    agent = _Agent(7)
    agent.session_id = "s-1"
    payload = fleet_api._agent_payload(agent, _State(), {}, {})
    assert payload["instructable"] is False
    assert payload["reason"] == fleet_instruct.NO_SEAT
    assert payload["seat"] is None


def test_the_listing_names_the_seat_where_there_is_one():
    agent = _Agent(7)
    agent.session_id = "s-1"
    payload = fleet_api._agent_payload(agent, _State(), {}, {"s-1": _seat()})
    assert payload["instructable"] is True and payload["seat"] == "proj#aaaa"


# --- waiters ---------------------------------------------------------------- #


def _waiter(pid, session):
    return fleet_instruct.Waiter(pid=pid, session=session, cwd="/x")


def test_an_unreadable_process_table_is_not_an_empty_waiter_list(monkeypatch):
    """"No waiters" invites installing one; "we could not look" does not."""
    monkeypatch.setattr(fleet_instruct, "live_waiters", lambda **k: None)
    out = fleet_api.fleet_waiters()
    assert out["measured"] is False and out["orphaned_count"] == 0
    assert out["reason"]


def test_undeterminable_liveness_orphans_nothing_and_says_so(monkeypatch):
    monkeypatch.setattr(fleet_instruct, "live_waiters",
                        lambda **k: [_waiter(1, "a"), _waiter(2, "b")])
    monkeypatch.setattr(fleet_api, "live_session_ids", lambda **k: None)
    out = fleet_api.fleet_waiters()
    assert out["measured"] is False
    assert out["orphaned"] == [] and all(not r["removable"] for r in out["waiters"])


def test_the_three_statuses_are_kept_apart(monkeypatch):
    """`orphaned` may be removed, `live` must not be, and `undeterminable` is a
    waiter whose session cannot be read — listed, never offered."""
    monkeypatch.setattr(fleet_instruct, "live_waiters",
                        lambda **k: [_waiter(1, "halott"), _waiter(2, "elo"), _waiter(3, None)])
    monkeypatch.setattr(fleet_api, "live_session_ids", lambda **k: {"elo"})
    out = fleet_api.fleet_waiters()
    by_pid = {r["pid"]: r for r in out["waiters"]}
    assert by_pid[1]["status"] == "orphaned" and by_pid[1]["removable"] is True
    assert by_pid[2]["status"] == "live" and by_pid[2]["removable"] is False
    assert by_pid[3]["status"] == "undeterminable" and by_pid[3]["removable"] is False
    assert out["orphaned"] == [1]


def test_a_refused_removal_is_409_carrying_its_reason(monkeypatch):
    monkeypatch.setattr(fleet_api, "live_session_ids", lambda **k: {"elo"})
    monkeypatch.setattr(fleet_instruct, "remove_waiter",
                        lambda pid, **k: {"removed": False, "pid": pid, "reason": "its session is alive"})
    with pytest.raises(HTTPException) as excinfo:
        fleet_api.fleet_remove_waiter(2)
    assert excinfo.value.status_code == 409
    assert "alive" in excinfo.value.detail["reason"]


def test_there_is_no_bulk_remove_route():
    """A cleanup that takes a list is one mistaken list away from killing live
    waiters, and a killed live waiter is invisible."""
    from set_orch.api import router
    removes = [r.path for r in router.routes if "waiter" in r.path and "remove" in r.path]
    assert removes == ["/api/fleet/waiters/{pid}/remove"]
    assert not any(r.path.endswith("/waiters/remove") for r in router.routes)


# --------------------------------------------------------------------------- #
# 3.4 / 3.5 in the payload — declared, never merged into measured
# --------------------------------------------------------------------------- #


def _seat_with(**over):
    base = dict(seat="proj#aaaa", agent="proj", session="s-1", liveness="live")
    base.update(over)
    return fleet_instruct.Seat(**base)


def test_an_unreadable_bus_is_not_an_agent_that_declared_nothing():
    """Two different sentences: "it says nothing about itself" and "we could not
    find out". Only the first is a fact about the agent."""
    agent = _Agent(7); agent.session_id = "s-1"
    silent = fleet_api._agent_payload(agent, _State(), {}, None)["declared"]
    nothing = fleet_api._agent_payload(agent, _State(), {}, {})["declared"]
    assert silent["known"] is False and nothing["known"] is True
    assert silent["phase"] is None and nothing["phase"] is None


def test_blocked_and_working_are_both_reported():
    """3.5 — the pair the surface exists to show."""
    agent = _Agent(7); agent.session_id = "s-1"
    seats = {"s-1": _seat_with(phase="blocked", focus_text="egy válaszra várok")}
    payload = fleet_api._agent_payload(agent, _StateOf("working", tool="Bash"), {}, seats)
    assert payload["state"] == "working"
    assert payload["declared"]["blocked"] is True
    assert payload["declared"]["phase"] == "blocked"


def test_a_waiting_agent_that_declared_nothing_is_not_blocked():
    agent = _Agent(7); agent.session_id = "s-1"
    payload = fleet_api._agent_payload(agent, _StateOf("waiting"), {}, {"s-1": _seat_with()})
    assert payload["state"] == "waiting"
    assert payload["declared"]["blocked"] is False and payload["declared"]["phase"] is None


def test_the_declaration_never_reaches_a_log_record(caplog):
    """CONFIDENTIALITY — measured on the live roster: one project's focus named a
    partner company and an unpaid invoice. Shown at request time, never written."""
    import logging
    agent = _Agent(7); agent.session_id = "s-1"
    marker = "Saltex Kft kifizetetlen szamlai"
    seats = {"s-1": _seat_with(focus_text=marker, focus_files=("knowledge/tetelek.md",))}
    with caplog.at_level(logging.DEBUG):
        payload = fleet_api._agent_payload(agent, _State(), {}, seats)
    assert payload["declared"]["focus"] == marker     # it REACHED the reader…
    blob = " ".join(r.getMessage() for r in caplog.records) + " ".join(
        str(r.args) for r in caplog.records)
    assert marker not in blob                          # …and nowhere else
    assert "tetelek.md" not in blob


def _StateOf(state, **over):
    """`_State` fixes `state="quiet"`; these tests need another one.

    A separate helper rather than a parameter on `_State`, because that fixture
    is used by a dozen tests whose point is that the state is quiet — widening
    it would put a default in their path.
    """
    from set_orch.fleet.state import AgentState
    return AgentState(state=state, last_movement_age=1.0, **over)


# --------------------------------------------------------------------------- #
# 3.9 in the payload — purpose from the engine's record, never invented
# --------------------------------------------------------------------------- #


def _purpose(pid, **over):
    from set_orch.fleet.purpose import Progress, Purpose
    base = dict(change="c", unit_id="u1", group="g1", pid=pid, status="running",
                progress=Progress(done=2, total=5, measured=True))
    base.update(over)
    return Purpose(**base)


def test_an_agent_with_no_recorded_run_reports_no_purpose():
    """Design §8.1 — where the engine is absent the absence is stated, not filled."""
    agent = _Agent(7); agent.session_id = "s-1"
    assert fleet_api._agent_payload(agent, _State(), {}, {}, [])["purpose"] is None
    assert fleet_api._agent_payload(agent, _State(), {}, {}, None)["purpose"] is None


def test_the_purpose_is_joined_on_the_pid_the_engine_recorded():
    agent = _Agent(7); agent.session_id = "s-1"
    payload = fleet_api._agent_payload(agent, _State(), {}, {}, [_purpose(7)])
    assert payload["purpose"]["change"] == "c" and payload["purpose"]["group"] == "g1"
    assert payload["purpose"]["progress"]["done"] == 2


def test_another_agents_run_does_not_leak_onto_this_tile():
    agent = _Agent(7); agent.session_id = "s-1"
    assert fleet_api._agent_payload(agent, _State(), {}, {}, [_purpose(9)])["purpose"] is None


def test_a_stale_record_is_never_shown_as_this_agents_purpose():
    """A record whose process is gone must not lend its purpose to whatever now
    holds that pid — that is one project's work under another's agent."""
    agent = _Agent(7); agent.session_id = "s-1"
    stale = _purpose(7, status="stale")
    assert fleet_api._agent_payload(agent, _State(), {}, {}, [stale])["purpose"] is None


# --------------------------------------------------------------------------- #
# 5.10 / 9.16 — exactly ONE path starts a work unit
# --------------------------------------------------------------------------- #

from set_orch.api.fleet import StartUnitBody


def test_the_unit_route_runs_the_engines_command_and_never_spawns_an_agent(monkeypatch, tmp_path):
    """5.10 — a run started outside the engine is absent from the engine's state,
    which is the source the rest of this screen reads."""
    seen = {}
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: {str(tmp_path)})
    monkeypatch.setattr(fleet_api.OwnerClient, "start",
                        lambda self, **kw: seen.update(kw) or {"label": kw["label"], "pid": 5})
    out = fleet_api.fleet_start_unit(StartUnitBody(
        change="fleet-view", cwd=str(tmp_path), seat="set-core#aaaa", limit=3))
    argv = seen["argv"]
    assert argv[0] == fleet_api.ENGINE_COMMAND
    assert fleet_api.ENGINE_RUN in argv
    assert "--seat" in argv and "set-core#aaaa" in argv
    assert "--limit" in argv and "3" in argv
    assert out["kind"] == "work-unit" and out["change"] == "fleet-view"


def test_the_unit_route_builds_the_argv_and_takes_none(tmp_path):
    """No parameter through which a second start path could be smuggled in."""
    fields = set(StartUnitBody.model_fields)
    assert "argv" not in fields and "command" not in fields and "label" not in fields


def test_the_engine_subcommand_this_route_names_is_the_one_that_starts_a_unit():
    """9.16 — asserted against the ENGINE's own parser, not against a string.

    The engine marks its start command `starts_a_unit=True` precisely so a
    caller can check rather than assume. A test that only checked our constant
    spelled `run` would pass on a build where the engine renamed it.
    """
    from set_workcycle.cli import build_parser
    import argparse
    parser = build_parser()
    subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    assert len(subs) == 1
    starting = [name for name, sp in subs[0].choices.items()
                if getattr(sp.get_default("starts_a_unit"), "__bool__", lambda: False)()]
    assert starting == [fleet_api.ENGINE_RUN], starting


def test_exactly_one_surface_route_starts_a_work_unit(monkeypatch, tmp_path):
    """9.16 — enumerate the START paths and DRIVE each one; do not read the source.

    A source scan for the engine's name is a substring test wearing a
    guarantee: it passes on a route that merely mentions the constant and fails
    on one that reaches it through a variable. So each starter is actually
    called against a fake owner, and what is asserted is the argv it handed over
    — the thing the owner would really execute.

    Two starters are expected, not one. The bare-session route is deliberately
    still here (5.8), so "only one start route" would be wrong in the other
    direction; what must be unique is the one that starts a WORK UNIT.
    """
    import inspect
    from set_orch.api import fleet as mod

    calls = []
    monkeypatch.setattr(mod, "_known_roots", lambda: {str(tmp_path)})
    monkeypatch.setattr(mod.OwnerClient, "start",
                        lambda self, **kw: calls.append(kw) or {"label": kw["label"], "pid": 1})

    starters = [name for name, fn in vars(mod).items()
                if name.startswith("fleet_") and callable(fn)
                and "OwnerClient().start(" in (inspect.getsource(fn) if inspect.isfunction(fn) else "")]
    assert sorted(starters) == ["fleet_start_agent", "fleet_start_unit"], starters

    mod.fleet_start_agent(StartAgentBody(label="bare", cwd=str(tmp_path)))
    mod.fleet_start_unit(StartUnitBody(change="c", cwd=str(tmp_path), seat="p#1"))

    engine_starts = [c for c in calls
                     if (c.get("argv") or [None])[0] == mod.ENGINE_COMMAND]
    assert len(calls) == 2, calls
    assert len(engine_starts) == 1, calls
    # …and the bare one hands over NO argv at all, so it cannot become a second
    # way to run the engine by passing one in.
    bare = [c for c in calls if c not in engine_starts]
    assert bare[0].get("argv") is None


def test_a_directory_outside_every_known_project_cannot_start_a_unit(monkeypatch, tmp_path):
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: set())
    monkeypatch.setattr(fleet_api.OwnerClient, "start",
                        lambda self, **kw: pytest.fail("the owner was asked"))
    with pytest.raises(HTTPException) as excinfo:
        fleet_api.fleet_start_unit(StartUnitBody(change="c", cwd=str(tmp_path), seat="s#1"))
    assert excinfo.value.status_code == 400


def test_an_absent_owner_is_503_with_no_local_fallback(monkeypatch, tmp_path):
    """Starting it here would rebuild CB-1: the dashboard restarts on every
    deploy and would take every agent it started with it."""
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: {str(tmp_path)})
    def _down(self, **kw):
        raise OwnerUnavailable("no owner")
    monkeypatch.setattr(fleet_api.OwnerClient, "start", _down)
    with pytest.raises(HTTPException) as excinfo:
        fleet_api.fleet_start_unit(StartUnitBody(change="c", cwd=str(tmp_path), seat="s#1"))
    assert excinfo.value.status_code == 503


def test_the_label_tells_a_unit_run_from_a_bare_session(monkeypatch, tmp_path):
    """The terminal column, the stop action and recovery all key on the label."""
    seen = {}
    monkeypatch.setattr(fleet_api, "_known_roots", lambda: {str(tmp_path)})
    monkeypatch.setattr(fleet_api.OwnerClient, "start",
                        lambda self, **kw: seen.update(kw) or {"label": kw["label"]})
    fleet_api.fleet_start_unit(StartUnitBody(change="c", cwd=str(tmp_path), seat="p#1"))
    assert seen["label"].startswith("unit-")
    assert "#" not in seen["label"] and "/" not in seen["label"]


# --------------------------------------------------------------------------- #
# 5.5 — the terminal does not survive the owner, and `foreign` would be a lie
# --------------------------------------------------------------------------- #


def test_an_agent_the_framework_started_is_orphaned_not_foreign(monkeypatch):
    """5.5 — after the owner restarts, its scope is still there and the pty is not.

    Reporting this `foreign` says the framework did not start it. It did; it lost
    the handle. And `foreign` hides the one control that helps, because recovery
    is possible exactly here and impossible for a genuinely foreign session.
    """
    monkeypatch.setattr(fleet_api.fleet_scopes, "scope_of",
                        lambda pid: "set-agent-mine.scope")
    payload = fleet_api._agent_payload(_Agent(7), _State(), {})
    assert payload["population"] == "orphaned"
    assert payload["scope"] == "set-agent-mine.scope"
    assert payload["terminal_label"] is None, "an orphan has no terminal to attach to"


def test_a_session_in_no_framework_scope_is_still_foreign(monkeypatch):
    monkeypatch.setattr(fleet_api.fleet_scopes, "scope_of", lambda pid: None)
    payload = fleet_api._agent_payload(_Agent(7), _State(), {})
    assert payload["population"] == "foreign" and payload["scope"] is None


def test_an_unreachable_owner_is_still_unknown_and_the_cgroup_is_not_consulted(monkeypatch):
    """`unknown` must not become `orphaned`: the owner being unreachable is not
    evidence about whether it holds this pty, and a scope says nothing about that."""
    asked = []
    monkeypatch.setattr(fleet_api.fleet_scopes, "scope_of",
                        lambda pid: asked.append(pid) or "set-agent-x.scope")
    payload = fleet_api._agent_payload(_Agent(7), _State(), None)
    assert payload["population"] == "unknown" and asked == []


def test_the_survival_claim_is_narrower_than_the_scope_suggests():
    """Measured both ways: pty-attached + owner killed → scope inactive, process
    gone. So the framework may claim a web-service restart and nothing more."""
    payload = fleet_api._agent_payload(_Agent(7), _State(), {7: {"label": "mine"}})
    assert payload["survives"] == "web-service-restart"
    assert "owner" not in payload["survives"]


# --------------------------------------------------------------------------- #
# 7.18 — descendants, and what the count cannot see
# --------------------------------------------------------------------------- #


def test_descendants_come_from_what_was_recorded_at_start_time():
    """The process tree cannot answer this: measured, 0 of 23 live agents had an
    agent ancestor, and an agent this surface starts has the OWNER as its parent."""
    a, b = _Agent(7), _Agent(9)
    index = fleet_api._descendants_index([a, b], {9: {"requested_by": "proj#aaaa"}})
    assert index == {"proj#aaaa": [9]}


def test_the_count_says_it_only_sees_live_children_even_when_it_is_zero():
    """Zero is exactly when a reader takes a number for completeness. An agent
    started with `claude -p` that has exited leaves no process to count."""
    agent = _Agent(7); agent.session_id = "s-1"
    payload = fleet_api._agent_payload(agent, _State(), {}, {"s-1": _seat_with()}, [], {})
    d = payload["descendants"]
    assert d["known"] is True and d["live"] == 0
    assert d["live_only"] is True and "already exited" in d["reason"]


def test_a_descendant_is_named_so_the_surface_can_offer_a_way_in():
    agent = _Agent(7); agent.session_id = "s-1"
    payload = fleet_api._agent_payload(
        agent, _State(), {}, {"s-1": _seat_with()}, [], {"proj#aaaa": [11, 12]})
    assert payload["descendants"]["live"] == 2
    assert payload["descendants"]["pids"] == [11, 12]


def test_an_agent_with_no_seat_reports_unknown_rather_than_zero():
    """Without a seat there is no key to look this agent up by, and a zero would
    say *nothing runs under it* about an agent that may have started five."""
    agent = _Agent(7); agent.session_id = "s-1"
    d = fleet_api._agent_payload(agent, _State(), {}, {}, [], {})["descendants"]
    assert d["known"] is False and d["live"] == 0


def test_lineage_does_not_stop_at_the_project_boundary(monkeypatch):
    """The index is built once for the whole fleet. A per-project one would
    report a lineage that ends where the project does, which is not where it ends."""
    import inspect
    src = inspect.getsource(fleet_api.fleet_agents)
    before_loop = src.split("for project in projects:")[0]
    assert "_descendants_index(" in before_loop, \
        "the index is built inside the per-project loop"
