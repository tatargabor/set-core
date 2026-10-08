"""Project facts: root resolution, the ignore guard, worktree detection."""

from __future__ import annotations

import pytest

from conftest_kb import git, make_repo, write
from set_kb.indexer import AtomicIndexSource, RunIndexAtomicOpts, run_index_atomic
from set_kb.project import ProjectError, ensure_ignored, index_paths, main_checkout, resolve_root, seed_from_main


def test_resolve_root_from_a_subdirectory(tmp_path):
    """AC: searching from any folder in the project uses the project root."""
    root = make_repo(tmp_path)
    sub = write(root / "docs" / "deep" / "keep.md", "# x")
    assert resolve_root(sub.parent) == str(root.resolve())


def test_outside_a_repository_is_loud(tmp_path):
    """AC: outside a repository the engine says no project was found."""
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    with pytest.raises(ProjectError, match="no project found"):
        resolve_root(outside)


def test_index_paths_live_at_set_kb(tmp_path):
    root = make_repo(tmp_path)
    db, lock = index_paths(root)
    assert db.endswith("/.set/kb/index.db") and lock.endswith("/.set/kb/index.lock")


def test_ignored_index_passes_the_guard(tmp_path):
    root = make_repo(tmp_path)  # .gitignore already covers .set/
    db, _lock = index_paths(root)
    ensure_ignored(root, db)  # no raise; works for a path that does not exist yet


def test_unignored_index_is_refused_by_name(tmp_path):
    """AC: WHEN `.set/` is not covered THEN the engine refuses to build, names
    the path, and tells the caller to ignore it."""
    root = make_repo(tmp_path, gitignored=False)
    db, _lock = index_paths(root)
    with pytest.raises(ProjectError) as e:
        ensure_ignored(root, db)
    msg = str(e.value)
    assert ".set/kb/index.db" in msg and "refusing" in msg and ".gitignore" in msg


def test_index_never_staged_after_a_build(tmp_path):
    """AC: WHEN a search built or refreshed the index THEN `git status` lists
    nothing under `.set/kb/`."""
    root = make_repo(tmp_path)
    write(root / "note.md", "# Note\n\n" + "word " * 30 + "\n")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "corpus")
    db, lock = index_paths(root)
    ensure_ignored(root, db)
    run_index_atomic(RunIndexAtomicOpts(db_path=db, sources=[AtomicIndexSource(id="", dir=str(root))]))
    status = git(root, "status", "--porcelain")
    assert status.strip() == "", "the index and its sidecars are invisible to git"


def test_main_checkout_none_in_the_main_checkout(tmp_path):
    root = make_repo(tmp_path)
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "init")
    assert main_checkout(root) is None


def test_main_checkout_found_from_a_linked_worktree(tmp_path):
    root = make_repo(tmp_path)
    write(root / "note.md", "# Note\n\n" + "word " * 30 + "\n")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "init")
    wt = tmp_path / "wt"
    git(root, "worktree", "add", "-q", "-b", "feat", str(wt))
    assert main_checkout(wt) == str(root.resolve())
    assert main_checkout(root) is None


def test_seed_copies_the_main_index_once(tmp_path):
    """A worktree without an index gets the main checkout's; a worktree WITH
    an index (or the main checkout itself) gets nothing."""
    root = make_repo(tmp_path)
    write(root / "note.md", "# Note\n\n" + "word " * 30 + "\n")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "init")
    db, _lock = index_paths(root)
    run_index_atomic(RunIndexAtomicOpts(db_path=db, sources=[AtomicIndexSource(id="", dir=str(root))]))
    wt = tmp_path / "wt"
    git(root, "worktree", "add", "-q", "-b", "feat", str(wt))
    wt_db, _wt_lock = index_paths(wt)
    assert seed_from_main(wt, wt_db) is True and wt_db and __import__("os").path.exists(wt_db)
    assert seed_from_main(wt, wt_db) is False, "an existing index is never overwritten by a seed"
    assert seed_from_main(root, index_paths(root)[0]) is False, "the main checkout does not seed from itself"
