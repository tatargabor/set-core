"""Regression: _clean_untracked_merge_conflicts handles git's dir-collapsed form.

Bug surfaced on micro-web-run-20260415-0014:
  The shadcn overlay deployed src/components/ui/*.tsx as untracked files on
  main. When the feature branch committed those files and asked for an
  ff-merge, git refused: "untracked working tree files would be overwritten".

  The existing cleanup function queried `git status --porcelain` but git
  collapses a fully-untracked directory to a single `?? src/components/`
  entry — matching individual file paths (`src/components/ui/button.tsx`)
  against that entry never hit, so cleanup skipped the files and the
  ff-merge failed.

Fix: track dir-level untracked entries and match added files by prefix.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
    )


@pytest.fixture
def repo_with_untracked_dir(tmp_path: Path, monkeypatch):
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("init\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    # Create the feature branch that adds a whole subtree.
    _git(repo, "checkout", "-b", "change/foundation-and-content")
    (repo / "src" / "components" / "ui").mkdir(parents=True)
    (repo / "src" / "components" / "ui" / "button.tsx").write_text("// branch version\n")
    (repo / "src" / "components" / "ui" / "card.tsx").write_text("// branch version\n")
    (repo / "src" / "lib").mkdir()
    (repo / "src" / "lib" / "util.ts").write_text("export const x = 1;\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add components")

    # Back to main, deploy the SAME files as UNTRACKED (mimics scaffold init).
    _git(repo, "checkout", "-q", "main")
    # Depending on git version "main" may be called "master"; tolerate.
    current = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if current != "main":
        _git(repo, "branch", "-M", "main")

    (repo / "src" / "components" / "ui").mkdir(parents=True)
    (repo / "src" / "components" / "ui" / "button.tsx").write_text("// main version\n")
    (repo / "src" / "components" / "ui" / "card.tsx").write_text("// main version\n")
    # Verify git collapses to SOME dir-level (could be src/, src/components/, etc.)
    status = _git(repo, "status", "--porcelain").stdout
    assert "?? src/" in status, f"Expected dir-collapsed untracked entry, got: {status!r}"

    monkeypatch.chdir(repo)
    return repo


def test_cleanup_handles_directory_level_untracked(repo_with_untracked_dir):
    """Given a dir-collapsed untracked entry, cleanup must remove files inside
    it that overlap with the branch's added files."""
    from set_orch.merger import _clean_untracked_merge_conflicts

    _clean_untracked_merge_conflicts("foundation-and-content")

    repo = repo_with_untracked_dir
    # Files that conflict with the branch must be gone.
    assert not (repo / "src" / "components" / "ui" / "button.tsx").exists()
    assert not (repo / "src" / "components" / "ui" / "card.tsx").exists()
    # Empty dir should be pruned so next iteration doesn't re-flag it.
    assert not (repo / "src" / "components").exists()


def test_cleanup_leaves_unrelated_untracked_alone(tmp_path: Path, monkeypatch):
    """Untracked files/dirs the branch does NOT claim must be preserved."""
    from set_orch.merger import _clean_untracked_merge_conflicts

    repo = tmp_path / "r2"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("init\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "checkout", "-b", "change/cart")
    (repo / "src").mkdir()
    (repo / "src" / "cart.ts").write_text("x")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "cart")
    _git(repo, "checkout", "-q", "main")
    current = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if current != "main":
        _git(repo, "branch", "-M", "main")

    # Unrelated untracked content on main.
    (repo / "unrelated").mkdir()
    (repo / "unrelated" / "ignore_me.md").write_text("keep")
    (repo / "noise.txt").write_text("keep")

    monkeypatch.chdir(repo)
    _clean_untracked_merge_conflicts("cart")

    assert (repo / "unrelated" / "ignore_me.md").exists()
    assert (repo / "noise.txt").exists()
