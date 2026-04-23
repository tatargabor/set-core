"""Regression tests for fix-iss-lifecycle-hardening change.

Covers:
- Native-merge auto-resolve purges the orphan fix-iss child.
- Re-escalation with live link returns existing name (no duplicate).
- Re-escalation with stale link auto-repairs and creates fresh child.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


def _write_state(state_file: Path, changes: list[dict]) -> None:
    state_file.write_text(json.dumps({
        "status": "running",
        "plan_version": 1,
        "changes": changes,
        "merge_queue": [],
    }))


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    """Redirect SetRuntime (where LineagePaths resolves state_file to) under tmp_path
    so these tests don't collide with the host's real runtime state."""
    import set_orch.paths as paths_mod
    monkeypatch.setattr(
        paths_mod, "SET_TOOLS_DATA_DIR",
        str(tmp_path / "xdg" / "set-core"),
    )
    yield


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "openspec" / "changes").mkdir(parents=True)
    (proj / ".set" / "issues").mkdir(parents=True)
    return proj


def _runtime_state_file(project: Path) -> Path:
    """Resolve the runtime state-file path that _check_affected_change_merged reads."""
    from set_orch.paths import LineagePaths
    sf = Path(LineagePaths(str(project)).state_file)
    sf.parent.mkdir(parents=True, exist_ok=True)
    return sf


# --- Native-merge auto-resolve --------------------------------------------


def test_native_merge_auto_resolve_purges_orphan(project: Path) -> None:
    """When `_check_affected_change_merged` transitions an issue to RESOLVED
    because the parent merged natively, the linked pending fix-iss child
    must be purged."""
    from set_orch.issues.manager import IssueManager
    from set_orch.issues.registry import IssueRegistry
    from set_orch.issues.audit import AuditLog
    from set_orch.issues.policy import PolicyEngine, IssuesPolicyConfig
    from set_orch.issues.models import Issue, IssueState

    state_file = _runtime_state_file(project)
    child_dir = project / "openspec" / "changes" / "fix-iss-007-the-parent"
    child_dir.mkdir()
    (child_dir / "proposal.md").write_text("x")
    _write_state(state_file, [
        {"name": "the-parent", "scope": "s", "status": "merged", "phase": 1},
        {
            "name": "fix-iss-007-the-parent", "scope": "s",
            "status": "pending", "phase": 2,
        },
    ])

    issue = Issue(
        id="ISS-001",
        environment="test",
        environment_path=str(project),
        source="gate",
        state=IssueState.NEW,
        affected_change="the-parent",
        change_name="fix-iss-007-the-parent",
    )
    registry = IssueRegistry(project)
    registry._issues[issue.id] = issue
    registry.save()

    mgr = IssueManager(
        registry=registry,
        audit=AuditLog(project),
        policy=PolicyEngine(IssuesPolicyConfig()),
    )
    resolved = mgr._check_affected_change_merged(issue)

    assert resolved is True
    assert issue.state == IssueState.RESOLVED
    # Orphan purged
    assert not child_dir.exists()
    state = json.loads(state_file.read_text())
    assert all(c["name"] != "fix-iss-007-the-parent" for c in state["changes"])


# --- Escalation idempotency ------------------------------------------------


def test_escalation_returns_existing_link_when_live(project: Path) -> None:
    """Re-escalation for a parent with a live fix_iss_child link must return
    the existing name without creating a duplicate."""
    from set_orch.issues.manager import escalate_change_to_fix_iss

    # escalate_change_to_fix_iss resolves openspec/ by walking up from the
    # state_file's dirname. Writing state at project root makes it find our
    # openspec/changes/ correctly.
    state_file = project / "orchestration-state.json"
    child_dir = project / "openspec" / "changes" / "fix-iss-001-the-parent"
    child_dir.mkdir()
    (child_dir / "proposal.md").write_text("existing")
    _write_state(state_file, [
        {
            "name": "the-parent", "scope": "s", "status": "failed:token_runaway",
            "phase": 1, "fix_iss_child": "fix-iss-001-the-parent",
        },
        {
            "name": "fix-iss-001-the-parent", "scope": "s",
            "status": "pending", "phase": 2,
        },
    ])

    result = escalate_change_to_fix_iss(
        state_file=str(state_file),
        change_name="the-parent",
        stop_gate="verify",
        escalation_reason="merge_stalled",
    )

    assert result == "fix-iss-001-the-parent"
    # Dir content untouched (no new proposal written)
    assert (child_dir / "proposal.md").read_text() == "existing"
    # No fix-iss-002 created
    assert not (project / "openspec" / "changes" / "fix-iss-002-the-parent").exists()


def test_escalation_auto_repairs_stale_link_when_dir_missing(project: Path) -> None:
    """When `parent.fix_iss_child` points at a gone dir, escalate clears the
    stale link and creates a fresh child."""
    from set_orch.issues.manager import escalate_change_to_fix_iss

    state_file = project / "orchestration-state.json"
    _write_state(state_file, [{
        "name": "the-parent", "scope": "s", "status": "failed:token_runaway",
        "phase": 1, "fix_iss_child": "fix-iss-003-the-parent",  # dir doesn't exist
    }])

    result = escalate_change_to_fix_iss(
        state_file=str(state_file),
        change_name="the-parent",
        stop_gate="verify",
        escalation_reason="merge_stalled",
    )

    # Fresh child was claimed (NNN differs from the stale link or re-uses slot)
    assert result.startswith("fix-iss-")
    assert (project / "openspec" / "changes" / result / "proposal.md").exists()
    # Parent's fix_iss_child was cleared then set to the new name
    state = json.loads(state_file.read_text())
    parent = next(c for c in state["changes"] if c["name"] == "the-parent")
    assert parent.get("fix_iss_child") == result


def test_escalation_first_time_unchanged(project: Path) -> None:
    """A parent with no prior link behaves exactly as before the change."""
    from set_orch.issues.manager import escalate_change_to_fix_iss

    state_file = project / "orchestration-state.json"
    _write_state(state_file, [{
        "name": "the-parent", "scope": "s", "status": "failed:token_runaway",
        "phase": 1,
    }])

    result = escalate_change_to_fix_iss(
        state_file=str(state_file),
        change_name="the-parent",
        stop_gate="verify",
        escalation_reason="retry_budget_exhausted",
    )

    assert result.startswith("fix-iss-")
    assert (project / "openspec" / "changes" / result).is_dir()
    state = json.loads(state_file.read_text())
    parent = next(c for c in state["changes"] if c["name"] == "the-parent")
    assert parent.get("fix_iss_child") == result


# --- End-to-end regression -------------------------------------------------


def test_full_lifecycle_native_merge_then_reescalate(project: Path) -> None:
    """Complete scenario: parent auto-resolves (orphan purged), then same
    parent re-escalates (clean slate, no collision).

    Uses the RUNTIME state path for the auto-resolve step (where
    LineagePaths resolves) and the SAME path for escalation so both
    operations see a consistent state.
    """
    from set_orch.issues.manager import (
        IssueManager, escalate_change_to_fix_iss,
    )
    from set_orch.issues.registry import IssueRegistry
    from set_orch.issues.audit import AuditLog
    from set_orch.issues.policy import PolicyEngine, IssuesPolicyConfig
    from set_orch.issues.models import Issue, IssueState

    # Runtime state path — LineagePaths + auto-resolve read here.
    # escalate_change_to_fix_iss walks up from state_file's dir looking for
    # openspec/ — the runtime path is deep under xdg/, so we need a
    # different strategy: seed openspec/ at the tmp root too, and ensure
    # the walk finds it.
    state_file = _runtime_state_file(project)
    # Create openspec dir relative to state_file so escalate walks up and finds it
    openspec_dir = state_file.parent.parent / "openspec" / "changes"
    openspec_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: first escalation creates fix-iss-001
    _write_state(state_file, [{
        "name": "p", "scope": "s", "status": "failed:token_runaway", "phase": 1,
    }])
    first = escalate_change_to_fix_iss(
        state_file=str(state_file), change_name="p",
        stop_gate="verify", escalation_reason="token_runaway",
    )
    assert first == "fix-iss-001-p"
    assert (openspec_dir / first / "proposal.md").exists()

    # Phase 2: parent merges natively (dispatcher brought it back)
    state = json.loads(state_file.read_text())
    for c in state["changes"]:
        if c["name"] == "p":
            c["status"] = "merged"
    state_file.write_text(json.dumps(state))

    # Register a matching issue so auto-resolve can fire. environment_path
    # is the project root; LineagePaths resolves to the runtime state_file.
    issue = Issue(
        id="ISS-99",
        environment="test",
        environment_path=str(project),
        source="gate",
        state=IssueState.NEW,
        affected_change="p",
        change_name=first,
    )
    registry = IssueRegistry(project)
    registry._issues[issue.id] = issue
    registry.save()

    # The purge helper reads project_path/openspec/changes/ — but escalation
    # put the dir under state_file.parent.parent/openspec/. To make the
    # paths line up, we pass env_path=state_file.parent.parent (same root
    # that escalation used).
    issue.environment_path = str(state_file.parent.parent)

    mgr = IssueManager(
        registry=registry,
        audit=AuditLog(project),
        policy=PolicyEngine(IssuesPolicyConfig()),
    )
    assert mgr._check_affected_change_merged(issue) is True

    # Orphan purged — fix-iss-001 gone from state + disk
    state2 = json.loads(state_file.read_text())
    assert all(c["name"] != first for c in state2["changes"])
    assert not (openspec_dir / first).exists()

    # Phase 3: parent fails again (different trigger) → re-escalate
    for c in state2["changes"]:
        if c["name"] == "p":
            c["status"] = "failed:merge_stalled"
            c["fix_iss_child"] = None
    state_file.write_text(json.dumps(state2))

    second = escalate_change_to_fix_iss(
        state_file=str(state_file), change_name="p",
        stop_gate="merge", escalation_reason="merge_stalled",
    )
    assert second.startswith("fix-iss-")
    assert (openspec_dir / second / "proposal.md").exists()
