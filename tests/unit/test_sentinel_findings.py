"""Tests for sentinel findings, status, and inbox."""

import json
import os

import pytest

from wt_orch.sentinel.events import SentinelEventLogger
from wt_orch.sentinel.findings import SentinelFindings
from wt_orch.sentinel.status import SentinelStatus
from wt_orch.sentinel.inbox import check_inbox, write_to_inbox


@pytest.fixture
def project(tmp_path):
    return str(tmp_path)


class TestSentinelFindings:
    def test_add_finding(self, project):
        findings = SentinelFindings(project)
        f = findings.add(severity="bug", change="add-cart", summary="IDOR vulnerability")
        assert f["id"] == "F001"
        assert f["severity"] == "bug"
        assert f["status"] == "open"

    def test_sequential_ids(self, project):
        findings = SentinelFindings(project)
        f1 = findings.add(severity="bug", change="a", summary="first")
        f2 = findings.add(severity="observation", change="b", summary="second")
        assert f1["id"] == "F001"
        assert f2["id"] == "F002"

    def test_update_finding(self, project):
        findings = SentinelFindings(project)
        findings.add(severity="bug", change="a", summary="test")
        updated = findings.update("F001", status="fixed", commit="abc123")
        assert updated["status"] == "fixed"
        assert updated["commit"] == "abc123"
        # Verify persisted
        reloaded = SentinelFindings(project).list()
        assert reloaded[0]["status"] == "fixed"

    def test_update_nonexistent(self, project):
        findings = SentinelFindings(project)
        assert findings.update("F999", status="fixed") is None

    def test_list_all(self, project):
        findings = SentinelFindings(project)
        findings.add(severity="bug", change="a", summary="open bug")
        findings.add(severity="observation", change="b", summary="obs")
        findings.update("F001", status="fixed")
        assert len(findings.list()) == 2

    def test_list_filtered(self, project):
        findings = SentinelFindings(project)
        findings.add(severity="bug", change="a", summary="open")
        findings.add(severity="bug", change="b", summary="also open")
        findings.update("F001", status="fixed")
        open_only = findings.list(status="open")
        assert len(open_only) == 1
        assert open_only[0]["id"] == "F002"

    def test_assess(self, project):
        findings = SentinelFindings(project)
        a = findings.assess(scope="phase-2", summary="2/4 merged", recommendation="fix IDOR")
        assert a["scope"] == "phase-2"
        data = findings.get_all()
        assert len(data["assessments"]) == 1

    def test_add_emits_event(self, project):
        logger = SentinelEventLogger(project)
        findings = SentinelFindings(project, event_logger=logger)
        findings.add(severity="bug", change="cart", summary="IDOR")
        events = logger.tail()
        finding_events = [e for e in events if e["type"] == "finding"]
        assert len(finding_events) == 1
        assert finding_events[0]["finding_id"] == "F001"

    def test_empty_findings(self, project):
        findings = SentinelFindings(project)
        assert findings.list() == []
        data = findings.get_all()
        assert data["findings"] == []
        assert data["assessments"] == []


class TestSentinelStatus:
    def test_register(self, project):
        status = SentinelStatus(project)
        data = status.register(member="tg@linux", orchestrator_pid=12345)
        assert data["active"] is True
        assert data["member"] == "tg@linux"
        assert data["orchestrator_pid"] == 12345

    def test_heartbeat(self, project):
        status = SentinelStatus(project)
        status.register(member="tg@linux")
        old = status.get()["last_event_at"]
        import time; time.sleep(0.01)
        status.heartbeat()
        new = status.get()["last_event_at"]
        # Heartbeat should update (or same second)
        assert new >= old

    def test_deactivate(self, project):
        status = SentinelStatus(project)
        status.register(member="tg@linux")
        status.deactivate()
        assert status.get()["active"] is False

    def test_get_missing_file(self, project):
        status = SentinelStatus(project)
        data = status.get()
        assert data["active"] is False

    def test_is_active_true(self, project):
        status = SentinelStatus(project)
        status.register(member="tg@linux")
        assert status.is_active() is True

    def test_is_active_false_when_deactivated(self, project):
        status = SentinelStatus(project)
        status.register(member="tg@linux")
        status.deactivate()
        assert status.is_active() is False


class TestInbox:
    def test_empty_inbox(self, project):
        assert check_inbox(project) == []

    def test_write_and_read(self, project):
        write_to_inbox(project, sender="user", content="hello")
        messages = check_inbox(project)
        assert len(messages) == 1
        assert messages[0]["from"] == "user"
        assert messages[0]["content"] == "hello"

    def test_cursor_advances(self, project):
        write_to_inbox(project, sender="user", content="first")
        msgs1 = check_inbox(project)
        assert len(msgs1) == 1

        # Second check without new messages
        msgs2 = check_inbox(project)
        assert len(msgs2) == 0

        # Write another message
        write_to_inbox(project, sender="user", content="second")
        msgs3 = check_inbox(project)
        assert len(msgs3) == 1
        assert msgs3[0]["content"] == "second"

    def test_multiple_messages(self, project):
        write_to_inbox(project, sender="a", content="msg1")
        write_to_inbox(project, sender="b", content="msg2")
        write_to_inbox(project, sender="c", content="msg3")
        messages = check_inbox(project)
        assert len(messages) == 3
