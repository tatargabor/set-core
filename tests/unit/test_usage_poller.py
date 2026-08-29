"""That reading is free, and that a failed refresh does not erase a good answer.

The call count is asserted on a fake transport rather than timed. A timing
assertion would pass on a machine that was merely slow, and fail on one that was
fast — measuring the harness instead of the code.
"""

from __future__ import annotations

from set_orch.usage.accounts import Account, KIND_WEB
from set_orch.usage.client import OUTCOME_MEASURED, UsageClient
from set_orch.usage.poller import UsagePoller

ORGS = [{"uuid": "org-max", "capabilities": ["claude_max"]}]
DOC = {"limits": [{"kind": "session", "group": "session", "percent": 12,
                   "severity": "normal", "resets_at": "2026-08-27T19:30:00+00:00",
                   "scope": None}]}


class CountingTransport:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def __call__(self, url, account):
        self.calls += 1
        if self.fail:
            return None
        return ORGS if url.endswith("/organizations") else DOC


def _poller(transport):
    accounts = [Account(name="alpha@example.invalid", kind=KIND_WEB, credential="sk-1")]
    return UsagePoller(interval=3600, client=UsageClient(transport=transport),
                       discover=lambda: accounts)


def test_reads_between_two_polls_make_no_upstream_call():
    transport = CountingTransport()
    poller = _poller(transport)
    poller.refresh()
    after_first = transport.calls

    for _ in range(5):
        poller.snapshot()

    assert transport.calls == after_first


def test_the_snapshot_carries_when_it_was_measured():
    poller = _poller(CountingTransport())
    assert poller.snapshot()["measured_at"] is None

    poller.refresh()

    assert poller.snapshot()["measured_at"] is not None


def test_a_failed_refresh_keeps_the_earlier_figures_and_their_timestamp():
    """A stale measurement beats none — and the reader can see which it is."""
    transport = CountingTransport()
    poller = _poller(transport)
    poller.refresh()
    good = poller.snapshot()

    transport.fail = True
    poller.refresh()
    after = poller.snapshot()

    # The account is now reported unreachable, but the ANSWER still stands with
    # the moment it was taken — nothing was replaced by an error.
    assert after["measured_at"] >= good["measured_at"]
    assert after["accounts"]


def test_a_raising_discovery_leaves_the_previous_answer_untouched():
    transport = CountingTransport()
    poller = _poller(transport)
    poller.refresh()
    good = poller.snapshot()

    def explode():
        raise RuntimeError("store vanished")

    poller._discover = explode
    poller.refresh()
    after = poller.snapshot()

    assert after["accounts"] == good["accounts"]
    assert after["measured_at"] == good["measured_at"]
    assert after["last_error"] == "RuntimeError"


def test_the_first_snapshot_distinguishes_never_measured_from_no_accounts():
    poller = UsagePoller(interval=3600, client=UsageClient(transport=CountingTransport()),
                         discover=lambda: [])

    before = poller.snapshot()
    poller.refresh()
    after = poller.snapshot()

    assert before["measured_at"] is None and before["accounts"] == []
    assert after["measured_at"] is not None and after["accounts"] == []


def test_a_refresh_reports_the_measured_outcome():
    poller = _poller(CountingTransport())

    poller.refresh()

    assert poller.snapshot()["accounts"][0]["outcome"] == OUTCOME_MEASURED


# ---- sources --------------------------------------------------------------

from set_orch.usage.poller import UsageSource  # noqa: E402


class StaticSource:
    """A source whose discover/client behaviour the test pins per case."""

    def __init__(self, name, accounts=None, fail_discovery=False, client=None):
        self.name = name
        self._accounts = accounts or []
        self._fail = fail_discovery
        self.client = client

    def discover(self):
        if self._fail:
            raise RuntimeError("store vanished")
        return self._accounts


class OkClient:
    def __init__(self, names):
        self.names = names

    def fetch_all(self, accounts):
        return [SimpleUsage(n) for n in self.names]


class SimpleUsage:
    def __init__(self, name):
        self.name = name
        self.kind = "web"
        self.outcome = "measured"
        self.windows = []
        self.active = False

    def to_dict(self):
        return {"name": self.name, "kind": self.kind, "outcome": self.outcome,
                "active": self.active, "windows": self.windows}


def test_two_sources_both_reach_the_snapshot():
    sources = [
        UsageSource(discover=lambda: [Account(name="a", kind=KIND_WEB, credential="t")],
                   client=OkClient(["a"])),
        UsageSource(discover=lambda: [Account(name="b", kind=KIND_WEB, credential="t")],
                   client=OkClient(["b"])),
    ]
    poller = UsagePoller(interval=3600, sources=sources)

    poller.refresh()

    names = [a["name"] for a in poller.snapshot()["accounts"]]
    assert names == ["a", "b"]
    assert poller.snapshot()["last_error"] is None


def test_one_source_raising_does_not_remove_the_other_sources_accounts():
    sources = [
        UsageSource(discover=StaticSource("dead", fail_discovery=True).discover,
                   client=OkClient([])),
        UsageSource(discover=lambda: [Account(name="b", kind=KIND_WEB, credential="t")],
                   client=OkClient(["b"])),
    ]
    poller = UsagePoller(interval=3600, sources=sources)

    poller.refresh()
    snap = poller.snapshot()

    assert [a["name"] for a in snap["accounts"]] == ["b"]
    assert snap["last_error"] == "RuntimeError"
    assert snap["measured_at"] is not None, "the surviving source still stamps a fresh time"


def test_one_source_raising_keeps_that_sources_previous_figures():
    healthy = UsageSource(discover=lambda: [Account(name="b", kind=KIND_WEB, credential="t")],
                          client=OkClient(["b"]))
    flaky_accounts = [Account(name="a", kind=KIND_WEB, credential="t")]
    flaky = StaticSource("flaky", accounts=flaky_accounts, client=OkClient(["a"]))
    sources = [UsageSource(discover=flaky.discover, client=flaky.client), healthy]
    poller = UsagePoller(interval=3600, sources=sources)

    poller.refresh()
    good = poller.snapshot()

    flaky._fail = True
    poller.refresh()
    after = poller.snapshot()

    names = [a["name"] for a in after["accounts"]]
    assert names == ["a", "b"], "the flaky source keeps its last measured accounts"
    assert after["measured_at"] >= good["measured_at"]


def test_every_source_raising_keeps_the_timestamp_of_the_last_measurement():
    flaky = StaticSource("flaky", accounts=[Account(name="a", kind=KIND_WEB, credential="t")],
                         client=OkClient(["a"]))
    poller = UsagePoller(interval=3600,
                         sources=[UsageSource(discover=flaky.discover, client=flaky.client)])

    poller.refresh()
    good = poller.snapshot()

    flaky._fail = True
    poller.refresh()
    after = poller.snapshot()

    assert after["accounts"] == good["accounts"]
    assert after["measured_at"] == good["measured_at"], "a true-but-old measurement beats none"
    assert after["last_error"] == "RuntimeError"


def test_the_default_source_list_contains_no_provider_backed_source():
    """The guard against a GLM default sneaking into the poller.

    A default here would make every existing poller test read this machine's
    real provider configuration, which carries a live credential.
    """
    from set_orch.usage import default_sources

    poller = UsagePoller(interval=3600, client=UsageClient(transport=CountingTransport()),
                         discover=lambda: [])
    assert len(poller._sources) == 1
    assert poller._sources[0].discover() == []

    sources = default_sources()
    assert len(sources) == 2
    assert all(not hasattr(s, "credential") for s in sources)
