"""The usage route: where it sits in the table, and what it never carries.

Registration order is not cosmetic here for the same reason it is not for the
fleet routes (finding CB-16): FastAPI resolves in registration order, and a
`/api/{project}/...` family registered first would answer `/api/usage/accounts`
as a project named "usage" — a 200 with the wrong body, which is worse than a 404.
"""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from set_orch.api.usage import router as usage_router
from set_orch.usage.accounts import Account, KIND_CC, KIND_WEB
from set_orch.usage.client import UsageClient
from set_orch.usage.poller import UsagePoller

ORGS = [{"uuid": "org-max", "capabilities": ["claude_max"]}]
DOC = {"limits": [{"kind": "session", "group": "session", "percent": 7,
                   "severity": "normal", "resets_at": "2026-08-27T19:30:00+00:00",
                   "scope": None}]}


def _app(poller):
    app = FastAPI()
    app.include_router(usage_router)
    app.state.usage_poller = poller
    return app


def _poller(accounts, *, fail=False):
    def transport(url, account):
        if fail:
            return None
        return ORGS if url.endswith("/organizations") else DOC

    return UsagePoller(interval=3600, client=UsageClient(transport=transport),
                       discover=lambda: accounts)


def test_the_route_is_registered_before_the_project_wildcards():
    from set_orch.api import router

    paths = [(i, r.path) for i, r in enumerate(router.routes)]
    usage = [i for i, p in paths if p.startswith("/api/usage")]
    wildcards = [i for i, p in paths if "{project" in p and not p.startswith("/api/fleet")]

    assert usage, "the usage router is not mounted at all"
    assert wildcards, "no project wildcard found — this test would pass vacuously"
    assert max(usage) < min(wildcards)


def test_no_account_state_lets_a_credential_into_the_body():
    """Asserted for every outcome, not for the happy one.

    An error path is where a payload most often grows a field somebody added to
    aid debugging, so the unreachable account is in this list on purpose.
    """
    accounts = [
        Account(name="alpha@example.invalid", kind=KIND_WEB, credential="sk-secret-web"),
        Account(name="beta@example.invalid", kind=KIND_CC, credential="tok-secret-cc"),
    ]
    good = _poller(accounts)
    good.refresh()
    bad = _poller(accounts, fail=True)
    bad.refresh()

    for poller in (good, bad):
        with TestClient(_app(poller)) as client:
            body = client.get("/api/usage/accounts").text
        assert "sk-secret-web" not in body
        assert "tok-secret-cc" not in body
        assert "sessionKey" not in body and "accessToken" not in body


def test_an_unconfigured_machine_answers_an_empty_list_not_an_error():
    poller = _poller([])
    poller.refresh()

    with TestClient(_app(poller)) as client:
        response = client.get("/api/usage/accounts")

    assert response.status_code == 200
    assert response.json()["accounts"] == []
    assert response.json()["measured_at"] is not None


def test_an_unconfigured_machine_and_an_unreachable_account_are_different_answers():
    """Both are "no figures". Only one of them is a failure."""
    empty = _poller([])
    empty.refresh()
    unreachable = _poller(
        [Account(name="alpha@example.invalid", kind=KIND_WEB, credential="sk-1")], fail=True)
    unreachable.refresh()

    with TestClient(_app(empty)) as client:
        empty_body = client.get("/api/usage/accounts").json()
    with TestClient(_app(unreachable)) as client:
        unreachable_body = client.get("/api/usage/accounts").json()

    assert empty_body["accounts"] == []
    assert [a["outcome"] for a in unreachable_body["accounts"]] == ["unreachable"]


def test_a_missing_poller_answers_200_and_says_so():
    """A broken server and an unmeasurable account must not look the same."""
    app = FastAPI()
    app.include_router(usage_router)
    app.state.usage_poller = None

    with TestClient(app) as client:
        response = client.get("/api/usage/accounts")

    assert response.status_code == 200
    assert response.json()["last_error"] == "poller-not-running"
    assert response.json()["measured_at"] is None


def test_reading_the_endpoint_issues_no_upstream_call():
    calls = {"n": 0}

    def transport(url, account):
        calls["n"] += 1
        return ORGS if url.endswith("/organizations") else DOC

    poller = UsagePoller(
        interval=3600, client=UsageClient(transport=transport),
        discover=lambda: [Account(name="alpha@example.invalid", kind=KIND_WEB, credential="sk-1")])
    poller.refresh()
    after_refresh = calls["n"]

    with TestClient(_app(poller)) as client:
        for _ in range(4):
            client.get("/api/usage/accounts")

    assert calls["n"] == after_refresh
