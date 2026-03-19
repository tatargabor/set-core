"""Tests for sentinel event logging, rotation, and .set/ directory creation."""

import json
import os
import tempfile

import pytest

from set_orch.sentinel.events import SentinelEventLogger
from set_orch.sentinel.rotation import rotate
from set_orch.sentinel.set_dir import ensure_set_dir


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Create a temporary project directory with isolated runtime."""
    # Override XDG_DATA_HOME so SetRuntime resolves to tmp_path
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    # Reload paths module to pick up new env
    import importlib
    import set_orch.paths
    importlib.reload(set_orch.paths)
    yield str(tmp_path)
    # Restore
    importlib.reload(set_orch.paths)


class TestWtDir:
    def test_creates_sentinel_dir(self, project):
        path = ensure_set_dir(project)
        assert os.path.isdir(path)
        assert os.path.isdir(os.path.join(path, "archive"))

    def test_sentinel_dir_under_xdg(self, project):
        """Sentinel dir is now under ~/.local/share/set-core/, not project-local."""
        path = ensure_set_dir(project)
        assert "set-core" in path
        assert "sentinel" in path

    def test_idempotent(self, project):
        path1 = ensure_set_dir(project)
        path2 = ensure_set_dir(project)
        assert path1 == path2
        assert os.path.isdir(path1)


class TestSentinelEventLogger:
    def test_poll_event(self, project):
        logger = SentinelEventLogger(project)
        event = logger.poll(state="running", change="add-cart", iteration=3)
        assert event["type"] == "poll"
        assert event["state"] == "running"
        assert event["change"] == "add-cart"
        assert event["iteration"] == 3
        assert "ts" in event
        assert "epoch" in event

    def test_crash_event(self, project):
        logger = SentinelEventLogger(project)
        event = logger.crash(pid=12345, exit_code=1, stderr_tail="error msg")
        assert event["type"] == "crash"
        assert event["pid"] == 12345
        assert event["exit_code"] == 1
        assert event["stderr_tail"] == "error msg"

    def test_stderr_truncation(self, project):
        logger = SentinelEventLogger(project)
        long_stderr = "x" * 1000
        event = logger.crash(pid=1, exit_code=1, stderr_tail=long_stderr)
        assert len(event["stderr_tail"]) == 500

    def test_restart_event(self, project):
        logger = SentinelEventLogger(project)
        event = logger.restart(new_pid=99999, attempt=2)
        assert event["type"] == "restart"
        assert event["new_pid"] == 99999
        assert event["attempt"] == 2

    def test_decision_event(self, project):
        logger = SentinelEventLogger(project)
        event = logger.decision(action="auto_approve", reason="periodic checkpoint")
        assert event["type"] == "decision"
        assert event["action"] == "auto_approve"

    def test_escalation_event(self, project):
        logger = SentinelEventLogger(project)
        event = logger.escalation(reason="non-periodic checkpoint", context="ctx")
        assert event["type"] == "escalation"
        assert event["reason"] == "non-periodic checkpoint"

    def test_finding_event(self, project):
        logger = SentinelEventLogger(project)
        event = logger.finding(finding_id="F001", severity="bug", change="add-cart", summary="IDOR")
        assert event["type"] == "finding"
        assert event["finding_id"] == "F001"

    def test_message_events(self, project):
        logger = SentinelEventLogger(project)
        recv = logger.message_received(sender="user", content="stop")
        sent = logger.message_sent(recipient="user", content="ok")
        assert recv["type"] == "message_received"
        assert sent["type"] == "message_sent"

    def test_events_appended_to_jsonl(self, project):
        logger = SentinelEventLogger(project)
        logger.poll(state="running")
        logger.poll(state="running")
        logger.crash(pid=1, exit_code=1)

        with open(logger.events_file) as f:
            lines = [l for l in f.readlines() if l.strip()]
        assert len(lines) == 3
        assert json.loads(lines[0])["type"] == "poll"
        assert json.loads(lines[2])["type"] == "crash"

    def test_tail_returns_all_events(self, project):
        logger = SentinelEventLogger(project)
        logger.poll(state="a")
        logger.poll(state="b")
        events = logger.tail()
        assert len(events) == 2
        assert events[0]["state"] == "a"
        assert events[1]["state"] == "b"

    def test_tail_with_limit(self, project):
        logger = SentinelEventLogger(project)
        for i in range(10):
            logger.poll(state=f"s{i}")
        events = logger.tail(limit=3)
        assert len(events) == 3
        assert events[0]["state"] == "s7"

    def test_tail_with_since(self, project):
        logger = SentinelEventLogger(project)
        e1 = logger.poll(state="old")
        epoch = e1["epoch"]
        # Events with same epoch should be filtered by > not >=
        events = logger.tail(since_epoch=epoch)
        assert len(events) == 0

    def test_tail_empty_file(self, project):
        logger = SentinelEventLogger(project)
        assert logger.tail() == []

    def test_tail_no_file(self, project):
        logger = SentinelEventLogger(project)
        os.remove(logger.events_file) if os.path.exists(logger.events_file) else None
        assert logger.tail() == []


class TestRotation:
    def test_rotate_moves_files(self, project):
        logger = SentinelEventLogger(project)
        logger.poll(state="running")

        # Create a findings file too
        findings_path = os.path.join(logger.sentinel_dir, "findings.json")
        with open(findings_path, "w") as f:
            json.dump({"findings": [{"id": "F001"}]}, f)

        result = rotate(project)
        assert result["events_archived"] != ""
        assert result["findings_archived"] != ""
        assert os.path.exists(result["events_archived"])
        assert os.path.exists(result["findings_archived"])

        # Original events file should be empty (recreated)
        assert os.path.exists(logger.events_file)
        assert os.path.getsize(logger.events_file) == 0

    def test_rotate_no_files(self, project):
        ensure_set_dir(project)
        result = rotate(project)
        assert result["events_archived"] == ""
        assert result["findings_archived"] == ""

    def test_rotate_empty_files(self, project):
        logger = SentinelEventLogger(project)
        # events_file exists but is empty (created by ensure_set_dir -> no)
        # Actually, SentinelEventLogger doesn't create the file on init
        open(logger.events_file, "w").close()
        result = rotate(project)
        assert result["events_archived"] == ""
