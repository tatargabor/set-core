"""Unit tests for `_purge_fix_iss_child` helper."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from set_orch.issues.manager import _purge_fix_iss_child
from set_orch.issues.models import Issue, IssueState


def _make_issue(change_name: str, parent: str = "the-parent") -> Issue:
    return Issue(
        id="ISS-001",
        environment="test",
        environment_path="",
        source="test",
        state=IssueState.RESOLVED,
        change_name=change_name,
        affected_change=parent,
    )


def _write_state(state_file: Path, changes: list[dict]) -> None:
    state_file.write_text(json.dumps({
        "status": "running",
        "plan_version": 1,
        "changes": changes,
        "merge_queue": [],
    }))


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "openspec" / "changes").mkdir(parents=True)
    return tmp_path


def test_pending_with_dir_both_removed(project: Path) -> None:
    state_file = project / "orchestration-state.json"
    child_dir = project / "openspec" / "changes" / "fix-iss-007-foo"
    child_dir.mkdir()
    (child_dir / "proposal.md").write_text("x")
    _write_state(state_file, [{
        "name": "fix-iss-007-foo", "scope": "s",
        "status": "pending", "phase": 2,
    }])

    issue = _make_issue("fix-iss-007-foo")
    result = _purge_fix_iss_child(issue, str(state_file), str(project), reason="test")

    assert result["state_removed"] is True
    assert result["dir_removed"] is True
    assert result["skipped_reason"] is None
    assert not child_dir.exists()
    state = json.loads(state_file.read_text())
    assert all(c["name"] != "fix-iss-007-foo" for c in state["changes"])


def test_merged_is_noop(project: Path) -> None:
    state_file = project / "orchestration-state.json"
    child_dir = project / "openspec" / "changes" / "fix-iss-007-foo"
    child_dir.mkdir()
    _write_state(state_file, [{
        "name": "fix-iss-007-foo", "scope": "s",
        "status": "merged", "phase": 2,
    }])

    issue = _make_issue("fix-iss-007-foo")
    result = _purge_fix_iss_child(issue, str(state_file), str(project), reason="test")

    assert result["state_removed"] is False
    assert result["dir_removed"] is False
    assert result["skipped_reason"] == "already_merged"
    assert child_dir.exists()  # not touched


def test_active_dispatch_skipped(project: Path) -> None:
    state_file = project / "orchestration-state.json"
    child_dir = project / "openspec" / "changes" / "fix-iss-007-foo"
    child_dir.mkdir()
    _write_state(state_file, [{
        "name": "fix-iss-007-foo", "scope": "s",
        "status": "dispatched", "phase": 2,
    }])

    issue = _make_issue("fix-iss-007-foo")
    result = _purge_fix_iss_child(issue, str(state_file), str(project), reason="test")

    assert result["state_removed"] is False
    assert result["dir_removed"] is False
    assert result["skipped_reason"] == "active_dispatch"
    assert child_dir.exists()


def test_state_only_no_dir(project: Path) -> None:
    state_file = project / "orchestration-state.json"
    _write_state(state_file, [{
        "name": "fix-iss-007-foo", "scope": "s",
        "status": "pending", "phase": 2,
    }])

    issue = _make_issue("fix-iss-007-foo")
    result = _purge_fix_iss_child(issue, str(state_file), str(project), reason="test")

    assert result["state_removed"] is True
    assert result["dir_removed"] is False
    state = json.loads(state_file.read_text())
    assert all(c["name"] != "fix-iss-007-foo" for c in state["changes"])


def test_dir_only_no_state(project: Path) -> None:
    state_file = project / "orchestration-state.json"
    child_dir = project / "openspec" / "changes" / "fix-iss-007-foo"
    child_dir.mkdir()
    _write_state(state_file, [])  # empty state

    issue = _make_issue("fix-iss-007-foo")
    result = _purge_fix_iss_child(issue, str(state_file), str(project), reason="test")

    assert result["state_removed"] is False
    assert result["dir_removed"] is True
    assert not child_dir.exists()


def test_neither_present_noop(project: Path) -> None:
    state_file = project / "orchestration-state.json"
    _write_state(state_file, [])

    issue = _make_issue("fix-iss-007-foo")
    result = _purge_fix_iss_child(issue, str(state_file), str(project), reason="test")

    assert result["state_removed"] is False
    assert result["dir_removed"] is False
    assert result["skipped_reason"] is None  # not a skip, just a no-op


def test_non_fix_iss_change_name_returns_early(project: Path) -> None:
    state_file = project / "orchestration-state.json"
    _write_state(state_file, [{"name": "regular-change", "scope": "s", "status": "pending"}])

    issue = _make_issue("regular-change")  # NOT a fix-iss prefix
    result = _purge_fix_iss_child(issue, str(state_file), str(project), reason="test")

    assert result["skipped_reason"] == "not_a_fix_iss_child"
    # State untouched
    state = json.loads(state_file.read_text())
    assert any(c["name"] == "regular-change" for c in state["changes"])


def test_empty_change_name_returns_early(project: Path) -> None:
    issue = _make_issue("")
    result = _purge_fix_iss_child(
        issue, str(project / "state.json"), str(project), reason="test",
    )
    assert result["skipped_reason"] == "not_a_fix_iss_child"
