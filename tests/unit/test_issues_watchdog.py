"""Tests for lib/set_orch/issues/watchdog.py — diagnosed-timeout watchdog."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.issues.models import (
    DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS,
    Issue,
    IssueState,
)
from set_orch.issues.registry import IssueRegistry
from set_orch.issues.watchdog import (
    _reset_watchdog_state_for_tests,
    check_diagnosed_timeouts,
)


@pytest.fixture(autouse=True)
def _clean_watchdog_state():
    _reset_watchdog_state_for_tests()
    yield
    _reset_watchdog_state_for_tests()


def _iso(dt: datetime) -> str:
    return dt.astimezone().isoformat(timespec="seconds")


def _make_issue(
    id: str,
    *,
    state: IssueState = IssueState.DIAGNOSED,
    diagnosed_at: str | None = None,
    affected_change: str = "foo",
) -> Issue:
    return Issue(
        id=id,
        environment="test",
        environment_path="/tmp/proj",
        source="sentinel",
        state=state,
        error_summary="test",
        affected_change=affected_change,
        diagnosed_at=diagnosed_at,
    )


class FakeBus:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def emit(self, event_type: str, **kwargs) -> None:
        self.events.append((event_type, kwargs))


class TestDiagnosedTimeoutWatchdog:
    def test_stuck_past_timeout_emits_event(self, tmp_path):
        registry = IssueRegistry(tmp_path)
        old = datetime.now(timezone.utc) - timedelta(seconds=DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS + 60)
        registry.add(_make_issue("ISS-001", diagnosed_at=_iso(old)))

        bus = FakeBus()
        hits = check_diagnosed_timeouts(tmp_path, event_bus=bus)
        assert len(hits) == 1
        assert hits[0]["issue_id"] == "ISS-001"
        assert hits[0]["change"] == "foo"
        assert hits[0]["age_seconds"] >= DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS
        assert len(bus.events) == 1
        assert bus.events[0][0] == "ISSUE_DIAGNOSED_TIMEOUT"

    def test_fresh_diagnosed_issue_no_fire(self, tmp_path):
        registry = IssueRegistry(tmp_path)
        now = datetime.now(timezone.utc)
        registry.add(_make_issue("ISS-001", diagnosed_at=_iso(now)))

        bus = FakeBus()
        hits = check_diagnosed_timeouts(tmp_path, event_bus=bus)
        assert hits == []
        assert bus.events == []

    def test_non_diagnosed_issue_ignored(self, tmp_path):
        registry = IssueRegistry(tmp_path)
        old = datetime.now(timezone.utc) - timedelta(seconds=DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS + 60)
        registry.add(_make_issue("ISS-001", state=IssueState.RESOLVED, diagnosed_at=_iso(old)))
        registry.add(_make_issue("ISS-002", state=IssueState.FIXING, diagnosed_at=_iso(old)))

        hits = check_diagnosed_timeouts(tmp_path, event_bus=FakeBus())
        assert hits == []

    def test_dedup_across_calls(self, tmp_path):
        registry = IssueRegistry(tmp_path)
        old = datetime.now(timezone.utc) - timedelta(seconds=DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS + 60)
        registry.add(_make_issue("ISS-001", diagnosed_at=_iso(old)))

        state: dict = {}
        hits1 = check_diagnosed_timeouts(tmp_path, event_bus=FakeBus(), state=state)
        hits2 = check_diagnosed_timeouts(tmp_path, event_bus=FakeBus(), state=state)
        assert len(hits1) == 1
        assert hits2 == []
        assert state["diagnosed_timeout_seen"] == ["ISS-001"]

    def test_custom_timeout(self, tmp_path):
        registry = IssueRegistry(tmp_path)
        old = datetime.now(timezone.utc) - timedelta(seconds=120)
        registry.add(_make_issue("ISS-001", diagnosed_at=_iso(old)))

        hits = check_diagnosed_timeouts(
            tmp_path, timeout_secs=60, event_bus=FakeBus(),
        )
        assert len(hits) == 1

    def test_issue_without_diagnosed_at_falls_back_to_updated_at(self, tmp_path):
        registry = IssueRegistry(tmp_path)
        issue = _make_issue("ISS-001", diagnosed_at=None)
        # updated_at is set in __init__ via now_iso(); fake it to be old
        old = datetime.now(timezone.utc) - timedelta(seconds=DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS + 60)
        issue.updated_at = _iso(old)
        registry.add(issue)

        hits = check_diagnosed_timeouts(tmp_path, event_bus=FakeBus())
        assert len(hits) == 1

    def test_missing_registry_returns_empty(self, tmp_path):
        # Empty project dir, no issues/registry.json — should not crash
        hits = check_diagnosed_timeouts(tmp_path, event_bus=FakeBus())
        assert hits == []

    def test_dedup_process_local_when_state_none(self, tmp_path):
        """When caller omits `state`, dedup still works across polls.

        The engine's monitor loop calls check_diagnosed_timeouts without
        threading a dict. The process-local cache keyed by project_path
        must dedup so ISSUE_DIAGNOSED_TIMEOUT is emitted exactly once
        for each stuck issue.
        """
        registry = IssueRegistry(tmp_path)
        old = datetime.now(timezone.utc) - timedelta(seconds=DEFAULT_ISSUE_DIAGNOSED_TIMEOUT_SECS + 60)
        registry.add(_make_issue("ISS-042", diagnosed_at=_iso(old)))

        bus1 = FakeBus()
        bus2 = FakeBus()
        hits1 = check_diagnosed_timeouts(tmp_path, event_bus=bus1)
        hits2 = check_diagnosed_timeouts(tmp_path, event_bus=bus2)
        assert len(hits1) == 1
        assert hits2 == []
        assert len(bus1.events) == 1
        assert bus2.events == []
