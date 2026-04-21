"""Tests for `_resolve_source_branch` — Fix B for the ghost-merge bug.

The merger previously hardcoded `source_branch = f"change/{change_name}"`.
When dispatcher `_unique_worktree_name` had generated a `-N` suffix, this
pointed at an empty sibling branch and Case 2 ("already merged") fired,
silently discarding the agent's work. The resolver now derives the branch
from the worktree's actual HEAD.
"""

import os
import subprocess
from pathlib import Path

import pytest

from set_orch.merger import _resolve_source_branch


def _git(*args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False,
    )


@pytest.fixture
def repo(tmp_path):
    _git("init", cwd=tmp_path)
    _git("checkout", "-b", "main", cwd=tmp_path)
    (tmp_path / "seed.txt").write_text("seed\n")
    _git("add", "-A", cwd=tmp_path)
    _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init", cwd=tmp_path)
    return tmp_path


def _make_worktree(repo: Path, branch: str, dir_suffix: str) -> Path:
    wt_path = repo.parent / f"{repo.name}-wt-{dir_suffix}"
    r = _git("worktree", "add", "-b", branch, str(wt_path), "main", cwd=repo)
    assert r.returncode == 0, r.stderr
    return wt_path


class TestResolveSourceBranch:
    def test_bare_name_used_when_worktree_branch_matches(self, repo):
        wt = _make_worktree(repo, "change/feature-x", "feature-x")
        assert _resolve_source_branch(str(wt), "feature-x") == "change/feature-x"

    def test_suffix_resolved_from_worktree_head(self, repo):
        """The critical scenario: worktree on change/foo-2 while change.name=foo.

        Previously the merger would return 'change/foo' (pointing at the empty
        sibling) instead of 'change/foo-2' (where the agent's work is).
        """
        wt = _make_worktree(repo, "change/email-dispatch-library-2", "email-dispatch-library-2")
        resolved = _resolve_source_branch(str(wt), "email-dispatch-library")
        assert resolved == "change/email-dispatch-library-2"

    def test_fallback_when_worktree_missing(self, repo):
        """If the worktree dir doesn't exist, fall back to the conventional name."""
        missing = str(repo / "does-not-exist")
        assert _resolve_source_branch(missing, "foo") == "change/foo"

    def test_fallback_when_wt_path_empty(self):
        assert _resolve_source_branch("", "foo") == "change/foo"

    def test_fallback_when_head_detached(self, repo):
        wt = _make_worktree(repo, "change/foo", "foo")
        # Detach HEAD
        r = _git("-C", str(wt), "checkout", "--detach", "HEAD", cwd=wt)
        assert r.returncode == 0, r.stderr
        assert _resolve_source_branch(str(wt), "foo") == "change/foo"
