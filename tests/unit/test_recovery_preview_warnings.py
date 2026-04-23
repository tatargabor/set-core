"""Unit tests for recovery.render_preview active-issue warnings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from set_orch.recovery import RecoveryPlan, render_preview


def _make_plan(rollback_changes: list[str]) -> RecoveryPlan:
    return RecoveryPlan(
        target_change=rollback_changes[0] if rollback_changes else "",
        target_commit="deadbeef1234",
        rollback_changes=rollback_changes,
        branches_to_delete=[f"change/{c}" for c in rollback_changes],
        worktrees_to_remove=[],
        archive_dirs_to_restore=[],
        state_changes_to_reset=rollback_changes,
        backup_tag="recovery-backup-20260423-100000",
        first_rolled_back_phase=1,
    )


def _write_registry(project: Path, issues: list[dict]) -> None:
    (project / ".set" / "issues").mkdir(parents=True, exist_ok=True)
    (project / ".set" / "issues" / "registry.json").write_text(
        json.dumps({"issues": issues, "next_issue_num": len(issues) + 1})
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return tmp_path


def test_no_active_issues_no_warning_section(project: Path) -> None:
    plan = _make_plan(["foo"])
    out = render_preview(plan, project)
    assert "Active fix-iss pipelines outside rollback scope" not in out


def test_active_issue_inside_scope_not_listed(project: Path) -> None:
    _write_registry(project, [{
        "id": "ISS-1", "state": "investigating",
        "affected_change": "foo",
        "change_name": "fix-iss-001-foo",
    }])
    plan = _make_plan(["foo"])  # rolling back "foo"
    out = render_preview(plan, project)
    assert "Active fix-iss pipelines outside rollback scope" not in out


def test_active_issue_outside_scope_listed(project: Path) -> None:
    _write_registry(project, [{
        "id": "ISS-4", "state": "diagnosed",
        "affected_change": "admin-dashboard",
        "change_name": "fix-iss-004-admin-dashboard",
    }])
    plan = _make_plan(["foo"])  # rolling back "foo", NOT admin-dashboard
    out = render_preview(plan, project)
    assert "Active fix-iss pipelines outside rollback scope" in out
    assert "ISS-4" in out
    assert "admin-dashboard" in out
    assert "fix-iss-004-admin-dashboard" in out


def test_terminal_state_ignored(project: Path) -> None:
    _write_registry(project, [
        {"id": "R1", "state": "resolved", "affected_change": "other"},
        {"id": "D1", "state": "dismissed", "affected_change": "other"},
        {"id": "M1", "state": "muted", "affected_change": "other"},
        {"id": "C1", "state": "cancelled", "affected_change": "other"},
        {"id": "F1", "state": "failed", "affected_change": "other"},
        {"id": "S1", "state": "skipped", "affected_change": "other"},
    ])
    plan = _make_plan(["foo"])
    out = render_preview(plan, project)
    assert "Active fix-iss pipelines outside rollback scope" not in out


def test_mixed_states_only_active_listed(project: Path) -> None:
    _write_registry(project, [
        {"id": "A1", "state": "investigating", "affected_change": "other1",
         "change_name": "fix-iss-001-other1"},
        {"id": "A2", "state": "diagnosed", "affected_change": "other2"},
        {"id": "A3", "state": "fixing", "affected_change": "other3"},
        {"id": "R1", "state": "resolved", "affected_change": "gone1"},
    ])
    plan = _make_plan(["foo"])
    out = render_preview(plan, project)
    assert "A1" in out
    assert "A2" in out
    assert "A3" in out
    assert "R1" not in out


def test_registry_missing_graceful(project: Path) -> None:
    # No registry file at all
    plan = _make_plan(["foo"])
    out = render_preview(plan, project)  # must not raise
    assert "Active fix-iss pipelines outside rollback scope" not in out


def test_registry_malformed_graceful(project: Path) -> None:
    (project / ".set" / "issues").mkdir(parents=True, exist_ok=True)
    (project / ".set" / "issues" / "registry.json").write_text("{not: valid json")
    plan = _make_plan(["foo"])
    out = render_preview(plan, project)  # must not raise
    assert "Active fix-iss pipelines outside rollback scope" not in out


def test_issue_with_no_affected_change_ignored(project: Path) -> None:
    _write_registry(project, [{
        "id": "ISS-5", "state": "investigating", "affected_change": None,
    }])
    plan = _make_plan(["foo"])
    out = render_preview(plan, project)
    assert "Active fix-iss pipelines outside rollback scope" not in out
