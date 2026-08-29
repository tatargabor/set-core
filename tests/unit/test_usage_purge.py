"""Purging dead accounts from the credential stores, at the store and at the route.

The store tests pin what happens to the FILES; the route tests pin the
unreachable-only guard. The two halves exist because the guard is what makes the
endpoint safe and the store semantics are what make it correct — a test suite
that pinned only the route would pass while a store regressed.
"""

from __future__ import annotations

import json
import os
import stat

from fastapi import FastAPI
import set_orch.api.usage as usage_api
from fastapi.testclient import TestClient

from set_orch.api.usage import router as usage_router
from set_orch.usage.accounts import (
    KIND_CC,
    KIND_WEB,
    Account,
    discover_accounts,
    purge_accounts,
)
from set_orch.usage.client import UsageClient
from set_orch.usage.poller import UsagePoller

TOKEN_WEB = "sk-secret-web-token"
TOKEN_CC = "tok-secret-cc-token"


# ---- the browser session store -------------------------------------------

def _web_store(tmp_path, entries):
    path = tmp_path / "claude-session.json"
    path.write_text(json.dumps({"accounts": entries}))
    os.chmod(path, 0o600)
    return path


def test_a_dead_web_account_is_removed_from_the_store(tmp_path):
    _web_store(tmp_path, [
        {"name": "dead@example.invalid", "sessionKey": TOKEN_WEB},
        {"name": "alive@example.invalid", "sessionKey": "sk-other"},
    ])

    answer = purge_accounts([{"kind": KIND_WEB, "name": "dead@example.invalid"}],
                            directory=tmp_path)

    assert answer["removed"] == 1 and answer["refused"] == 0
    survivors = discover_accounts(tmp_path)
    assert [a.name for a in survivors] == ["alive@example.invalid"]
    assert TOKEN_WEB not in (tmp_path / "claude-session.json").read_text()


def test_the_store_is_written_back_atomically_in_the_current_shape(tmp_path):
    """A purge must never regress the store to the legacy single-key form."""
    path = _web_store(tmp_path, [
        {"name": "a@x.invalid", "sessionKey": "sk-1"},
        {"name": "b@x.invalid", "sessionKey": "sk-2"},
    ])
    purge_accounts([{"kind": KIND_WEB, "name": "a@x.invalid"}], directory=tmp_path)

    data = json.loads(path.read_text())
    assert set(data.keys()) == {"accounts"}
    assert [e["name"] for e in data["accounts"]] == ["b@x.invalid"]


def test_owner_only_permissions_survive_a_purge(tmp_path):
    path = _web_store(tmp_path, [{"name": "a@x.invalid", "sessionKey": "sk-1"}])

    purge_accounts([{"kind": KIND_WEB, "name": "a@x.invalid"}], directory=tmp_path)

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_every_entry_under_a_name_goes_together(tmp_path):
    """The name is the identity the strip displayed and the operator confirmed."""
    _web_store(tmp_path, [
        {"name": "dup@x.invalid", "sessionKey": "sk-1"},
        {"name": "dup@x.invalid", "sessionKey": "sk-2", "source": "chrome-scan"},
    ])
    answer = purge_accounts([{"kind": KIND_WEB, "name": "dup@x.invalid"}], directory=tmp_path)

    assert answer["removed"] == 1
    assert discover_accounts(tmp_path) == []


def test_an_entry_the_store_does_not_have_is_refused_not_removed(tmp_path):
    _web_store(tmp_path, [{"name": "a@x.invalid", "sessionKey": "sk-1"}])

    answer = purge_accounts([{"kind": KIND_WEB, "name": "ghost@x.invalid"}], directory=tmp_path)

    assert answer["removed"] == 0 and answer["refused"] == 1
    assert "ghost" in answer["results"][0]["reason"]


def test_the_legacy_single_key_store_purges_as_default(tmp_path):
    path = tmp_path / "claude-session.json"
    path.write_text(json.dumps({"sessionKey": TOKEN_WEB}))
    os.chmod(path, 0o600)

    answer = purge_accounts([{"kind": KIND_WEB, "name": "Default"}], directory=tmp_path)

    assert answer["removed"] == 1
    assert json.loads(path.read_text()) == {"accounts": []}


# ---- the CLI OAuth store ---------------------------------------------------

class FakePool:
    """The store rules `set_router.AccountPool` enforces, as a stand-in."""

    def __init__(self, emails, refuse_reason=None):
        self.emails = list(emails)
        self.removed = []
        self.refuse_reason = refuse_reason

    def remove(self, email):
        if email not in self.emails:
            raise KeyError(f"Account '{email}' not found")
        if len(self.emails) <= 1:
            raise ValueError("Cannot remove the last account")
        if self.refuse_reason:
            raise ValueError(self.refuse_reason)
        self.removed.append(email)
        self.emails.remove(email)
        return f"Removed account '{email}'"


