"""The fleet API's provider half — tasks 7.1 to 7.8.

A separate file from `test_fleet_api.py` for the reason the sibling owner file
gives: two tracks edit `api/fleet.py` at once, and one shared test file is where
their edits collide silently.

The load-bearing test here is
`test_nothing_this_change_produces_ever_carries_a_credential`. Every other test
in this file guards a mistake somebody would notice; that one guards a mistake
nobody would — a token in a response body, a log line or an error message looks
exactly like a token that is not there until somebody reads the log.
"""

from __future__ import annotations

import logging
import os

import pytest
from fastapi import HTTPException

from set_orch.api import fleet as fleet_api
from set_orch.api.fleet import StartAgentBody
from set_orch.fleet.owner_client import OwnerClientError, OwnerUnavailable
from set_orch.providers.config import Credential, Provider, ProvidersConfig
from set_orch.providers.errors import ConfigError
from set_orch.fleet import state as attention_state

SECRET = "sk-do-not-let-this-out-0123456789"


@pytest.fixture
def _here(monkeypatch, tmp_path):
    """A cwd the screen accepts, so every test below is about the provider."""
    monkeypatch.setattr(fleet_api, "_known_roots",
                        lambda: {os.path.realpath(str(tmp_path))})
    monkeypatch.setattr(fleet_api, "_project_for", lambda cwd: "some-project")
    return str(tmp_path)


class _Owner:
    """Records what the route asked the owner for."""

    def __init__(self, answer=None, raises=None):
        self.calls = []
        self.answer = answer or {"label": "x", "pid": 1, "unit": "u"}
        self.raises = raises

    def start(self, **kw):
        self.calls.append(kw)
        if self.raises:
            raise self.raises
        return self.answer


def _config(**over) -> ProvidersConfig:
    glm = Provider(name="glm", models=("glm-4.6",), requires_credential=True,
                   credential=Credential(token=SECRET, base_url="https://gw.invalid"),
                   default_model="glm-4.6", env={}, args=())
    unset = Provider(name="needs-key", models=("m1",), requires_credential=True,
                     credential=None, default_model=None, env={}, args=())
    login = Provider(name="anthropic", models=("opus",), requires_credential=False,
                     credential=None, default_model="opus", env={}, args=())
    base = dict(providers={"glm": glm, "needs-key": unset, "anthropic": login},
                default_provider="anthropic", default_model="opus", projects={},
                source=__import__("pathlib").Path("/nowhere/providers.json"))
    base.update(over)
    return ProvidersConfig(**base)


# --------------------------------------------------------------------------- #
# 7.1 — the named fields, and what the body still refuses
# --------------------------------------------------------------------------- #

def test_a_start_carries_the_named_provider_and_model_to_the_owner(monkeypatch, _here):
    owner = _Owner()
    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: owner)

    fleet_api.fleet_start_agent(StartAgentBody(
        label="x", cwd=_here, provider="glm", model="glm-4.6"))

    call = owner.calls[0]
    assert call["provider"] == "glm"
    assert call["model"] == "glm-4.6"
    # The project is resolved here, so a per-project override applies to a start
    # made from the screen exactly as it does to one made from the CLI.
    assert call["project"] == "some-project"


def test_the_start_body_still_refuses_an_argv_or_an_environment(monkeypatch, _here):
    """The half that is easy to lose while adding fields.

    A body that accepts an environment mapping is a route that runs an arbitrary
    command with arbitrary secrets — and it would pass every test above.
    """
    with pytest.raises(Exception):
        StartAgentBody(label="x", cwd=_here, argv=["rm", "-rf", "/"])
    with pytest.raises(Exception):
        StartAgentBody(label="x", cwd=_here, env={"ANTHROPIC_AUTH_TOKEN": SECRET})


def test_a_start_naming_nothing_sends_no_provider(monkeypatch, _here):
    owner = _Owner()
    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: owner)
    fleet_api.fleet_start_agent(StartAgentBody(label="x", cwd=_here))
    assert owner.calls[0]["provider"] is None
    assert owner.calls[0]["model"] is None


# --------------------------------------------------------------------------- #
# 7.2 / 7.3 — a refusal reported as the fault it is
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("kind,status", [
    ("unknown-provider", 400),
    ("unknown-model", 400),
    ("provider-config", 503),
    ("command-not-resolvable", 503),
    ("environment-not-delivered", 503),
])
def test_a_refusal_is_answered_by_whose_act_fixes_it(monkeypatch, _here, kind, status):
    """400 and 503 are not severities here, they are addresses.

    A name the catalogue does not declare is this request's mistake and the next
    request may succeed. An unreadable configuration is an operator's file, and
    every request will fail identically until somebody edits it. Answering both
    with 409 — the status for "somebody else holds that label" — sends the
    reader to change a name that was never the problem.
    """
    owner = _Owner(raises=OwnerClientError("nem ismert: zzz", kind))
    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: owner)

    with pytest.raises(HTTPException) as exc:
        fleet_api.fleet_start_agent(StartAgentBody(label="x", cwd=_here, provider="zzz"))
    assert exc.value.status_code == status
    assert "zzz" in exc.value.detail


