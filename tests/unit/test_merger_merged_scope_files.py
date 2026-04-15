"""Test: _list_merged_scope_files uses pre_merge_sha..HEAD, not main..source.

Observed on craftbrew-run-20260415-0146: foundation-setup and auth-and-accounts
had merged_scope_files=[] after merge. Tier 2 cross-change regression detection
relies on this field to attribute a failing test to its owning merged change;
when empty, the (c) path of resolve_owning_change never fires.

Root cause: the original implementation ran `git log --name-only main..<source>`
AFTER the ff-merge completed. At that point source is an ancestor of main, so
the diff is empty.

Fix: use pre_merge_sha (captured before merge) vs HEAD (post-merge).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
    )


def test_merged_scope_files_captures_new_files_after_ff_merge(tmp_path: Path, monkeypatch):
    from set_orch.merger import _list_merged_scope_files

    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("init\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    # Feature branch adds three files
    _git(repo, "checkout", "-b", "change/cart")
    (repo / "src").mkdir()
    (repo / "src" / "cart.ts").write_text("export const cart = [];\n")
    (repo / "src" / "cart.test.ts").write_text("// test\n")
    (repo / "tests" / "e2e").mkdir(parents=True)
    (repo / "tests" / "e2e" / "cart.spec.ts").write_text("// cart spec\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add cart")

    # Simulate the orchestrator's merge_change: capture pre_merge_sha,
    # then ff-merge into main.
    _git(repo, "checkout", "-q", "main")
    pre_merge_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "merge", "--ff-only", "change/cart")

    monkeypatch.chdir(repo)
    files = _list_merged_scope_files(pre_merge_sha, "change/cart")
    assert "src/cart.ts" in files
    assert "src/cart.test.ts" in files
    assert "tests/e2e/cart.spec.ts" in files
    assert len(files) == 3


def test_merged_scope_files_empty_when_pre_sha_empty(tmp_path: Path, monkeypatch):
    from set_orch.merger import _list_merged_scope_files

    repo = tmp_path / "r2"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "a.txt").write_text("a")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    monkeypatch.chdir(repo)
    # No pre_merge_sha → degrade gracefully, not crash.
    assert _list_merged_scope_files("", "change/whatever") == []


def test_merged_scope_files_returns_empty_on_git_failure(tmp_path: Path, monkeypatch):
    """If git diff fails (e.g., bad sha), return [] instead of raising."""
    from set_orch.merger import _list_merged_scope_files

    repo = tmp_path / "r3"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "a.txt").write_text("a")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    monkeypatch.chdir(repo)
    # Invalid sha → git diff returns non-zero.
    result = _list_merged_scope_files("0" * 40, "nonexistent-branch")
    assert result == []