def test_a_dead_cc_account_is_removed_through_the_pool_rules(tmp_path):
    pool = FakePool(["a@x.invalid", "b@x.invalid"])

    answer = purge_accounts([{"kind": KIND_CC, "name": "a@x.invalid"}],
                            directory=tmp_path, pool=pool)

    assert answer["removed"] == 1
    assert pool.removed == ["a@x.invalid"]


def test_the_last_cc_account_is_refused_by_the_store_rule(tmp_path):
    pool = FakePool(["only@x.invalid"])

    answer = purge_accounts([{"kind": KIND_CC, "name": "only@x.invalid"}],
                            directory=tmp_path, pool=pool)

    assert answer["removed"] == 0 and answer["refused"] == 1
    assert "last" in answer["results"][0]["reason"].lower() or "only" in answer["results"][0]["reason"]


def test_a_cc_account_the_pool_does_not_know_is_refused(tmp_path):
    pool = FakePool(["a@x.invalid"])

    answer = purge_accounts([{"kind": KIND_CC, "name": "ghost@x.invalid"}],
                            directory=tmp_path, pool=pool)

    assert answer["refused"] == 1
    assert "ghost" in answer["results"][0]["reason"]


def test_an_active_cc_account_removal_reports_what_became_active(tmp_path):
    pool = FakePool(["active@x.invalid", "other@x.invalid"])
    pool.remove = lambda email: (
        f"Removed '{email}'. Switched to 'other@x.invalid'")

    answer = purge_accounts([{"kind": KIND_CC, "name": "active@x.invalid"}],
                            directory=tmp_path, pool=pool)

    assert answer["removed"] == 1
    assert "other@x.invalid" in answer["results"][0].get("detail", "")


# ---- the provider refusal and the mixed answer -----------------------------

def test_a_glm_account_is_refused_and_providers_json_is_never_touched(tmp_path):
    answer = purge_accounts([{"kind": "glm", "name": "GLM"}], directory=tmp_path)

    assert answer["refused"] == 1
    assert "providers.json" in answer["results"][0]["reason"]
    assert not (tmp_path / "providers.json").exists()


def test_a_mixed_request_removes_and_refuses_independently(tmp_path):
    _web_store(tmp_path, [{"name": "dead@x.invalid", "sessionKey": "sk-1"}])
    pool = FakePool(["cc@x.invalid", "keep@x.invalid"])  # two: the last-account rule holds

    answer = purge_accounts(
        [
            {"kind": KIND_WEB, "name": "dead@x.invalid"},
            {"kind": KIND_CC, "name": "cc@x.invalid"},
            {"kind": "glm", "name": "GLM"},
            {"kind": "martian", "name": "?"},
        ],
        directory=tmp_path, pool=pool)

    assert answer["removed"] == 2
    assert answer["refused"] == 2
    assert [r["outcome"] for r in answer["results"]] == [
        "removed", "removed", "refused", "refused"]


def test_no_credential_travels_in_the_answer(tmp_path):
    _web_store(tmp_path, [{"name": "a@x.invalid", "sessionKey": TOKEN_WEB}])
    pool = FakePool(["cc@x.invalid"])

    answer = purge_accounts(
        [
            {"kind": KIND_WEB, "name": "a@x.invalid"},
            {"kind": KIND_CC, "name": "cc@x.invalid"},
        ],
        directory=tmp_path, pool=pool)
    rendered = json.dumps(answer)

    assert TOKEN_WEB not in rendered
    assert TOKEN_CC not in rendered
    assert "sessionKey" not in rendered and "accessToken" not in rendered


# ---- the route: the unreachable-only guard ---------------------------------

DOC = {"limits": [{"kind": "session", "group": "session", "percent": 7,
                   "severity": "normal", "resets_at": "2026-08-27T19:30:00+00:00",
                   "scope": None}]}


def _app_with(poller):
    app = FastAPI()
    app.include_router(usage_router)
    app.state.usage_poller = poller
    return app


def _poller(accounts):
    """A poller whose measurement makes every account unreachable."""

    def transport(url, account):
        return None  # everything fails: every account ends up unreachable

    poller = UsagePoller(interval=3600, client=UsageClient(transport=transport),
                         discover=lambda: accounts)
    poller.refresh()
    return poller


def _healthy_poller(accounts):
    def transport(url, account):
        return ORGS if url.endswith("/organizations") else DOC

    poller = UsagePoller(interval=3600, client=UsageClient(transport=transport),
                         discover=lambda: accounts)
    poller.refresh()
    return poller


ORGS = [{"uuid": "org-max", "capabilities": ["claude_max"]}]