def test_an_unclassified_refusal_is_still_409(monkeypatch, _here):
    """The existing behaviour, held so the new mapping cannot swallow it.

    An owner that gives no kind — an older one, or a refusal with no class — must
    not be read as a kind of its own. `None` is not a key in the table, and the
    fall-through is the answer that already shipped.
    """
    owner = _Owner(raises=OwnerClientError("label already held"))
    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: owner)
    with pytest.raises(HTTPException) as exc:
        fleet_api.fleet_start_agent(StartAgentBody(label="x", cwd=_here))
    assert exc.value.status_code == 409


def test_an_absent_owner_is_still_503_with_a_provider_named(monkeypatch, _here):
    owner = _Owner(raises=OwnerUnavailable("the agent owner is not running"))
    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: owner)
    with pytest.raises(HTTPException) as exc:
        fleet_api.fleet_start_agent(StartAgentBody(label="x", cwd=_here, provider="glm"))
    assert exc.value.status_code == 503


# --------------------------------------------------------------------------- #
# 7.4 — the catalogue, without the credential
# --------------------------------------------------------------------------- #

def test_the_catalogue_says_whether_a_credential_is_configured_and_never_what(monkeypatch):
    monkeypatch.setattr(fleet_api.providers_config, "load", lambda: _config())

    answer = fleet_api.fleet_providers()
    by_name = {p["name"]: p for p in answer["providers"]}

    assert answer["default_provider"] == "anthropic"
    assert by_name["glm"]["configured"] is True
    assert by_name["glm"]["models"] == ["glm-4.6"]
    # Declared but not set up — a start on it will be refused, and the screen
    # can say so before the click.
    assert by_name["needs-key"]["requires_credential"] is True
    assert by_name["needs-key"]["configured"] is False
    # …and one that needs no credential is NOT reported as unconfigured. The two
    # would collapse into one flag and send the reader looking for a key nobody
    # needs — the false-absence class.
    assert by_name["anthropic"]["requires_credential"] is False
    assert by_name["anthropic"]["usable"] is True
    assert SECRET not in str(answer)
    assert "token" not in str(answer).lower()


def test_an_unreadable_configuration_is_503_and_never_an_empty_catalogue(monkeypatch):
    """An empty list reads as "this machine declares no providers", which is a
    false zero: the screen would offer nothing and say nothing was wrong."""
    def _boom():
        raise ConfigError("/nowhere/providers.json is mode 0644; it holds credentials")

    monkeypatch.setattr(fleet_api.providers_config, "load", _boom)
    with pytest.raises(HTTPException) as exc:
        fleet_api.fleet_providers()
    assert exc.value.status_code == 503
    assert "providers.json" in exc.value.detail


# --------------------------------------------------------------------------- #
# 7.6 — the load-bearing one
# --------------------------------------------------------------------------- #

def test_nothing_this_change_produces_ever_carries_a_credential(monkeypatch, _here, caplog):
    """Response bodies, error messages AND log lines, in one sweep.

    Written as one test on purpose: a credential leaks through whichever carrier
    was not checked, and three separate tests are three places to forget the
    fourth carrier. The log is included because it is the carrier that leaves
    the machine — the rule `db_safety.py` already follows for URLs.
    """
    monkeypatch.setattr(fleet_api.providers_config, "load", lambda: _config())
    owner = _Owner(answer={"label": "x", "pid": 1, "unit": "u",
                           "provider": "glm", "model": "glm-4.6",
                           "provenance": {"credential": "machine-default"}})
    monkeypatch.setattr(fleet_api, "OwnerClient", lambda *a, **k: owner)

    with caplog.at_level(logging.DEBUG):
        catalogue = fleet_api.fleet_providers()
        started = fleet_api.fleet_start_agent(StartAgentBody(
            label="x", cwd=_here, provider="glm", model="glm-4.6"))
        with pytest.raises(HTTPException) as exc:
            monkeypatch.setattr(
                fleet_api, "OwnerClient",
                lambda *a, **k: _Owner(raises=OwnerClientError(
                    "glm: no credential configured", "provider-config")))
            fleet_api.fleet_start_agent(StartAgentBody(
                label="y", cwd=_here, provider="glm"))

    for carrier in (str(catalogue), str(started), exc.value.detail, caplog.text):
        assert SECRET not in carrier
    # The provenance DOES travel — it is the level, which is the useful half and
    # also the safe one.
    assert started["provenance"]["credential"] == "machine-default"


# --------------------------------------------------------------------------- #
# 7.5 — what a listed agent says, and what it must not
# --------------------------------------------------------------------------- #

def test_a_listed_agent_reports_its_provider_or_admits_it_has_none():
    """6.9 as the surface sees it. `recorded: false` is a gap; the machine
    default in that slot would be a claim about who is being billed."""
    from set_orch.fleet.discovery import Agent

    known = Agent(pid=1, cwd="/tmp", session_id="s1")
    unknown = Agent(pid=2, cwd="/tmp", session_id="s2")
    owned = {
        1: {"label": "a", "provider_recorded": True, "provider": "glm",
            "model": "glm-4.6", "provenance": {"provider": "request"}},
        2: {"label": "b"},
    }

    state = attention_state.AgentState()
    row_known = fleet_api._agent_payload(known, state, owned=owned)
    row_unknown = fleet_api._agent_payload(unknown, state, owned=owned)

    assert row_known["provider"]["recorded"] is True
    assert row_known["provider"]["provider"] == "glm"
    assert row_known["provider"]["provenance"]["provider"] == "request"
    assert row_unknown["provider"]["recorded"] is False
    assert row_unknown["provider"]["provider"] is None
