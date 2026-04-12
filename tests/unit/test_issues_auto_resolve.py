"""Tests for issue auto-resolve on change merge (Part 6)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.issues.models import Issue, IssueState, now_iso
from set_orch.issues.registry import IssueRegistry


def _make_issue(
    id: str,
    *,
    affected_change: str = "change-a",
    state: IssueState = IssueState.DIAGNOSED,
    environment: str = "test-proj",
) -> Issue:
    return Issue(
        id=id,
        environment=environment,
        environment_path="/tmp/proj",
        source="sentinel",
        state=state,
        error_summary="test",
        affected_change=affected_change,
        diagnosed_at=now_iso() if state == IssueState.DIAGNOSED else None,
    )


class TestAutoResolveForChange:
    def test_single_diagnosed_issue_resolved(self, tmp_path):
        registry = IssueRegistry(tmp_path)
        registry.add(_make_issue("ISS-001", affected_change="foo"))

        resolved = registry.auto_resolve_for_change("foo")
        assert resolved == ["ISS-001"]
        assert registry.get("ISS-001").state == IssueState.RESOLVED
        assert registry.get("ISS-001").resolved_at

    def test_multiple_issues_same_change_all_resolved(self, tmp_path):
        registry = IssueRegistry(tmp_path)
        registry.add(_make_issue("ISS-001", affected_change="foo"))
        registry.add(_make_issue("ISS-002", affected_change="foo", state=IssueState.INVESTIGATING))
        registry.add(_make_issue("ISS-003", affected_change="foo"))

        resolved = registry.auto_resolve_for_change("foo")
        assert set(resolved) == {"ISS-001", "ISS-002", "ISS-003"}
        for iid in ("ISS-001", "ISS-002", "ISS-003"):
            assert registry.get(iid).state == IssueState.RESOLVED

    def test_cross_change_issues_untouched(self, tmp_path):
        registry = IssueRegistry(tmp_path)
        registry.add(_make_issue("ISS-001", affected_change="foo"))
        registry.add(_make_issue("ISS-002", affected_change="bar"))

        resolved = registry.auto_resolve_for_change("foo")
        assert resolved == ["ISS-001"]
        assert registry.get("ISS-002").state == IssueState.DIAGNOSED

    def test_already_resolved_issues_skipped(self, tmp_path):
        registry = IssueRegistry(tmp_path)
        registry.add(_make_issue("ISS-001", affected_change="foo", state=IssueState.RESOLVED))
        registry.add(_make_issue("ISS-002", affected_change="foo", state=IssueState.DIAGNOSED))

        resolved = registry.auto_resolve_for_change("foo")
        assert resolved == ["ISS-002"]

    def test_no_matching_issues_returns_empty(self, tmp_path):
        registry = IssueRegistry(tmp_path)
        registry.add(_make_issue("ISS-001", affected_change="other"))

        resolved = registry.auto_resolve_for_change("foo")
        assert resolved == []

    def test_empty_registry_noop(self, tmp_path):
        registry = IssueRegistry(tmp_path)
        resolved = registry.auto_resolve_for_change("foo")
        assert resolved == []

    def test_dismissed_issue_left_alone(self, tmp_path):
        registry = IssueRegistry(tmp_path)
        registry.add(_make_issue("ISS-001", affected_change="foo", state=IssueState.DISMISSED))
        resolved = registry.auto_resolve_for_change("foo")
        assert resolved == []

    def test_audit_entries_written(self, tmp_path):
        registry = IssueRegistry(tmp_path)
        registry.add(_make_issue("ISS-001", affected_change="foo"))

        registry.auto_resolve_for_change("foo", reason="merge_success:foo")

        audit_path = tmp_path / ".set" / "issues" / "audit.jsonl"
        assert audit_path.exists()
        entries = [json.loads(line) for line in audit_path.read_text().splitlines() if line.strip()]
        assert any(
            e.get("issue_id") == "ISS-001"
            and e.get("action") == "change_merged_auto_resolve"
            and e.get("reason") == "merge_success:foo"
            and e.get("from_state") == "diagnosed"
            and e.get("to_state") == "resolved"
            for e in entries
        )
