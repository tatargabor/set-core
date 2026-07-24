"""The loss-free guarantee of `set-project prune`, proven rather than asserted.

The user's constraint on this tool is that nothing may be lost from disk and a
project whose directory exists may not be deleted. "There is no `rm` in this
module" is a review claim, and review claims decay — and a grep cannot see into
a dependency. So the central test here hashes the whole fixture tree before and
after a full prune and demands byte-equality outside the two places a prune is
allowed to touch.

That test fails if destruction is ever introduced anywhere in the call graph.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch import project_registry  # noqa: E402
from set_orch import registry_prune as rp  # noqa: E402


# ─── Fixtures ─────────────────────────────────────────────────────────


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )


def _make_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(root.parent, "init", "-q", root.name)
    (root / "file.txt").write_text("content\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    return root


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A registry plus: a live project with a live worktree and an orphaned one,
    a project whose directory was deleted, and one on a missing mount."""
    home = tmp_path / "home"
    (home / ".config" / "set-core").mkdir(parents=True)
    registry = home / ".config" / "set-core" / "projects.json"

    live = _make_repo(tmp_path / "live")
    # A worktree that stays, and one whose directory we delete to orphan its record.
    _git(live, "worktree", "add", "-q", "-b", "change/keep", str(tmp_path / "live-wt-keep"))
    _git(live, "worktree", "add", "-q", "-b", "change/orphan", str(tmp_path / "live-wt-orphan"))
    import shutil
    shutil.rmtree(tmp_path / "live-wt-orphan")

    gone = tmp_path / "gone"          # parent (tmp_path) exists → deregistrable
    unreachable = tmp_path / "no-mount" / "proj"   # parent missing → unknown

    registry.write_text(json.dumps({
        "projects": {
            "live": {"path": str(live), "addedAt": "2026-01-01"},
            "gone": {"path": str(gone), "addedAt": "2026-01-01"},
            "unreachable": {"path": str(unreachable), "addedAt": "2026-01-01"},
        },
        "default": "gone",
    }, indent=2))

    monkeypatch.setattr(project_registry, "PROJECTS_FILE", registry)
    return {"root": tmp_path, "registry": registry, "live": live,
            "keep_wt": tmp_path / "live-wt-keep"}


def _hash_tree(root: Path, skip: tuple[str, ...]) -> dict[str, str]:
    """Content hash of every file under root, excluding paths matching `skip`."""
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if any(s in rel for s in skip):
            continue
        if p.is_symlink():
            out[rel] = "symlink:" + os.readlink(p)
        elif p.is_file():
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        elif p.is_dir():
            out[rel] = "dir"
    return out


# ─── The guarantee ────────────────────────────────────────────────────


def test_a_full_prune_leaves_the_tree_byte_identical(tree):
    """AC-1. The only permitted deltas are the registry file and git's own
    worktree administration. Everything else — including every file inside every
    project — must be untouched."""
    skip = ("projects.json", ".git/worktrees", ".git\\worktrees")
    before = _hash_tree(tree["root"], skip)

    report = rp.run_prune(preview=False)
    assert report.deregistered == ["gone"], report.to_dict()

    after = _hash_tree(tree["root"], skip)
    assert after == before, {
        "vanished": sorted(set(before) - set(after)),
        "appeared": sorted(set(after) - set(before)),
        "changed": sorted(k for k in set(before) & set(after) if before[k] != after[k]),
    }


def test_a_branch_behind_an_orphaned_worktree_survives(tree):
    """AC-2. `git worktree prune` discards a record; the branch and its commit
    are not its business. If a future edit reaches for `worktree remove`, or for
    a branch delete, this is what catches it."""
    live = tree["live"]
    sha_before = _git(live, "rev-parse", "change/orphan").stdout.strip()

    report = rp.run_prune(preview=False)
    assert report.worktree_count == 1, report.to_dict()

    sha_after = _git(live, "rev-parse", "change/orphan").stdout.strip()
    assert sha_after == sha_before
    branches = _git(live, "branch", "--format=%(refname:short)").stdout.split()
    assert "change/orphan" in branches
    assert "change/keep" in branches


