"""Project-level filesystem facts: where the project is, where the index
lives, and why the engine may refuse to write it.

THE IGNORE GUARD IS THE LOAD-BEARING HALF (design D6). The index and its WAL
sidecar carry corpus text verbatim — in a project with client folders that is
client correspondence — so an index that git could commit is a leak waiting
for `git add -A`. Before creating or writing anything under `.set/kb/` the
engine asks GIT whether the path is ignored, and refuses to build when it is
not: naming the path and the remedy beats an index that sits one habit away
from a commit.

Root resolution is GIT's, not a directory walk: `git rev-parse --show-toplevel`
answers for subdirectories and for linked worktrees alike, which is also what
makes worktree seeding (design D6) a copy instead of a rebuild.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# The index directory, under the project root. `.set/` is the runtime
# directory initialized projects already ignore.
INDEX_DIR_REL = os.path.join(".set", "kb")
DB_NAME = "index.db"
LOCK_NAME = "index.lock"


class ProjectError(RuntimeError):
    """The project could not be established (outside a repository, git
    unusable) or the index path is not safe to write."""


def run_git(args: list, cwd) -> str:
    """Run git in the project; stdout on success, a ProjectError that carries
    git's own stderr on failure — the error a caller shows should be git's
    words plus ours, not ours alone."""
    try:
        r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    except FileNotFoundError as e:
        raise ProjectError("kb: git is required to locate the project and guard the index — install git") from e
    if r.returncode != 0:
        detail = (r.stderr or "").strip().splitlines()
        raise ProjectError(f"kb: git {' '.join(args)} failed: {detail[-1] if detail else f'exit {r.returncode}'}")
    return r.stdout


def resolve_root(start_dir) -> str:
    """The repository root for `start_dir` — the project the command serves.
    Outside a repository this is the loud end: there is no project to search,
    and guessing a parent would index the wrong tree confidently."""
    try:
        out = run_git(["rev-parse", "--show-toplevel"], start_dir)
    except ProjectError as e:
        raise ProjectError(f"kb: no project found — {start_dir} is not inside a git repository ({e})") from e
    return out.strip()


def index_paths(root) -> tuple:
    """(db path, lock path) under `<root>/.set/kb/`. Both are RELATIVE facts
    of the root — the index is addressable by the project alone, never by the
    machine's directory layout (design D6)."""
    dir_path = os.path.join(str(root), INDEX_DIR_REL)
    return os.path.join(dir_path, DB_NAME), os.path.join(dir_path, LOCK_NAME)


def ensure_ignored(root, db_path: str) -> None:
    """Refuse to write an index git could commit (AC: runtime directory not
    ignored). `git check-ignore` answers for the exact path — covering
    `.set/` in `.gitignore` is enough, and works for a path that does not
    exist yet, so the guard runs BEFORE anything is created."""
    rel = os.path.relpath(db_path, str(root))
    try:
        r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=str(root), capture_output=True, text=True)
    except FileNotFoundError as e:
        raise ProjectError("kb: git is required to guard the index — install git") from e
    if r.returncode == 0:
        return
    if r.returncode == 1:
        raise ProjectError(
            f"kb: refusing to build the index — '{rel}' is not ignored by git, and the index and its WAL "
            f"carry corpus text verbatim. Add '.set/' to the project's .gitignore, then run the search again."
        )
    detail = (r.stderr or "").strip().splitlines()
    raise ProjectError(f"kb: git check-ignore failed for '{rel}': {detail[-1] if detail else f'exit {r.returncode}'}")


def main_checkout(root) -> "str | None":
    """The main checkout's path when `root` is a LINKED worktree, else None.
    `git worktree list --porcelain` lists the main checkout first (design D6);
    equality is decided on resolved paths, so a trailing-slash or symlink
    difference cannot send us seeding from ourselves."""
    out = run_git(["worktree", "list", "--porcelain"], root)
    first = out.splitlines()[0] if out.splitlines() else ""
    if not first.startswith("worktree "):
        raise ProjectError("kb: could not parse `git worktree list --porcelain` output")
    main = Path(first[len("worktree "):]).resolve()
    if main == Path(root).resolve():
        return None
    return str(main)


def seed_from_main(root, db_path: str) -> bool:
    """Copy the main checkout's index into a linked worktree that has none
    (AC: search in a new worktree). Only the main DB FILE is copied — never
    its WAL sidecars, which may be mid-checkpoint in the main checkout; a
    copy that misses the last commits is still a VALID older snapshot, and
    the incremental refresh that immediately follows brings it current. True
    when a seed happened."""
    if os.path.exists(db_path):
        return False
    main = main_checkout(root)
    if not main:
        return False
    src = os.path.join(main, INDEX_DIR_REL, DB_NAME)
    if not os.path.isfile(src):
        logger.info("kb index: no index in the main checkout yet — building from scratch")
        return False
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    shutil.copyfile(src, db_path)
    logger.info("kb index: seeded from the main checkout's index, refreshing incrementally")
    return True
