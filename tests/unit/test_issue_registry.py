"""Tests for IssueRegistry — CRUD, dedup, queries, atomic writes."""

import json
import tempfile
from pathlib import Path

import pytest

from set_orch.issues.models import Issue, IssueState, Diagnosis, IssueGroup, MutePattern
from set_orch.issues.registry import IssueRegistry


@pytest.fixture
def tmp_project(tmp_path):
    return tmp_path


@pytest.fixture
def registry(tmp_project):
    return IssueRegistry(tmp_project)


class TestIssueCRUD:
    def test_register_creates_issue(self, registry):
        issue = registry.register(
            source="gate",
            error_summary="Build failed",
            error_detail="npm ERR! code 1",
            environment="test-env",
            environment_path="/tmp/test",
        )
        assert issue is not None
        assert issue.id == "ISS-001"
        assert issue.state == IssueState.NEW
        assert issue.severity == "unknown"
        assert issue.occurrence_count == 1

    def test_register_auto_increments_id(self, registry):
        i1 = registry.register(source="gate", error_summary="Error 1", environment="e")
        i2 = registry.register(source="gate", error_summary="Error 2", environment="e")
        assert i1.id == "ISS-001"
        assert i2.id == "ISS-002"

    def test_get_issue(self, registry):
        registry.register(source="gate", error_summary="Error", environment="e")
        issue = registry.get("ISS-001")
        assert issue is not None
        assert issue.error_summary == "Error"

    def test_get_nonexistent_returns_none(self, registry):
        assert registry.get("ISS-999") is None

    def test_all_issues(self, registry):
        registry.register(source="gate", error_summary="E1", environment="e")
        registry.register(source="gate", error_summary="E2", environment="e")
        assert len(registry.all_issues()) == 2

    def test_persistence_survives_reload(self, tmp_project):
        reg1 = IssueRegistry(tmp_project)
        reg1.register(source="gate", error_summary="Persistent", environment="e")

        reg2 = IssueRegistry(tmp_project)
        assert len(reg2.all_issues()) == 1
        assert reg2.get("ISS-001").error_summary == "Persistent"

    def test_atomic_write(self, registry, tmp_project):
        registry.register(source="gate", error_summary="Test", environment="e")
        path = tmp_project / ".set" / "issues" / "registry.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data["issues"]) == 1


class TestDeduplication:
    def test_duplicate_suppressed(self, registry):
        i1 = registry.register(source="gate", error_summary="Build failed", environment="e")
        i2 = registry.register(source="gate", error_summary="Build failed", environment="e")
        assert i1 is not None
        assert i2 is None  # duplicate
        assert registry.get("ISS-001").occurrence_count == 2

    def test_different_errors_not_deduplicated(self, registry):
        i1 = registry.register(source="gate", error_summary="Build failed", environment="e")
        i2 = registry.register(source="gate", error_summary="Test failed", environment="e")
        assert i1 is not None
        assert i2 is not None
        assert i1.id != i2.id

    def test_resolved_allows_reregistration(self, registry):
        i1 = registry.register(source="gate", error_summary="Build failed", environment="e")
        i1.state = IssueState.RESOLVED
        registry.save()

        i2 = registry.register(source="gate", error_summary="Build failed", environment="e")
        assert i2 is not None
        assert i2.id == "ISS-002"

    def test_timestamps_stripped_for_fingerprint(self, registry):
        i1 = registry.register(
            source="gate",
            error_summary="Error at 2026-03-24T14:00:00Z in module",
            environment="e",
        )
        i2 = registry.register(
            source="gate",
            error_summary="Error at 2026-03-25T10:30:00Z in module",
            environment="e",
        )
        assert i2 is None  # same fingerprint after stripping timestamp


class TestQueries:
    def test_by_state(self, registry):
        i1 = registry.register(source="gate", error_summary="E1", environment="e")
        i2 = registry.register(source="gate", error_summary="E2", environment="e")
        i2.state = IssueState.INVESTIGATING
        registry.save()

        assert len(registry.by_state(IssueState.NEW)) == 1
        assert len(registry.by_state(IssueState.INVESTIGATING)) == 1

    def test_by_severity(self, registry):
        i1 = registry.register(source="gate", error_summary="E1", environment="e")
        i1.severity = "high"
        registry.save()

        assert len(registry.by_severity("high")) == 1
        assert len(registry.by_severity("low")) == 0

    def test_active_excludes_terminal(self, registry):
        i1 = registry.register(source="gate", error_summary="E1", environment="e")
        i2 = registry.register(source="gate", error_summary="E2", environment="e")
        i2.state = IssueState.RESOLVED
        registry.save()

        active = registry.active()
        assert len(active) == 1
        assert active[0].id == "ISS-001"

    def test_count_by_state(self, registry):
        registry.register(source="gate", error_summary="E1", environment="e")
        registry.register(source="gate", error_summary="E2", environment="e")
        assert registry.count_by_state(IssueState.NEW) == 2
        assert registry.count_by_state(IssueState.FIXING) == 0

    def test_stats(self, registry):
        registry.register(source="gate", error_summary="E1", environment="e")
        stats = registry.stats()
        assert stats["by_state"]["new"] == 1
        assert stats["total_open"] >= 1


class TestGroups:
    def test_create_group(self, registry):
        registry.register(source="gate", error_summary="E1", environment="e")
        registry.register(source="gate", error_summary="E2", environment="e")

        group = registry.create_group(
            name="test-group",
            issue_ids=["ISS-001", "ISS-002"],
            reason="Same root cause",
        )
        assert group.id == "GRP-001"
        assert len(group.issue_ids) == 2
        assert registry.get("ISS-001").group_id == "GRP-001"
        assert registry.get("ISS-002").group_id == "GRP-001"

    def test_active_groups(self, registry):
        registry.register(source="gate", error_summary="E1", environment="e")
        registry.register(source="gate", error_summary="E2", environment="e")
        registry.create_group(name="g", issue_ids=["ISS-001", "ISS-002"])

        assert len(registry.active_groups()) == 1


class TestMutePatterns:
    def test_add_and_match_mute(self, registry):
        registry.add_mute(pattern="Build failed", reason="Known issue")
        mute = registry.matches_mute("Build failed in CI")
        assert mute is not None
        assert mute.match_count == 1

    def test_no_match(self, registry):
        registry.add_mute(pattern="Build failed", reason="Known")
        assert registry.matches_mute("Test passed") is None

    def test_expired_mute_ignored(self, registry):
        registry.add_mute(
            pattern="Build failed",
            reason="Temp",
            expires_at="2020-01-01T00:00:00+00:00",
        )
        assert registry.matches_mute("Build failed") is None

    def test_match_count_increments(self, registry):
        registry.add_mute(pattern="Error", reason="Known")
        registry.matches_mute("Error occurred")
        registry.matches_mute("Error happened")
        mute = registry.all_mutes()[0]
        assert mute.match_count == 2

    def test_mute_persistence(self, tmp_project):
        reg1 = IssueRegistry(tmp_project)
        reg1.add_mute(pattern="test", reason="r")

        reg2 = IssueRegistry(tmp_project)
        assert len(reg2.all_mutes()) == 1
