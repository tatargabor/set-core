"""The ChatGPT plan as a usage source — what it reports, and what it refuses to guess.

Two properties carry the weight. A window's group comes from its measured LENGTH,
never from the slot it arrived in, so a plan that reorders or adds a window cannot
relabel a weekly quota as a five-hour one. And a machine with no Codex login has
no account at all, which is a different fact from an account that did not answer.
"""

from __future__ import annotations

import json

import pytest

from set_orch.usage.astra import (
    ACCOUNT_NAME,
    KIND_ASTRA,
    USAGE_URL,
    AstraUsageClient,
    discover_astra_account,
)
from set_orch.usage.accounts import Account
from set_orch.usage.client import (
    OUTCOME_MEASURED,
    OUTCOME_UNMEASURED,
    OUTCOME_UNREACHABLE,
)


def _auth(tmp_path, **tokens):
    p = tmp_path / "auth.json"
    p.write_text(json.dumps({"tokens": {"access_token": "tok", "account_id": "acc", **tokens}}))
    return p


#: The live shape, measured 2026-09-08 against the real endpoint.
LIVE = {
    "plan_type": "plus",
    "rate_limit": {
        "allowed": True,
        "limit_reached": False,
        "primary_window": {"used_percent": 31, "limit_window_seconds": 18000,
                           "reset_at": 1788875586},
        "secondary_window": {"used_percent": 5, "limit_window_seconds": 604800,
                             "reset_at": 1789462386},
    },
}


class TestDiscovery:
    def test_a_login_is_an_account(self, tmp_path):
        accounts = discover_astra_account(_auth(tmp_path))
        assert len(accounts) == 1
        assert accounts[0].name == ACCOUNT_NAME
        assert accounts[0].kind == KIND_ASTRA
        assert accounts[0].credential == "tok"

    def test_no_login_is_no_account_not_a_dead_one(self, tmp_path):
        """Absent must not become a row that says 'did not answer'.

        A machine that never signed in has nothing to report; rendering it as
        unreachable would invite a purge of a credential that does not exist.
        """
        assert discover_astra_account(tmp_path / "nope.json") == []

    def test_a_login_without_an_access_token_is_not_an_account(self, tmp_path):
        p = tmp_path / "auth.json"
        p.write_text(json.dumps({"tokens": {"account_id": "acc"}}))
        assert discover_astra_account(p) == []

    def test_malformed_login_is_not_a_crash(self, tmp_path):
        """This runs once a minute; a broken file must not take the poller down."""
        p = tmp_path / "auth.json"
        p.write_text("{not json")
        assert discover_astra_account(p) == []


class TestTransport:
    def test_the_request_shape_is_asserted_not_believed(self, tmp_path):
        """A bearer token plus the account-id header, at the endpoint that answers.

        Pinned because two sibling endpoints answered 403 when probed and this
        one answered 200: an edit that 'tidies' the URL or the header changes
        what the upstream says, silently.
        """
        seen = {}

        def fake(url, token, account_id):
            seen.update(url=url, token=token, account_id=account_id)
            return LIVE

        account = discover_astra_account(_auth(tmp_path))[0]
        AstraUsageClient(transport=fake).fetch(account)
        assert seen["url"] == USAGE_URL
        assert seen["token"] == "tok"
        assert seen["account_id"] == "acc"


