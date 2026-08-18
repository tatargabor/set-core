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
        self.binding_confirmed = True
        self.sources = ["process"]
        self.sources_missing = ["session-record", "registry"]
        self.kind = "interactive"
        self.record = None


class _State:
    state, tool, tool_elapsed, other_tools, last_movement_age, reason = "quiet", None, None, [], 1.0, None
    waiting_for = None
    declaration_ignored = None


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

    class _State:
        state, tool, tool_elapsed, other_tools = "quiet", None, None, []
        last_movement_age, reason, waiting_for, declaration_ignored = 1.0, None, None, None

    payload = fleet_api._agent_payload(_WithRecord(), _State(), {})
    assert "record" not in payload
    flattened = json.dumps(payload)
    for secret in ("private-consumer", "cc-socks", "messagingSocketPath"):
        assert secret not in flattened, f"{secret} reached the payload"
