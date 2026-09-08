"""What the upstream answer means, and what it means when it carries nothing.

The documents below are the shapes measured live on 2026-08-27 — including the
one that matters most, an account that answered `200` with both of its windows
`null`. Every identifier is invented; only the structure is real.
"""

from __future__ import annotations

import json

import pytest

from set_orch.usage.accounts import Account, KIND_CC, KIND_WEB
from set_orch.usage.client import (
    OUTCOME_MEASURED,
    OUTCOME_UNMEASURED,
    OUTCOME_UNREACHABLE,
    UsageClient,
)

ORGS = [
    {"uuid": "org-plain", "capabilities": ["chat"]},
    {"uuid": "org-max", "capabilities": ["chat", "claude_max"]},
]

MEASURED_DOC = {
    "five_hour": {"utilization": 18.0, "resets_at": "2026-08-27T19:30:00+00:00"},
    "seven_day": {"utilization": 96.0, "resets_at": "2026-08-28T13:00:00+00:00"},
    "limits": [
        {"kind": "session", "group": "session", "percent": 18, "severity": "normal",
         "resets_at": "2026-08-27T19:30:00+00:00", "scope": None, "is_active": False},
        {"kind": "weekly_all", "group": "weekly", "percent": 96, "severity": "critical",
         "resets_at": "2026-08-28T13:00:00+00:00", "scope": None, "is_active": True},
        {"kind": "weekly_scoped", "group": "weekly", "percent": 2, "severity": "normal",
         "resets_at": "2026-08-28T13:00:00+00:00",
         "scope": {"model": {"id": None, "display_name": "Fable"}, "surface": None},
         "is_active": False},
    ],
}

#: Reachable, healthy, and unknown — the state this module exists to keep apart
#: from "consumed nothing". One of three live accounts answered exactly this.
NULL_WINDOW_DOC = {"five_hour": None, "seven_day": None}


def _account(kind=KIND_WEB, name="alpha@example.invalid", credential="sk-secret-value"):
    return Account(name=name, kind=kind, credential=credential)


class Transport:
    """A fake upstream that counts what it was asked for."""

    def __init__(self, usage_doc, orgs=None, fail_usage=False):
        self.usage_doc = usage_doc
        self.orgs = ORGS if orgs is None else orgs
        self.fail_usage = fail_usage
        self.calls: list[str] = []

    def __call__(self, url, account):
        self.calls.append(url)
        if url.endswith("/organizations"):
            return self.orgs
        if self.fail_usage:
            return None
        return self.usage_doc


def test_the_windows_reported_are_the_ones_the_document_carries():
    client = UsageClient(transport=Transport(MEASURED_DOC))

    usage = client.fetch(_account())

    assert usage.outcome == OUTCOME_MEASURED
    assert [(w.kind, w.utilization) for w in usage.windows] == [
        ("session", 18.0), ("weekly_all", 96.0), ("weekly_scoped", 2.0),
    ]


def test_the_organization_with_the_max_capability_is_chosen():
    transport = Transport(MEASURED_DOC)

    UsageClient(transport=transport).fetch(_account())

    assert transport.calls[1] == "https://claude.ai/api/organizations/org-max/usage"


def test_severity_comes_from_the_document_and_is_not_recomputed():
    """96 % arrived labelled critical; nobody here picked 96."""
    client = UsageClient(transport=Transport(MEASURED_DOC))

    windows = {w.kind: w for w in client.fetch(_account()).windows}

    assert windows["weekly_all"].severity == "critical"
    assert windows["session"].severity == "normal"


def test_a_scoped_window_keeps_its_scope_and_stays_apart_from_the_account_wide_one():
    client = UsageClient(transport=Transport(MEASURED_DOC))

    windows = {w.kind: w for w in client.fetch(_account()).windows}

    assert windows["weekly_scoped"].scope.model == "Fable"
    assert windows["weekly_all"].scope is None
    assert windows["weekly_scoped"].group == windows["weekly_all"].group == "weekly"


def test_no_scope_is_invented_where_the_document_states_none():
    doc = {"limits": [{"kind": "session", "group": "session", "percent": 5,
                       "severity": "normal", "resets_at": None, "scope": None}]}
    client = UsageClient(transport=Transport(doc))

    assert all(w.scope is None for w in client.fetch(_account()).windows)


def test_a_null_window_is_unmeasured_and_is_not_a_zero():
    client = UsageClient(transport=Transport(NULL_WINDOW_DOC))

    usage = client.fetch(_account())

    assert usage.outcome == OUTCOME_UNMEASURED
    assert [w.utilization for w in usage.windows] == [None, None]
    assert all(not w.measured for w in usage.windows)


def test_one_measured_window_beside_one_that_is_not():
    doc = {"five_hour": {"utilization": 0.0, "resets_at": "2026-08-27T19:30:00+00:00"},
           "seven_day": None}
    client = UsageClient(transport=Transport(doc))

    windows = client.fetch(_account()).windows

    assert windows[0].measured is True and windows[0].utilization == 0.0
    assert windows[1].measured is False


def test_a_measured_zero_is_not_the_same_as_an_unmeasured_window():
    """The whole distinction, in one assertion."""
    zero = UsageClient(transport=Transport(
        {"five_hour": {"utilization": 0}, "seven_day": {"utilization": 0}})).fetch(_account())
    absent = UsageClient(transport=Transport(NULL_WINDOW_DOC)).fetch(_account())

    assert zero.outcome == OUTCOME_MEASURED
    assert absent.outcome == OUTCOME_UNMEASURED


def test_a_failing_usage_read_is_unreachable_with_no_figures():
    client = UsageClient(transport=Transport(MEASURED_DOC, fail_usage=True))

    usage = client.fetch(_account())

    assert usage.outcome == OUTCOME_UNREACHABLE
    assert usage.windows == []