def test_a_live_worktree_is_untouched(tree):
    """AC-6. The surviving worktree keeps both its directory and its record."""
    rp.run_prune(preview=False)
    assert tree["keep_wt"].is_dir()
    listing = _git(tree["live"], "worktree", "list", "--porcelain").stdout
    assert str(tree["keep_wt"]) in listing
    assert "prunable" not in listing


def test_no_prunable_records_means_git_is_not_mutated(tmp_path, monkeypatch):
    """AC-7. A clean repository is not written to at all — `worktree prune` is
    never invoked. Asserted on the argv, because "it would have been harmless"
    is not the claim being made."""
    home = tmp_path / "home"
    (home / ".config" / "set-core").mkdir(parents=True)
    registry = home / ".config" / "set-core" / "projects.json"
    clean = _make_repo(tmp_path / "clean")
    registry.write_text(json.dumps({"projects": {"clean": {"path": str(clean)}}}))
    monkeypatch.setattr(project_registry, "PROJECTS_FILE", registry)

    calls: list[list[str]] = []
    real = rp._run_git

    def spy(project_path, args):
        calls.append(list(args))
        return real(project_path, args)

    monkeypatch.setattr(rp, "_run_git", spy)
    rp.run_prune(preview=False)

    assert calls == [["worktree", "list", "--porcelain"]], calls


def test_the_module_refuses_a_destructive_git_verb(tmp_path):
    """The guard exists so that a later edit fails at the call site rather than
    in production. Not a behaviour test — a tripwire."""
    repo = _make_repo(tmp_path / "r")
    for args in (["worktree", "remove", "x"], ["branch", "-D", "x"],
                 ["worktree", "prune", "--expire", "now"], ["clean", "-fd"]):
        with pytest.raises(ValueError):
            rp._run_git(repo, args)


# ─── Classification ───────────────────────────────────────────────────


def test_a_live_directory_is_never_deregistered(tmp_path):
    """AC-3. Old, empty, no git, no orchestration state — still kept. The only
    fact that may deregister is that the directory is gone."""
    empty = tmp_path / "empty"
    empty.mkdir()
    old = tmp_path / "old"
    old.mkdir()
    os.utime(old, (0, 0))  # 1970

    cls = rp.classify_entries([
        {"name": "empty", "path": str(empty)},
        {"name": "old", "path": str(old)},
    ])
    assert cls.deregistrable == []
    assert {e["name"] for e in cls.kept} == {"empty", "old"}


def test_a_deleted_directory_is_deregistered(tmp_path):
    """AC-4."""
    cls = rp.classify_entries([{"name": "gone", "path": str(tmp_path / "gone")}])
    assert [e["name"] for e in cls.deregistrable] == ["gone"]


def test_an_unmounted_filesystem_is_kept_not_deregistered(tmp_path):
    """AC-5. `isdir()` is False for a deleted directory and for an unmounted one
    alike; the parent check is what tells them apart. Being wrong toward "remove"
    destroys a registration with no record it existed."""
    cls = rp.classify_entries([
        {"name": "nas", "path": str(tmp_path / "no-mount" / "proj")},
    ])
    assert cls.deregistrable == []
    assert [e["name"] for e in cls.unreachable] == ["nas"]


def test_the_unreachable_entry_survives_a_real_prune(tree):
    """The classification means nothing if the writer drops the entry anyway."""
    rp.run_prune(preview=False)
    remaining = json.loads(tree["registry"].read_text())["projects"]
    assert "unreachable" in remaining
    assert "live" in remaining
    assert "gone" not in remaining


def test_a_deregistered_default_is_cleared(tree):
    """A preserved `default` pointing at a removed entry reads exactly like a
    configured one to everything downstream."""
    rp.run_prune(preview=False)
    assert json.loads(tree["registry"].read_text())["default"] is None
