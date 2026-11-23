"""The relation map shows where an agent works (worktree, branch) and what its context holds.

Asked 2026-11-23 from the map screen: the worktree should be visible, and the context size
and consumption, as long as it costs little. The usage figures are COPIED from the listing
row; the only new measurement is one `git worktree list` per project with an agent outside
its root.
"""

from __future__ import annotations

import subprocess

import pytest

from set_orch.api import fleet_mandate as fm


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo_with_worktree(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    _git("init", "-q", "-b", "main", cwd=root)
    _git("-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i", cwd=root)
    wt = tmp_path / "proj-wt-feature"
    _git("worktree", "add", "-q", "-b", "feature-x", str(wt), cwd=root)
    (wt / "sub").mkdir()
    return root, wt


def test_an_agent_in_a_worktree_names_it_and_its_branch(repo_with_worktree):
    root, wt = repo_with_worktree
    row = {"project_root": str(root), "cwd": str(wt / "sub"), "branch": "feature-x"}
    assert fm._worktree_of(row, {}) == {"name": "proj-wt-feature", "branch": "feature-x"}


def test_an_agent_in_the_main_tree_has_no_worktree_and_costs_no_git_call(repo_with_worktree, monkeypatch):
    root, _ = repo_with_worktree
    monkeypatch.setattr(fm, "_worktrees_of", lambda r: pytest.fail("git was called for the main tree"))
    assert fm._worktree_of({"project_root": str(root), "cwd": str(root), "branch": "main"}, {}) is None


def test_one_git_call_per_project(repo_with_worktree, monkeypatch):
    root, wt = repo_with_worktree
    calls = []
    real = fm._worktrees_of
    monkeypatch.setattr(fm, "_worktrees_of", lambda r: calls.append(r) or real(r))
    cache = {}
    for _ in range(3):
        fm._worktree_of({"project_root": str(root), "cwd": str(wt)}, cache)
    assert calls == [str(root)]


def test_outside_the_root_and_in_no_worktree_is_said_not_guessed(tmp_path, repo_with_worktree):
    root, _ = repo_with_worktree
    stray = tmp_path / "elsewhere"
    stray.mkdir()
    got = fm._worktree_of({"project_root": str(root), "cwd": str(stray), "branch": None}, {})
    assert got == {"name": None, "branch": None, "unlisted": True}


def test_usage_is_copied_from_the_row_and_nothing_else():
    row = {"context": {"state": "measured", "fill": 0.37, "band": "normal", "tokens": 370_000,
                       "window": 1_000_000, "model": "claude-opus-5-5", "reason": "x"},
           "cache": {"cold": False, "rewrite_usd": 2.9, "seconds_remaining": 3000, "tokens": 1, "model": "m"}}
    got = fm._usage_of(row)
    assert got["context"] == {"state": "measured", "fill": 0.37, "band": "normal", "tokens": 370_000,
                              "window": 1_000_000, "model": "claude-opus-5-5"}
    assert got["cache"] == {"cold": False, "rewrite_usd": 2.9, "seconds_remaining": 3000}
    assert fm._usage_of({}) == {"context": {}}
