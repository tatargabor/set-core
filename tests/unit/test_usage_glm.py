"""The GLM source: discovery, the measured upstream shape, and the one local band.

Every fact these tests assert about the upstream was measured on 2026-08-29 —
the raw (no Bearer) Authorization header against z.ai's own plugin source, the
`CREDIT_LIMIT` document with epoch-millisecond reset times, and the absence of
any severity. When one of these tests fails, an upstream shape has moved.
"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace

from set_orch.usage.accounts import Account
from set_orch.usage.client import OUTCOME_MEASURED, OUTCOME_UNMEASURED, OUTCOME_UNREACHABLE
from set_orch.usage.glm import (
    KIND_GLM,
    QUOTA_PATH,
    discover_glm_account,
    monitor_base_url,
    GlmUsageClient,
)

TOKEN = "glm-token-abcdef"
BASE_URL = "https://api.z.ai/api/anthropic"

#: The live shape, scrubbed of nothing — these fields are not secret.
DOCUMENT = {
    "code": 200,
    "msg": "Operation successful",
    "success": True,
    "data": {
        "level": "max",
        "limits": [
            {"type": "CREDIT_LIMIT", "unit": 3, "number": 5, "usage": 28000,
             "currentValue": 264, "remaining": 27735, "percentage": 1,
             "nextResetTime": 1788044127711},
            {"type": "CREDIT_LIMIT", "unit": 6, "number": 1, "usage": 140000,
             "currentValue": 1101, "remaining": 138898, "percentage": 1,
             "nextResetTime": 1788602769998},
        ],
    },
}


def _provider_config(credential=None):
    """The slice of `ProvidersConfig` discovery reads, as a stand-in."""
    return SimpleNamespace(
        providers={"glm": SimpleNamespace(credential=credential)},
    )


def _credential():
    return SimpleNamespace(token=TOKEN, base_url=BASE_URL)


def _account() -> Account:
    return Account(name="GLM", kind=KIND_GLM, credential=TOKEN)


class RecordingTransport:
    def __init__(self, document=DOCUMENT, status="ok"):
        self.calls = []
        self.document = document
        self.status = status

    def __call__(self, url, token):
        self.calls.append({"url": url, "token": token})
        if self.status != "ok":
            return None
        return self.document


# ---- discovery ------------------------------------------------------------

def test_a_configured_glm_credential_is_discovered_with_its_kind():
    loader = lambda: (_provider_config(_credential()), None)
    accounts = discover_glm_account(loader=loader)

    assert len(accounts) == 1
    assert accounts[0].kind == KIND_GLM
    assert accounts[0].name == "GLM"
    assert accounts[0].credential == TOKEN


def test_a_machine_with_no_glm_provider_contributes_no_account():
    loader = lambda: (SimpleNamespace(providers={}), None)
    assert discover_glm_account(loader=loader) == []


def test_a_provider_without_a_credential_contributes_no_account():
    loader = lambda: (_provider_config(None), None)
    assert discover_glm_account(loader=loader) == []


def test_a_provider_config_that_cannot_be_read_is_not_an_account_and_does_not_raise():
    def loader():
        raise RuntimeError("no providers.json here")

    assert discover_glm_account(loader=loader) == []


def test_the_discovery_repr_carries_no_credential():
    loader = lambda: (_provider_config(_credential()), None)
    accounts = discover_glm_account(loader=loader)

    assert TOKEN not in repr(accounts)


def test_the_monitor_host_is_derived_from_the_credential_base_url():
    assert monitor_base_url(BASE_URL) == "https://api.z.ai"
    assert monitor_base_url("https://open.bigmodel.cn/api/anthropic") == "https://open.bigmodel.cn"
    assert monitor_base_url("not a url") is None
    assert monitor_base_url("no-scheme.example.com") is None


# ---- transport ------------------------------------------------------------

def test_the_quota_endpoint_is_read_with_the_raw_token_and_no_bearer_prefix():
    """The header shape is a measured property of the upstream, not a style.

    A well-meaning later edit that prefixes `Bearer ` changes what the endpoint
    answers; this assertion is the guard against exactly that edit.
    """
    transport = RecordingTransport()
    client = GlmUsageClient(transport=transport, resolve_base=lambda a: "https://api.z.ai")

    client.fetch(_account())

    assert len(transport.calls) == 1
    assert transport.calls[0]["url"] == f"https://api.z.ai{QUOTA_PATH}"
    assert transport.calls[0]["token"] == TOKEN
    assert "Bearer" not in transport.calls[0]["token"]


def test_a_transport_failure_is_unreachable():
    transport = RecordingTransport(status="down")
    client = GlmUsageClient(transport=transport, resolve_base=lambda a: "https://api.z.ai")

    usage = client.fetch(_account())

    assert usage.outcome == OUTCOME_UNREACHABLE
    assert usage.windows == []


def test_a_base_url_without_a_host_is_unreachable_not_a_crash():
    client = GlmUsageClient(transport=RecordingTransport(), resolve_base=lambda a: None)

    usage = client.fetch(_account())

    assert usage.outcome == OUTCOME_UNREACHABLE


def test_one_failing_account_does_not_shorten_the_answer():
    def transport(url, token):
        raise RuntimeError("socket exploded")

    client = GlmUsageClient(transport=transport, resolve_base=lambda a: "https://api.z.ai")
    accounts = [_account(), Account(name="GLM-2", kind=KIND_GLM, credential="t2")]

    out = client.fetch_all(accounts)

    assert [u.name for u in out] == ["GLM", "GLM-2"]
    assert all(u.outcome == OUTCOME_UNREACHABLE for u in out)


# ---- windows --------------------------------------------------------------

def _client(document=DOCUMENT):
    return GlmUsageClient(transport=RecordingTransport(document=document),
                          resolve_base=lambda a: "https://api.z.ai")


def test_the_windows_reported_are_the_ones_the_document_carries():
    usage = _client().fetch(_account())

    assert usage.outcome == OUTCOME_MEASURED
    assert len(usage.windows) == 2
    assert all(w.kind == "CREDIT_LIMIT" for w in usage.windows)


def test_the_five_hour_window_maps_to_the_session_group_and_its_real_length():
    usage = _client().fetch(_account())

    session = usage.windows[0]
    assert session.group == "session"
    assert session.window_seconds == 5 * 3600
    assert session.scope is None


def test_the_weekly_window_maps_to_the_weekly_group():
    usage = _client().fetch(_account())

    weekly = usage.windows[1]
    assert weekly.group == "weekly"
    assert weekly.window_seconds == 7 * 24 * 3600


def test_an_unknown_limit_type_is_kept_as_its_own_kind_and_not_dropped():
    document = json.loads(json.dumps(DOCUMENT))
    document["data"]["limits"].append(
        {"type": "SOMETHING_NEW", "unit": 4, "number": 2, "percentage": 5}
    )
    usage = _client(document).fetch(_account())

    kinds = [w.kind for w in usage.windows]
    assert "SOMETHING_NEW" in kinds


def test_an_unknown_unit_keeps_its_group_but_draws_no_elapsed_stripe():
    document = json.loads(json.dumps(DOCUMENT))
    document["data"]["limits"] = [
        {"type": "CREDIT_LIMIT", "unit": 9, "number": 9, "percentage": 5}
    ]
    window = _client(document).fetch(_account()).windows[0]

    assert window.group == "unit9x9"
    assert window.window_seconds is None
    assert window.resets_at is None or window.resets_at  # reset is orthogonal


def test_a_millisecond_reset_time_is_reported_as_iso_utc():
    usage = _client().fetch(_account())

    assert usage.windows[0].resets_at == "2026-08-29T22:55:27.711000+00:00"
    assert usage.windows[1].resets_at == "2026-09-05T10:06:09.998000+00:00"


def test_a_plausibly_second_reset_time_is_not_misdated_by_three_orders():
    document = json.loads(json.dumps(DOCUMENT))
    document["data"]["limits"][0]["nextResetTime"] = 1788044127  # seconds, not ms
    window = _client(document).fetch(_account()).windows[0]

    assert window.resets_at == "2026-08-29T22:55:27+00:00"


def test_a_reset_time_that_cannot_be_parsed_is_none():
    document = json.loads(json.dumps(DOCUMENT))
    document["data"]["limits"][0]["nextResetTime"] = "soon"
    window = _client(document).fetch(_account()).windows[0]

    assert window.resets_at is None


# ---- the one band ---------------------------------------------------------

def _window_at(percentage):
    document = json.loads(json.dumps(DOCUMENT))
    document["data"]["limits"] = [
        {"type": "CREDIT_LIMIT", "unit": 3, "number": 5, "percentage": percentage}
    ]
    return _client(document).fetch(_account()).windows[0]


def test_severity_is_banded_locally_because_upstream_states_none():
    assert _window_at(90).severity == "critical"
    assert _window_at(96).severity == "critical"
    assert _window_at(70).severity == "warning"
    assert _window_at(89).severity == "warning"
    assert _window_at(12).severity is None


def test_a_window_without_a_percentage_is_unmeasured_and_is_not_a_zero():
    window = _window_at(None)

    assert window.utilization is None
    assert window.severity is None
    assert not window.measured


def test_a_measured_zero_is_distinct_from_an_unmeasured_window():
    measured = _window_at(0)
    unmeasured = _window_at(None)

    assert measured.utilization == 0.0 and measured.measured
    assert unmeasured.utilization is None and not unmeasured.measured


# ---- outcomes -------------------------------------------------------------

def test_a_rejected_answer_is_unreachable_with_no_figures():
    document = json.loads(json.dumps(DOCUMENT))
    document["success"] = False
    usage = _client(document).fetch(_account())

    assert usage.outcome == OUTCOME_UNREACHABLE
    assert usage.windows == []


def test_a_document_without_limits_is_unmeasured_not_unreachable():
    document = {"code": 200, "success": True, "data": {"level": "max"}}
    usage = _client(document).fetch(_account())

    assert usage.outcome == OUTCOME_UNMEASURED


def test_a_non_document_answer_is_unreachable():
    usage = _client(["not", "a", "document"]).fetch(_account())

    assert usage.outcome == OUTCOME_UNREACHABLE


# ---- the credential does not travel ---------------------------------------

def test_no_serialised_record_carries_the_credential():
    usage = _client().fetch(_account())
    rendered = json.dumps(usage.to_dict(), default=str)

    assert TOKEN not in rendered
    assert TOKEN not in repr(usage)


def test_an_authentication_failure_is_logged_without_the_credential(caplog):
    client = GlmUsageClient(transport=RecordingTransport(status="down"),
                            resolve_base=lambda a: None)

    with caplog.at_level(logging.DEBUG, logger="set_orch.usage.glm"):
        client.fetch(_account())

    assert TOKEN not in caplog.text