def test_a_failing_organization_lookup_is_unreachable():
    client = UsageClient(transport=Transport(MEASURED_DOC, orgs=None))
    client._transport = lambda url, account: None

    assert client.fetch(_account()).outcome == OUTCOME_UNREACHABLE


def test_the_organization_is_looked_up_once_and_then_cached():
    transport = Transport(MEASURED_DOC)
    client = UsageClient(transport=transport)
    account = _account()

    client.fetch(account)
    client.fetch(account)

    assert transport.calls.count("https://claude.ai/api/organizations") == 1


def test_two_accounts_sharing_a_NAME_do_not_share_an_organization():
    """Measured on the first live run of this module, and it failed silently.

    Three OAuth accounts resolved against the uuids their same-named browser
    accounts had just cached. Nothing errored at the lookup — it failed one step
    later, at the usage read, which is the shape that hides a cause: the log named
    the wrong step, and the uuid in flight belonged to a different credential.

    Since 2026-09-07 the OAuth account has no lookup at all — it reads the CLI
    endpoint, account-scoped by its own token — so the same-name pair now proves
    the narrower fact: the web account's organization stays the web account's,
    and the OAuth account's upstream does not touch the web path.
    """
    seen: list[tuple[str, str]] = []

    def transport(url, account):
        seen.append((account.kind, url))
        if url.endswith("/organizations"):
            return [{"uuid": f"org-{account.kind}", "capabilities": ["claude_max"]}]
        return MEASURED_DOC

    client = UsageClient(transport=transport)
    name = "shared@example.invalid"
    client.fetch(_account(kind=KIND_WEB, name=name))
    client.fetch(_account(kind=KIND_CC, name=name))

    usage_urls = [url for kind, url in seen if url.endswith("/usage")]
    assert usage_urls == [
        "https://claude.ai/api/organizations/org-web/usage",
        "https://api.anthropic.com/api/oauth/usage",
    ]
    # nothing of the web account's lookup leaks into the oauth path
    assert not any(kind == "cc" and "organizations" in url for kind, url in seen)


def test_a_rejected_usage_read_drops_the_cached_organization():
    transport = Transport(MEASURED_DOC, fail_usage=True)
    client = UsageClient(transport=transport)
    account = _account()

    client.fetch(account)
    client.fetch(account)

    assert transport.calls.count("https://claude.ai/api/organizations") == 2


def test_one_failing_account_does_not_shorten_the_answer():
    """A missing row reads as "not configured", which is a different fact."""
    def transport(url, account):
        if account.name == "broken@example.invalid":
            raise RuntimeError("transport exploded")
        if url.endswith("/organizations"):
            return ORGS
        return MEASURED_DOC

    client = UsageClient(transport=transport)
    accounts = [
        _account(name="alpha@example.invalid"),
        _account(name="broken@example.invalid"),
        _account(name="gamma@example.invalid"),
    ]

    results = client.fetch_all(accounts)

    assert [u.name for u in results] == [a.name for a in accounts]
    assert [u.outcome for u in results] == [
        OUTCOME_MEASURED, OUTCOME_UNREACHABLE, OUTCOME_MEASURED,
    ]


@pytest.mark.parametrize("doc", [MEASURED_DOC, NULL_WINDOW_DOC])
def test_no_serialised_record_carries_the_credential(doc):
    client = UsageClient(transport=Transport(doc))

    payload = json.dumps(client.fetch(_account(credential="sk-secret-value")).to_dict())

    assert "sk-secret-value" not in payload
    assert "sessionKey" not in payload and "accessToken" not in payload


def test_an_authentication_failure_is_logged_without_the_credential(caplog):
    client = UsageClient(transport=Transport(MEASURED_DOC, fail_usage=True))

    with caplog.at_level("DEBUG", logger="set_orch.usage.client"):
        client.fetch(_account(credential="sk-secret-value"))

    assert caplog.records
    assert "sk-secret-value" not in caplog.text


def test_an_oauth_account_reads_the_cli_endpoint_and_skips_the_organization_lookup():
    """Measured 2026-09-07: the claude.ai web API rejects a fresh, working CC
    bearer token with 403 at every endpoint — for this account the organizations
    lookup was a loop that never ended, three log lines a minute. The CC
    upstream is the CLI's own usage endpoint, account-scoped by the token."""
    transport = Transport(MEASURED_DOC)

    usage = UsageClient(transport=transport).fetch(_account(kind=KIND_CC))

    assert transport.calls == ["https://api.anthropic.com/api/oauth/usage"]
    assert usage.outcome == OUTCOME_MEASURED


def test_the_cli_endpoint_legacy_shape_parses_without_limits():
    """The CLI endpoint also answers without the banded form; the plain pair
    must keep carrying the figure (measured live: five_hour/seven_day at 200)."""
    legacy = {"five_hour": {"utilization": 32.0, "resets_at": "2026-09-08T00:50:00+00:00"},
              "seven_day": {"utilization": 73.0, "resets_at": "2026-09-11T13:00:00+00:00"}}

    usage = UsageClient(transport=Transport(legacy)).fetch(_account(kind=KIND_CC))

    assert [(w.kind, w.utilization) for w in usage.windows] == [
        ("session", 32.0), ("weekly_all", 73.0),
    ]


def test_an_oauth_failure_is_unreachable_without_an_organization_call():
    transport = Transport({}, fail_usage=True)

    usage = UsageClient(transport=transport).fetch(_account(kind=KIND_CC))

    assert usage.outcome == OUTCOME_UNREACHABLE
    assert transport.calls == ["https://api.anthropic.com/api/oauth/usage"]