class TestParsing:
    def _fetch(self, document):
        client = AstraUsageClient(transport=lambda *a, **k: document)
        return client.fetch(Account(name=ACCOUNT_NAME, kind=KIND_ASTRA, credential="t"))

    def test_the_live_shape_measures_two_windows(self):
        usage = self._fetch(LIVE)
        assert usage.outcome == OUTCOME_MEASURED
        assert [w.utilization for w in usage.windows] == [31.0, 5.0]
        assert [w.group for w in usage.windows] == ["session", "weekly"]
        assert [w.window_seconds for w in usage.windows] == [18000, 604800]

    def test_the_group_comes_from_the_length_not_the_slot(self):
        """Swap the two windows and the groups must follow the LENGTHS.

        The slot names are positions, not meanings. Reading the group off the
        position would render a weekly quota under the five-hour label — a false
        value in the field a reader uses to decide whether to start more work.
        """
        swapped = {"rate_limit": {
            "limit_reached": False,
            "primary_window": {"used_percent": 5, "limit_window_seconds": 604800,
                               "reset_at": 1789462386},
            "secondary_window": {"used_percent": 31, "limit_window_seconds": 18000,
                                 "reset_at": 1788875586},
        }}
        usage = self._fetch(swapped)
        assert [w.group for w in usage.windows] == ["weekly", "session"]

    def test_limit_reached_outranks_the_band(self):
        """The upstream's own stop is stronger than any threshold we chose."""
        stopped = json.loads(json.dumps(LIVE))
        stopped["rate_limit"]["limit_reached"] = True
        usage = self._fetch(stopped)
        assert all(w.severity == "critical" for w in usage.windows)

    @pytest.mark.parametrize("percent,expected", [
        (10, None), (70, "warning"), (89, "warning"), (90, "critical"), (99, "critical"),
    ])
    def test_the_band_matches_the_one_the_other_source_documents(self, percent, expected):
        doc = {"rate_limit": {"limit_reached": False,
               "primary_window": {"used_percent": percent, "limit_window_seconds": 18000,
                                  "reset_at": 1788875586}}}
        assert self._fetch(doc).windows[0].severity == expected

    def test_an_answer_with_no_rate_limit_is_unmeasured_not_unreachable(self):
        """Answered-with-nothing and did-not-answer are different facts.

        Folding them together reports a live account as broken, which is the
        state that invites someone to delete a working credential.
        """
        assert self._fetch({"plan_type": "plus"}).outcome == OUTCOME_UNMEASURED

    def test_no_answer_at_all_is_unreachable(self):
        assert self._fetch(None).outcome == OUTCOME_UNREACHABLE

    def test_a_missing_percentage_is_none_never_zero(self):
        """`utilization: None` is the distinction this whole package exists for."""
        doc = {"rate_limit": {"limit_reached": False,
               "primary_window": {"limit_window_seconds": 18000, "reset_at": 1788875586}}}
        usage = self._fetch(doc)
        assert usage.windows[0].utilization is None
        assert usage.outcome == OUTCOME_UNMEASURED

    def test_reset_is_read_as_epoch_seconds(self):
        usage = self._fetch(LIVE)
        assert usage.windows[0].resets_at.startswith("2026-")

    def test_an_unparseable_reset_is_dropped_not_guessed(self):
        doc = {"rate_limit": {"limit_reached": False,
               "primary_window": {"used_percent": 5, "limit_window_seconds": 18000,
                                  "reset_at": "soon"}}}
        assert self._fetch(doc).windows[0].resets_at is None


class TestPollerContract:
    def test_the_client_answers_fetch_all(self):
        """The poller calls `fetch_all`; a client without it raises an
        AttributeError that the poller reports against the source's DISCOVER
        name — pointing a reader at the wrong half of the source. Measured here
        the first time this source was registered."""
        client = AstraUsageClient(transport=lambda *a, **k: LIVE)
        out = client.fetch_all([Account(name=ACCOUNT_NAME, kind=KIND_ASTRA, credential="t")])
        assert len(out) == 1 and out[0].outcome == OUTCOME_MEASURED

    def test_one_failing_account_removes_no_other(self):
        def boom(*a, **k):
            raise RuntimeError("upstream exploded")

        out = AstraUsageClient(transport=boom).fetch_all(
            [Account(name=ACCOUNT_NAME, kind=KIND_ASTRA, credential="t")])
        assert out[0].outcome == OUTCOME_UNREACHABLE

    def test_the_source_is_registered_on_this_machine(self):
        """A source nobody registered measures nothing, and says so to no one."""
        from set_orch.usage import default_sources

        names = [getattr(s.discover, "__name__", "") for s in default_sources()]
        assert "discover_astra_account" in names
