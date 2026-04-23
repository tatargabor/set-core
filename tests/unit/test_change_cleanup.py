"""Unit tests for `set_orch.change_cleanup`."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from set_orch.change_cleanup import CleanupResult, cleanup_change_artifacts


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Initialise a real git repo under tmp_path."""
    repo_path = tmp_path / "acme"
    repo_path.mkdir()
    _run(["git", "init", "-q"], cwd=repo_path)
    _run(["git", "checkout", "-q", "-b", "main"], cwd=repo_path)
    _run(["git", "config", "user.email", "t@example.com"], cwd=repo_path)
    _run(["git", "config", "user.name", "t"], cwd=repo_path)
    (repo_path / "README").write_text("seed")
    _run(["git", "add", "-A"], cwd=repo_path)
    _run(["git", "commit", "-q", "-m", "init"], cwd=repo_path)
    return repo_path


def _make_worktree(repo: Path, change: str, *, convention: str = "wt") -> Path:
    """Create a worktree + branch using the given naming convention.

    - convention="wt": `{repo}-wt-{change}` (bash `set-new` default)
    - convention="plain": `{repo}-{change}` (Python dispatcher direct-add)
    """
    if convention == "wt":
        wt_path = repo.parent / f"{repo.name}-wt-{change}"
    else:
        wt_path = repo.parent / f"{repo.name}-{change}"
    branch = f"change/{change}"
    r = _run(
        ["git", "worktree", "add", "-b", branch, str(wt_path)],
        cwd=repo,
    )
    assert r.returncode == 0, f"worktree add failed: {r.stderr}"
    return wt_path


def test_worktree_and_branch_both_present(repo: Path) -> None:
    wt = _make_worktree(repo, "foo")
    assert wt.is_dir()

    result = cleanup_change_artifacts("foo", str(repo))

    assert result.worktree_removed is True
    assert result.branch_removed is True
    assert result.warnings == []
    assert not wt.exists()
    # Branch gone
    r = _run(["git", "rev-parse", "--verify", "change/foo"], cwd=repo)
    assert r.returncode != 0


def test_worktree_already_removed_on_disk(repo: Path) -> None:
    # Create a branch only, no worktree
    _run(["git", "branch", "change/foo"], cwd=repo)

    result = cleanup_change_artifacts("foo", str(repo))

    assert result.worktree_removed is False
    assert result.branch_removed is True
    assert result.warnings == []


def test_branch_already_deleted(repo: Path) -> None:
    # Worktree with branch, then force-delete branch file but keep dir
    wt = _make_worktree(repo, "foo")
    _run(["git", "worktree", "remove", "--force", str(wt)], cwd=repo)
    _run(["git", "branch", "-D", "change/foo"], cwd=repo)

    result = cleanup_change_artifacts("foo", str(repo))

    # Nothing left to clean
    assert result.worktree_removed is False
    assert result.branch_removed is False
    assert result.warnings == []


def test_repeated_invocation_is_idempotent(repo: Path) -> None:
    _make_worktree(repo, "foo")
    first = cleanup_change_artifacts("foo", str(repo))
    assert first.worktree_removed is True
    assert first.branch_removed is True

    second = cleanup_change_artifacts("foo", str(repo))
    assert second.worktree_removed is False
    assert second.branch_removed is False
    assert second.warnings == []


def test_unregistered_worktree_fallback(repo: Path) -> None:
    """Directory exists at the canonical path but is NOT a registered worktree."""
    orphan = repo.parent / f"{repo.name}-wt-foo"
    orphan.mkdir()
    (orphan / "file").write_text("orphan")

    result = cleanup_change_artifacts("foo", str(repo))

    assert result.worktree_removed is True
    assert any("not registered" in w for w in result.warnings)
    assert not orphan.exists()


def test_both_naming_conventions_recognised(repo: Path) -> None:
    """When both `{project}-{name}` and `{project}-wt-{name}` exist, both removed."""
    wt_bash = _make_worktree(repo, "foo", convention="wt")
    # Create the Python-convention variant manually (git won't allow the same
    # branch, so use a detached HEAD)
    plain_path = repo.parent / f"{repo.name}-foo"
    r = _run(
        ["git", "worktree", "add", "--detach", str(plain_path), "HEAD"],
        cwd=repo,
    )
    assert r.returncode == 0, f"plain-convention worktree add failed: {r.stderr}"

    assert wt_bash.is_dir()
    assert plain_path.is_dir()

    result = cleanup_change_artifacts("foo", str(repo))

    assert result.worktree_removed is True
    assert not wt_bash.exists()
    assert not plain_path.exists()


def test_no_artifacts_all_absent(repo: Path) -> None:
    result = cleanup_change_artifacts("never-existed", str(repo))
    assert isinstance(result, CleanupResult)
    assert result.worktree_removed is False
    assert result.branch_removed is False
    assert result.warnings == []


def test_empty_args_warn(repo: Path) -> None:
    result = cleanup_change_artifacts("", str(repo))
    assert result.worktree_removed is False
    assert result.branch_removed is False
    assert any("empty args" in w for w in result.warnings)


def test_missing_project_path_warn(tmp_path: Path) -> None:
    bogus = tmp_path / "does-not-exist"
    result = cleanup_change_artifacts("foo", str(bogus))
    assert result.worktree_removed is False
    assert result.branch_removed is False
    assert any("does not exist" in w for w in result.warnings)


def test_cleanup_result_has_expected_fields() -> None:
    r = CleanupResult()
    assert hasattr(r, "worktree_removed")
    assert hasattr(r, "branch_removed")
    assert hasattr(r, "warnings")
    assert r.warnings == []
