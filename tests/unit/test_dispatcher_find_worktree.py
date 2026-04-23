"""Unit tests for `dispatcher._find_existing_worktree` and `_match_worktree_basename`."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from set_orch.dispatcher import (
    _find_existing_worktree,
    _match_worktree_basename,
)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
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


# --- Unit-level tests for the basename matcher --------------------------


def test_basename_match_plain_convention() -> None:
    assert _match_worktree_basename("acme-foo", "acme", "foo") == 0
    assert _match_worktree_basename("acme-foo-2", "acme", "foo") == 2
    assert _match_worktree_basename("acme-foo-7", "acme", "foo") == 7


def test_basename_match_wt_convention() -> None:
    assert _match_worktree_basename("acme-wt-foo", "acme", "foo") == 0
    assert _match_worktree_basename("acme-wt-foo-3", "acme", "foo") == 3


def test_basename_no_substring_false_positive() -> None:
    # `foo` should NOT match `foobar`
    assert _match_worktree_basename("acme-foobar", "acme", "foo") is None
    assert _match_worktree_basename("acme-wt-foobar-2", "acme", "foo") is None
    # Different project
    assert _match_worktree_basename("other-foo", "acme", "foo") is None


def test_basename_non_numeric_suffix_ignored() -> None:
    # `foo-bar` is not a numeric suffix of `foo`
    assert _match_worktree_basename("acme-foo-bar", "acme", "foo") is None


# --- Integration-level tests with a real git repo ----------------------


def _add_worktree(repo: Path, dir_path: Path, branch: str) -> None:
    r = _run(["git", "worktree", "add", "-b", branch, str(dir_path)], cwd=repo)
    assert r.returncode == 0, f"worktree add failed: {r.stderr}"


def test_single_match_returned(repo: Path) -> None:
    wt = repo.parent / "acme-wt-foo"
    _add_worktree(repo, wt, "change/foo")
    result = _find_existing_worktree(str(repo), "foo")
    assert result == str(wt)


def test_no_match_returns_conventional_path(repo: Path) -> None:
    result = _find_existing_worktree(str(repo), "nonexistent")
    assert result == str(repo) + "-nonexistent"


def test_highest_suffix_wins_bash_convention(repo: Path) -> None:
    wt1 = repo.parent / "acme-wt-foo"
    wt2 = repo.parent / "acme-wt-foo-2"
    _add_worktree(repo, wt1, "change/foo")
    _add_worktree(repo, wt2, "change/foo-2")

    result = _find_existing_worktree(str(repo), "foo")
    assert result == str(wt2)


def test_highest_suffix_across_both_conventions(repo: Path) -> None:
    wt_bash = repo.parent / "acme-wt-foo"
    wt_plain_2 = repo.parent / "acme-foo-2"
    _add_worktree(repo, wt_bash, "change/foo")
    _add_worktree(repo, wt_plain_2, "change/foo-2-variant")

    result = _find_existing_worktree(str(repo), "foo")
    assert result == str(wt_plain_2)


def test_substring_change_not_matched(repo: Path) -> None:
    """A worktree named for `foobar` must NOT match `foo`."""
    wt_decoy = repo.parent / "acme-wt-foobar"
    _add_worktree(repo, wt_decoy, "change/foobar")

    result = _find_existing_worktree(str(repo), "foo")
    # No match for "foo" — return the conventional would-be path
    assert result == str(repo) + "-foo"
