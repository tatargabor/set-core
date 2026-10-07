"""Shared helpers for the kb W2 tests: throwaway project repos and the
default-corpus index run.

A "repo" here is a real git repository under tmp_path — the ignore guard and
the worktree seeding need git, and `git init` inside tmp_path is what the
change's task list prescribes for exactly that reason.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from set_kb.indexer import AtomicIndexSource, IndexOptions, RunIndexAtomicOpts, run_index_atomic
from set_kb.store import SqliteFtsStore

# A throwaway identity, so `git commit` works on a machine with no global set.
GIT_ID = ["-c", "user.email=kb-test@example.invalid", "-c", "user.name=kb test"]


def make_repo(tmp_path, name="repo", gitignored=True) -> Path:
    """A throwaway project directory. `gitignored=True` writes the `.set/`
    ignore entry a real deploy guarantees; the guard tests turn it off."""
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    if gitignored:
        (root / ".gitignore").write_text(".set/\n", encoding="utf-8")
    return root


def git(root: Path, *args: str) -> str:
    """Run git in the repo, identity pinned, stdout returned."""
    r = subprocess.run(
        ["git", "-C", str(root), *GIT_ID, *args], check=True, capture_output=True, text=True, env={**os.environ}
    )
    return r.stdout


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def index_root(tmp_path, root: Path, opts: IndexOptions | None = None, db_name="idx.db") -> SqliteFtsStore:
    """Index `root` as the single (default-corpus) source and return an open
    store. The caller closes it."""
    db = str(tmp_path / db_name)
    run_index_atomic(
        RunIndexAtomicOpts(db_path=db, sources=[AtomicIndexSource(id="", dir=str(root))], index_opts=opts)
    )
    store = SqliteFtsStore(db)
    store.init()
    return store
