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
    """A POST and a GET on the same path are one route in prose and two here."""
    from set_orch.api.fleet import router

    surface = {(tuple(sorted(r.methods)), r.path) for r in router.routes}
    assert (("POST",), "/api/fleet/agents") in surface
    assert (("GET",), "/api/fleet/agents") in surface
    assert (("POST",), "/api/fleet/agents/{label}/stop") in surface
    assert (("GET",), "/api/fleet/owner") in surface


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
