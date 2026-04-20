"""Unit tests for divergent-plan reconciliation (section 6 of
fix-replan-stuck-gate-and-decomposer).

Exercises `reconcile_divergent_plan()` end-to-end on a real git repo:
- Worktrees whose change is not in the new plan get archived and removed.
- Dirty worktrees trigger stash (or rescue-branch fallback on simulated
  stash failure).
- `change/<name>` branches + `openspec/changes/<name>/` dirs get pruned.
- `fix-iss-*` dirs and `state-archive.jsonl` entries are preserved.
- Manifest is always written — even in `dry_run=True`, no destructive op
  runs but the manifest still lists the planned ops.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.reconciliation import (  # noqa: E402
    ReconciliationSummary,
    divergent_names,
    reconcile_divergent_plan,
    write_cleanup_manifest,
    _stash_worktree,
    _create_rescue_branch,
)


def _git(cwd, *args, check=True):
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=check, capture_output=True, text=True,
    )


@pytest.fixture
def repo(tmp_path):
    """Bare-bones project with a git repo, one worktree for `foo`, a
    `change/foo` branch, and `openspec/changes/foo/`.
    """
    project = tmp_path / "proj"
    project.mkdir()
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "t@t")
    _git(project, "config", "user.name", "t")
    (project / "README.md").write_text("hi")
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "initial")

    # Rename default branch to main
    _git(project, "branch", "-M", "main")

    # Create change/foo branch + worktree
    wt_path = tmp_path / "proj-wt-foo"
    _git(project, "branch", "change/foo")
    _git(project, "worktree", "add", str(wt_path), "change/foo")

    # Create openspec/changes/{foo,bar,fix-iss-001-xyz}
    changes = project / "openspec" / "changes"
    changes.mkdir(parents=True)
    (changes / "foo").mkdir()
    (changes / "foo" / "proposal.md").write_text("foo proposal")
    (changes / "bar").mkdir()
    (changes / "fix-iss-001-xyz").mkdir()
    (changes / "fix-iss-001-xyz" / "proposal.md").write_text("escalation")
    return {"project": project, "wt_path": wt_path, "changes": changes}


def test_divergent_names_symmetric_diff():
    assert divergent_names({"a", "b"}, {"b", "c"}) == {"a", "c"}
    assert divergent_names({"a"}, {"a"}) == set()
    assert divergent_names({}, {"a"}) == {"a"}


def test_manifest_always_written(repo):
    summary = reconcile_divergent_plan(
        str(repo["project"]), new_plan_names={"baz"},  # foo + bar both stale
        dry_run=True,
    )
    assert os.path.isfile(summary.manifest_path)
    content = open(summary.manifest_path).read()
    assert "remove_worktree" in content or "delete_branch" in content
    assert "remove_change_dir" in content


def test_dry_run_leaves_state_intact(repo):
    summary = reconcile_divergent_plan(
        str(repo["project"]), new_plan_names={"baz"},
        dry_run=True,
    )
    assert summary.dry_run is True
    assert summary.worktrees_removed == 0
    assert summary.branches_deleted == 0
    assert summary.change_dirs_removed == 0
    # worktree still present, branch still present, dirs still there
    assert repo["wt_path"].is_dir()
    assert (repo["changes"] / "foo").is_dir()
    r = _git(repo["project"], "branch", "--list", "change/foo")
    assert "change/foo" in r.stdout


def test_full_reconcile_removes_stale_state(repo):
    summary = reconcile_divergent_plan(
        str(repo["project"]), new_plan_names={"baz"},
        dry_run=False,
    )
    assert summary.worktrees_removed >= 1
    assert summary.branches_deleted >= 1
    assert summary.change_dirs_removed >= 2  # foo + bar

    # fix-iss-001-xyz preserved
    assert (repo["changes"] / "fix-iss-001-xyz").is_dir()
    # foo + bar gone
    assert not (repo["changes"] / "foo").is_dir()
    assert not (repo["changes"] / "bar").is_dir()


def test_partial_overlap_keeps_shared(repo):
    """foo in both plans → foo should NOT be touched."""
    summary = reconcile_divergent_plan(
        str(repo["project"]), new_plan_names={"foo", "baz"},
        dry_run=False,
    )
    # bar was in state but not in new plan → removed. foo preserved.
    assert repo["wt_path"].is_dir()
    assert (repo["changes"] / "foo").is_dir()
    assert not (repo["changes"] / "bar").is_dir()
    assert summary.worktrees_removed == 0
    assert summary.change_dirs_removed == 1


def test_dirty_worktree_triggers_stash(repo):
    # Make the worktree dirty
    (repo["wt_path"] / "dirty.txt").write_text("uncommitted")

    summary = reconcile_divergent_plan(
        str(repo["project"]), new_plan_names={"baz"},
        dry_run=False,
    )
    # dirty_forced == 1 and worktree removed
    assert summary.dirty_forced == 1
    assert summary.worktrees_removed == 1
    # A stash ref was recorded
    assert any("foo:stash@" in s for s in summary.stash_refs)


def test_archive_preserved(repo, tmp_path):
    # Add `bar` to state-archive.jsonl → should NOT be removed even if not
    # in the new plan.
    archive = repo["project"] / "state-archive.jsonl"
    archive.write_text(json.dumps({"name": "bar"}) + "\n")

    summary = reconcile_divergent_plan(
        str(repo["project"]), new_plan_names={"baz"},
        dry_run=False,
    )
    # bar is archived → its dir should be kept
    assert (repo["changes"] / "bar").is_dir()
    # foo is NOT archived → its dir + worktree gone
    assert not (repo["changes"] / "foo").is_dir()
    assert not repo["wt_path"].is_dir()


def test_rescue_branch_on_stash_failure(repo, tmp_path):
    """If stash fails (simulated by patching _stash_worktree), the rescue
    branch fallback must create wip/<name>-<epoch> with an unverified
    commit.
    """
    import set_orch.reconciliation as recon

    original_stash = recon._stash_worktree
    def fake_stash(*args, **kwargs):
        return False, "simulated I/O failure"
    recon._stash_worktree = fake_stash
    try:
        (repo["wt_path"] / "dirty.txt").write_text("uncommitted")
        summary = reconcile_divergent_plan(
            str(repo["project"]), new_plan_names={"baz"},
            dry_run=False,
        )
    finally:
        recon._stash_worktree = original_stash

    assert summary.dirty_forced == 1
    assert len(summary.rescue_branches) == 1
    assert summary.rescue_branches[0].startswith("wip/foo-")


def test_summary_is_structured_dict():
    summary = ReconciliationSummary(
        worktrees_removed=2, dirty_forced=1, branches_deleted=3,
    )
    d = summary.to_dict()
    for field in (
        "worktrees_removed", "dirty_skipped", "dirty_forced",
        "pids_cleared", "steps_fixed", "artifacts_collected",
        "merge_queue_entries_restored", "issues_released",
    ):
        assert field in d