def test_the_route_removes_an_account_the_snapshot_shows_dead(monkeypatch):
    """The store half is stubbed here: the route's own job is the guard, and a
    real `AccountPool` read would make this test depend on this machine's
    actual credential store."""
    removed = []

    def fake_purge(targets, *args, **kwargs):
        removed.extend(targets)
        return {"results": [{**t, "outcome": "removed"} for t in targets],
                "removed": len(targets), "refused": 0}

    monkeypatch.setattr(usage_api, "purge_accounts", fake_purge)
    poller = _poller([Account(name="cc@x.invalid", kind=KIND_CC, credential=TOKEN_CC)])

    with TestClient(_app_with(poller)) as client:
        response = client.post("/api/usage/accounts/purge",
                               json={"accounts": [{"kind": KIND_CC, "name": "cc@x.invalid"}]})

    assert response.status_code == 200
    assert response.json()["removed"] == 1
    assert removed == [{"kind": KIND_CC, "name": "cc@x.invalid"}]


def test_the_route_refuses_a_healthy_account(tmp_path):
    poller = _healthy_poller([Account(name="a@x.invalid", kind=KIND_WEB, credential="sk-1")])

    with TestClient(_app_with(poller)) as client:
        response = client.post("/api/usage/accounts/purge",
                               json={"accounts": [{"kind": KIND_WEB, "name": "a@x.invalid"}]})

    body = response.json()
    assert body["removed"] == 0 and body["refused"] == 1
    assert "does not show this account as dead" in body["results"][0]["reason"]


def test_the_route_refuses_a_name_the_measurement_does_not_carry(tmp_path):
    poller = _healthy_poller([Account(name="a@x.invalid", kind=KIND_WEB, credential="sk-1")])

    with TestClient(_app_with(poller)) as client:
        response = client.post("/api/usage/accounts/purge",
                               json={"accounts": [{"kind": KIND_WEB, "name": "ghost@x.invalid"}]})

    assert response.json()["refused"] == 1
    assert "carries no account" in response.json()["results"][0]["reason"]


def test_the_route_refuses_glm_and_names_where_the_credential_lives(tmp_path):
    poller = _poller([Account(name="GLM", kind="glm", credential="glm-tok")])

    with TestClient(_app_with(poller)) as client:
        response = client.post("/api/usage/accounts/purge",
                               json={"accounts": [{"kind": "glm", "name": "GLM"}]})

    body = response.json()
    assert body["refused"] == 1
    assert "providers.json" in body["results"][0]["reason"]


def test_a_mixed_route_request_removes_the_dead_and_names_the_refused(monkeypatch):
    monkeypatch.setattr(
        usage_api, "purge_accounts",
        lambda targets, *a, **k: {
            "results": [{**t, "outcome": "removed"} for t in targets],
            "removed": len(targets), "refused": 0})
    accounts = [
        Account(name="dead@x.invalid", kind=KIND_WEB, credential="sk-dead"),
        Account(name="alive@x.invalid", kind=KIND_WEB, credential="sk-alive"),
    ]
    # One unreachable and one healthy is not expressible with a single transport,
    # so the guard's mixed case here is: one dead + one the snapshot never carried.
    poller = _poller(accounts)

    with TestClient(_app_with(poller)) as client:
        response = client.post("/api/usage/accounts/purge", json={"accounts": [
            {"kind": KIND_WEB, "name": "dead@x.invalid"},
            {"kind": KIND_WEB, "name": "unknown@x.invalid"},
        ]})

    body = response.json()
    assert body["removed"] == 1
    assert body["refused"] == 1
    assert body["results"][0]["outcome"] == "removed"
    assert body["results"][1]["outcome"] == "refused"


def test_a_purge_request_without_a_poller_removes_nothing(tmp_path):
    app = FastAPI()
    app.include_router(usage_router)
    app.state.usage_poller = None

    with TestClient(app) as client:
        response = client.post("/api/usage/accounts/purge",
                               json={"accounts": [{"kind": KIND_WEB, "name": "a@x.invalid"}]})

    body = response.json()
    assert body["removed"] == 0 and body["refused"] == 1
    assert "no measurement is running" in body["results"][0]["reason"]


def test_the_purge_answer_never_carries_a_credential(tmp_path, monkeypatch):
    # Stub the store half so the assertion is about the answer's shape, and no
    # test ever reads this machine's real credential store.
    monkeypatch.setattr(
        usage_api, "purge_accounts",
        lambda targets, *a, **k: {
            "results": [{"kind": t["kind"], "name": t["name"],
                         "outcome": "removed" if t["kind"] != "glm" else "refused",
                         "reason": "x" if t["kind"] != "glm" else "providers.json"}
                        for t in targets],
            "removed": sum(1 for t in targets if t["kind"] != "glm"),
            "refused": sum(1 for t in targets if t["kind"] == "glm")})
    poller = _poller([Account(name="cc@x.invalid", kind=KIND_CC, credential=TOKEN_CC),
                      Account(name="GLM", kind="glm", credential="glm-secret-token")])

    with TestClient(_app_with(poller)) as client:
        body = client.post("/api/usage/accounts/purge", json={"accounts": [
            {"kind": KIND_CC, "name": "cc@x.invalid"},
            {"kind": "glm", "name": "GLM"},
        ]}).text

    assert TOKEN_CC not in body
    assert "glm-secret-token" not in body
    assert "sessionKey" not in body and "accessToken" not in body
