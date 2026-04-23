"""Regression tests for the fix-merge-worktree-collision change.

Seeds the exact failure modes observed in a production incident (reset
leaves artifacts → dispatcher bumps to `-2` → merger retries in a tight
loop) and verifies the new cleanup + circuit-breaker paths prevent them.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from set_orch.change_cleanup import cleanup_change_artifacts
from set_orch.dispatcher import _unique_worktree_name


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "acme"
    repo_path.mkdir()
    _run(["git", "init", "-q"], cwd=repo_path)
    _run(["git", "checkout", "-q", "-b", "main"], cwd=repo_path)
    _run(["git", "config", "user.email", "t@t"], cwd=repo_path)
    _run(["git", "config", "user.name", "t"], cwd=repo_path)
    (repo_path / "README").write_text("seed")
    _run(["git", "add", "-A"], cwd=repo_path)
    _run(["git", "commit", "-q", "-m", "init"], cwd=repo_path)
    return repo_path


def test_cleanup_prevents_collision_on_redispatch(repo: Path) -> None:
    """Reproduces the observed incident: change was reset, artifacts stayed,
    next dispatch bumped to `-2`. With cleanup, re-dispatch picks the
    canonical (unsuffixed) name."""
    # Seed the pre-reset state: worktree + branch exist on disk
    wt_path = repo.parent / "acme-wt-foo"
    _run(["git", "worktree", "add", "-b", "change/foo", str(wt_path)], cwd=repo)
    assert wt_path.is_dir()

    # --- BEFORE FIX: dispatcher would bump to -2 because of the collision ---
    # Simulate the old behavior: reset state without cleanup, then call
    # _unique_worktree_name. It would return "foo-2".
    bumped = _unique_worktree_name(str(repo), "foo")
    assert bumped == "foo-2"  # collision detected

    # --- AFTER FIX: cleanup removes artifacts before re-dispatch ---
    result = cleanup_change_artifacts("foo", str(repo))
    assert result.worktree_removed is True
    assert result.branch_removed is True
    assert not wt_path.exists()

    # Now the collision is gone; dispatcher picks the canonical name
    fresh = _unique_worktree_name(str(repo), "foo")
    assert fresh == "foo"  # no collision, no suffix bump


def test_cleanup_is_idempotent_for_recovery_overlap(repo: Path) -> None:
    """If recovery's plan-driven path already removed the artifacts, the
    circuit-breaker's call to `cleanup_change_artifacts` must be a safe no-op."""
    # Never created a worktree → cleanup should be no-op
    r1 = cleanup_change_artifacts("never-lived", str(repo))
    assert not r1.worktree_removed
    assert not r1.branch_removed
    assert r1.warnings == []

    # Create + remove manually (simulating recovery), then cleanup as no-op
    wt = repo.parent / "acme-wt-gone"
    _run(["git", "worktree", "add", "-b", "change/gone", str(wt)], cwd=repo)
    _run(["git", "worktree", "remove", "--force", str(wt)], cwd=repo)
    _run(["git", "branch", "-D", "change/gone"], cwd=repo)

    r2 = cleanup_change_artifacts("gone", str(repo))
    assert not r2.worktree_removed
    assert not r2.branch_removed
    assert r2.warnings == []


def test_merge_stall_threshold_triggers_escalation() -> None:
    """Smoke test: verify the merger module imports the stall threshold
    and that the escalation code path exists at the expected location."""
    from set_orch import merger
    assert merger.DEFAULT_MERGE_STALL_THRESHOLD == 6

    # Verify the escalation reference chain exists
    from set_orch.issues.manager import escalate_change_to_fix_iss
    # Function signature accepts our planned kwargs
    import inspect
    sig = inspect.signature(escalate_change_to_fix_iss)
    params = sig.parameters
    assert "state_file" in params
    assert "change_name" in params
    assert "stop_gate" in params
    assert "escalation_reason" in params
    assert "event_bus" in params


def test_reset_change_to_pending_clears_stall_counter() -> None:
    """reset_change_to_pending must clear `merge_stall_attempts` so a
    re-dispatched change starts fresh."""
    from set_orch.recovery import reset_change_to_pending
    from set_orch.state import Change

    ch = Change(name="x", scope="s")
    ch.extras["merge_stall_attempts"] = 5
    ch.extras["ff_retry_count"] = 3
    ch.extras["total_merge_attempts"] = 7
    ch.extras["user_custom"] = "preserve-me"

    reset_change_to_pending(ch)

    assert "merge_stall_attempts" not in ch.extras
    assert "ff_retry_count" not in ch.extras
    assert "total_merge_attempts" not in ch.extras
    # User-defined extras preserved
    assert ch.extras.get("user_custom") == "preserve-me"


def test_retry_parent_after_resolved_calls_cleanup_first(tmp_path: Path, repo: Path) -> None:
    """Integration test: `_retry_parent_after_resolved` must invoke
    `cleanup_change_artifacts` BEFORE `reset_change_to_pending`, and the
    combined effect is: disk artifacts gone, state back to pending, stall
    counter cleared."""
    from set_orch.issues.manager import IssueManager
    from set_orch.issues.registry import IssueRegistry
    from set_orch.issues.audit import AuditLog
    from set_orch.issues.policy import PolicyEngine, IssuesPolicyConfig
    from set_orch.issues.models import Issue, IssueState

    # Seed worktree + branch for a "failed:merge_stalled" change
    wt = repo.parent / "acme-wt-stalled"
    _run(["git", "worktree", "add", "-b", "change/stalled", str(wt)], cwd=repo)
    assert wt.is_dir()

    # Seed state.json with the parent in failed:merge_stalled.
    # `merge_stall_attempts` is serialized as a top-level key (Change.to_dict
    # flattens extras into the change dict); Change.from_dict routes unknown
    # keys back into `extras`.
    state_file = repo / "orchestration-state.json"
    state_file.write_text(json.dumps({
        "status": "running",
        "plan_version": 1,
        "changes": [{
            "name": "stalled",
            "scope": "",
            "status": "failed:merge_stalled",
            "phase": 1,
            "merge_stall_attempts": 6,
        }],
        "merge_queue": [],
    }))

    # Build a minimal Issue manually (the hook reads source, affected_change,
    # environment_path, and id).
    issue = Issue(
        id="ISS-test",
        environment="test",
        environment_path=str(repo),
        source="circuit-breaker:merge_stalled",
        state=IssueState.RESOLVED,
        error_summary="merge stall",
        error_detail="x",
        affected_change="stalled",
    )

    # Minimal IssueManager
    registry = IssueRegistry(repo)
    audit = AuditLog(repo)
    policy = PolicyEngine(IssuesPolicyConfig())
    mgr = IssueManager(registry=registry, audit=audit, policy=policy)

    mgr._retry_parent_after_resolved(issue)

    # Artifacts gone
    assert not wt.exists(), "cleanup should have removed worktree"
    # State flipped back to pending
    state = json.loads(state_file.read_text())
    assert state["changes"][0]["status"] == "pending"
    # Stall counter cleared (via reset_change_to_pending — extras are
    # flattened to top-level on save, so it would reappear as a top-level
    # key if still present in ch.extras).
    assert "merge_stall_attempts" not in state["changes"][0]
