"""Unit tests for `scan_fix_iss_orphans` + the `issues cleanup-orphans` CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from set_orch.issues.manager import (
    scan_fix_iss_orphans,
    _purge_fix_iss_child,
)
from set_orch.issues.models import Issue, IssueState


def _write_state(path: Path, changes: list[dict]) -> None:
    path.write_text(json.dumps({
        "status": "running", "plan_version": 1,
        "changes": changes, "merge_queue": [],
    }))


def _write_registry(path: Path, issues: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"issues": issues, "next_issue_num": len(issues) + 1}))


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "openspec" / "changes").mkdir(parents=True)
    (tmp_path / ".set" / "issues").mkdir(parents=True)
    return tmp_path


def test_scan_empty_project_returns_empty(project: Path) -> None:
    assert scan_fix_iss_orphans(str(project)) == []


def test_scan_parent_merged_orphan_child_detected(project: Path) -> None:
    _write_state(project / "orchestration-state.json", [
        {"name": "p", "status": "merged", "phase": 1, "scope": "s"},
        {"name": "fix-iss-001-p", "status": "pending", "phase": 2, "scope": "s"},
    ])
    _write_registry(project / ".set" / "issues" / "registry.json", [{
        "id": "ISS-1", "affected_change": "p", "change_name": "fix-iss-001-p",
        "state": "new", "source": "gate",
    }])
    (project / "openspec" / "changes" / "fix-iss-001-p").mkdir()

    orphans = scan_fix_iss_orphans(str(project))
    assert len(orphans) == 1
    assert orphans[0]["child_name"] == "fix-iss-001-p"
    assert orphans[0]["parent_name"] == "p"
    assert orphans[0]["reason"] == "parent_merged"


def test_scan_resolved_issue_with_pending_child(project: Path) -> None:
    _write_state(project / "orchestration-state.json", [
        {"name": "p", "status": "failed:token_runaway", "phase": 1, "scope": "s"},
        {"name": "fix-iss-002-p", "status": "pending", "phase": 2, "scope": "s"},
    ])
    _write_registry(project / ".set" / "issues" / "registry.json", [{
        "id": "ISS-2", "affected_change": "p", "change_name": "fix-iss-002-p",
        "state": "resolved", "source": "gate",
    }])
    (project / "openspec" / "changes" / "fix-iss-002-p").mkdir()

    orphans = scan_fix_iss_orphans(str(project))
    assert len(orphans) == 1
    assert orphans[0]["reason"] == "issue_resolved"


def test_scan_fs_divergence_dir_without_state(project: Path) -> None:
    _write_state(project / "orchestration-state.json", [])  # empty state
    (project / "openspec" / "changes" / "fix-iss-003-zombie").mkdir()

    orphans = scan_fix_iss_orphans(str(project))
    assert len(orphans) == 1
    assert orphans[0]["child_name"] == "fix-iss-003-zombie"
    assert orphans[0]["reason"] == "fs_state_divergence"


def test_scan_skips_active_dispatch(project: Path) -> None:
    _write_state(project / "orchestration-state.json", [
        {"name": "p", "status": "merged", "phase": 1, "scope": "s"},
        {"name": "fix-iss-004-p", "status": "dispatched", "phase": 2, "scope": "s"},
    ])
    _write_registry(project / ".set" / "issues" / "registry.json", [{
        "id": "ISS-4", "affected_change": "p", "change_name": "fix-iss-004-p",
        "state": "new", "source": "gate",
    }])
    (project / "openspec" / "changes" / "fix-iss-004-p").mkdir()

    # Active dispatch is NOT an orphan — it's in-flight work
    orphans = scan_fix_iss_orphans(str(project))
    assert orphans == []


def test_scan_skips_merged_child(project: Path) -> None:
    _write_state(project / "orchestration-state.json", [
        {"name": "p", "status": "merged", "phase": 1, "scope": "s"},
        {"name": "fix-iss-005-p", "status": "merged", "phase": 2, "scope": "s"},
    ])
    orphans = scan_fix_iss_orphans(str(project))
    assert orphans == []


def test_scan_multiple_orphans(project: Path) -> None:
    _write_state(project / "orchestration-state.json", [
        {"name": "p1", "status": "merged", "phase": 1, "scope": "s"},
        {"name": "fix-iss-001-p1", "status": "pending", "phase": 2, "scope": "s"},
        {"name": "p2", "status": "failed:token_runaway", "phase": 1, "scope": "s"},
        {"name": "fix-iss-002-p2", "status": "pending", "phase": 2, "scope": "s"},
    ])
    _write_registry(project / ".set" / "issues" / "registry.json", [
        {"id": "I1", "affected_change": "p1", "change_name": "fix-iss-001-p1",
         "state": "new", "source": "gate"},
        {"id": "I2", "affected_change": "p2", "change_name": "fix-iss-002-p2",
         "state": "resolved", "source": "gate"},
    ])
    (project / "openspec" / "changes" / "fix-iss-001-p1").mkdir()
    (project / "openspec" / "changes" / "fix-iss-002-p2").mkdir()

    orphans = scan_fix_iss_orphans(str(project))
    names = {o["child_name"] for o in orphans}
    assert names == {"fix-iss-001-p1", "fix-iss-002-p2"}


def test_cli_purge_flow_via_helpers(project: Path) -> None:
    """End-to-end: seed orphans, scan, purge each via the same code the CLI runs."""
    _write_state(project / "orchestration-state.json", [
        {"name": "p", "status": "merged", "phase": 1, "scope": "s"},
        {
            "name": "fix-iss-001-p", "status": "pending", "phase": 2,
            "scope": "s", "depends_on": ["p"],
        },
    ])
    child_dir = project / "openspec" / "changes" / "fix-iss-001-p"
    child_dir.mkdir()

    orphans = scan_fix_iss_orphans(str(project))
    assert len(orphans) == 1

    # Simulate the CLI's per-orphan purge loop
    state_file = str(project / "orchestration-state.json")
    for o in orphans:
        shim = Issue(
            id="CLI-test",
            environment="cli",
            environment_path=str(project),
            source="cli:cleanup-orphans",
            state=IssueState.RESOLVED,
            change_name=o["child_name"],
            affected_change=o["parent_name"],
        )
        result = _purge_fix_iss_child(
            shim, state_file, str(project), reason="cli_cleanup",
        )
        assert result["state_removed"] or result["dir_removed"]

    # Verify cleanup
    assert not child_dir.exists()
    state = json.loads((project / "orchestration-state.json").read_text())
    assert all(c["name"] != "fix-iss-001-p" for c in state["changes"])

    # Re-scan: no orphans left
    assert scan_fix_iss_orphans(str(project)) == []
