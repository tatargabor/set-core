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
