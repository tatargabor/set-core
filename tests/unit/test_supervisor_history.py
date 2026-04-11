"""Unit tests for lib/set_orch/supervisor/history.py."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.supervisor.history import build_prior_attempts_summary


@pytest.fixture
def events_file():
    d = tempfile.mkdtemp()
    p = Path(d) / "events.jsonl"
    yield p
    shutil.rmtree(d, ignore_errors=True)


def write_events(p: Path, events: list[dict]) -> None:
    with open(p, "w") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")


class TestBuildPriorAttemptsSummary:
    def test_no_events_returns_empty(self, events_file):
        # File doesn't exist
        assert build_prior_attempts_summary(events_file, trigger="anything") == ""

    def test_filters_by_trigger(self, events_file):
        write_events(events_file, [
            {"type": "SUPERVISOR_TRIGGER", "ts": "t1", "data": {
                "trigger": "integration_failed", "change": "x", "exit_code": 0,
                "stdout_tail": "fixed it",
            }},
            {"type": "SUPERVISOR_TRIGGER", "ts": "t2", "data": {
                "trigger": "process_crash", "exit_code": 0, "stdout_tail": "boom",
            }},
        ])
        out = build_prior_attempts_summary(events_file, trigger="integration_failed")
        assert "integration_failed" in out
        assert "fixed it" in out
        assert "boom" not in out

    def test_filters_by_change(self, events_file):
        write_events(events_file, [
            {"type": "SUPERVISOR_TRIGGER", "ts": "t1", "data": {
                "trigger": "integration_failed", "change": "alpha", "exit_code": 0,
                "stdout_tail": "alpha tail",
            }},
            {"type": "SUPERVISOR_TRIGGER", "ts": "t2", "data": {
                "trigger": "integration_failed", "change": "beta", "exit_code": 0,
                "stdout_tail": "beta tail",
            }},
        ])
        out = build_prior_attempts_summary(
            events_file, trigger="integration_failed", change="alpha",
        )
        assert "alpha tail" in out
        assert "beta tail" not in out

    def test_skipped_attempts_excluded(self, events_file):
        # SUPERVISOR_TRIGGER events without exit_code (just `skipped`) should
        # not show up as prior attempts — they were never actually dispatched.
        write_events(events_file, [
            {"type": "SUPERVISOR_TRIGGER", "ts": "t1", "data": {
                "trigger": "process_crash", "skipped": "rate_limit_hit",
            }},
        ])
        out = build_prior_attempts_summary(events_file, trigger="process_crash")
        assert out == ""

    def test_truncates_to_max(self, events_file):
        events = []
        for i in range(10):
            events.append({"type": "SUPERVISOR_TRIGGER", "ts": f"t{i}", "data": {
                "trigger": "process_crash",
                "exit_code": 0,
                "stdout_tail": f"tail-{i}",
            }})
        write_events(events_file, events)
        out = build_prior_attempts_summary(
            events_file, trigger="process_crash", max_attempts=3,
        )
        # Should mention 3 attempts and contain only the LAST 3 tails
        assert "3 most recent" in out
        assert "tail-7" in out
        assert "tail-8" in out
        assert "tail-9" in out
        assert "tail-0" not in out

    def test_other_event_types_ignored(self, events_file):
        write_events(events_file, [
            {"type": "STATE_CHANGE", "data": {"trigger": "integration_failed"}},
            {"type": "DISPATCH", "data": {"trigger": "integration_failed"}},
        ])
        assert build_prior_attempts_summary(
            events_file, trigger="integration_failed",
        ) == ""

    def test_malformed_lines_skipped(self, events_file):
        with open(events_file, "w") as f:
            f.write("not json\n")
            f.write(json.dumps({
                "type": "SUPERVISOR_TRIGGER", "ts": "t1",
                "data": {"trigger": "process_crash", "exit_code": 0, "stdout_tail": "ok"},
            }) + "\n")
            f.write("also not json\n")
        out = build_prior_attempts_summary(events_file, trigger="process_crash")
        assert "ok" in out
