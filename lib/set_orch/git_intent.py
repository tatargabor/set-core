from __future__ import annotations

"""Git history as a deletion-intent signal.

The provenance ledger (`deploy_ledger.py`) answers "did the project delete this?"
from what set-core itself recorded. That works from the *second* init onward. On the
first one the ledger is empty, so every absent path reads as "genuinely new" and the
deploy recreates it — including the files the project threw out on purpose.

Measured on a live consumer: a first init after the ledger landed resurrected 11
files, every one of them proven deliberate by the project's own git history (two
commits whose entire content was those deletions). An empty ledger is not evidence
of absence; it is absence of evidence.

Git history is the evidence that already exists. A path that appears under
`git log --diff-filter=D` was deleted in a commit somebody wrote and kept — that is
a stronger, older intent signal than anything set-core can reconstruct, and it is
available on the very first run.

Scope of the claim. This module answers exactly one question: "has this path ever
been deleted in this repository's history?" It deliberately does NOT ask who deleted
it or why. The caller must only consult it for paths that are *absent right now* —
a path deleted and later re-added exists on disk, so the question never arises.

Failure is not silence. Every path that cannot produce an answer — no git, not a
repository, a timeout on a large history — returns None, and the caller falls back
to its previous behaviour with a WARNING. A signal that fails closed would freeze
new projects out of ever receiving a template file.

Known false positive. `git rm --cached` — untracking a directory that later became
gitignored — records a D exactly like a real deletion, so those paths stop deploying.
It errs in the conservative direction (nothing is destroyed; a file merely fails to
appear) and every skip is named in the deploy output. The way out is
`SET_DEPLOY_IGNORE_GIT_HISTORY=1`, or dropping the path from `tombstones` in the
ledger after the first run.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, FrozenSet, Optional, Tuple

logger = logging.getLogger(__name__)

# History scans are one subprocess per repository per process. The timeout bounds a
# pathological history (very large monorepo) rather than a normal one; on expiry we
# report "unknown" instead of stalling an init.
_GIT_TIMEOUT_SEC = 20

# repo-identity → result. None means "asked and could not answer" and is cached too:
# re-running a failing git call once per file would turn one failure into hundreds.
_CACHE: Dict[str, Optional[FrozenSet[str]]] = {}


def _run_git(args, cwd: Path) -> Optional[str]:
    """Run a git command in `cwd`. Returns stdout, or None on any failure."""
    try:
        proc = subprocess.run(
            ["git"] + list(args),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SEC,
        )
    except FileNotFoundError:
        logger.debug("git_intent: git is not installed")
        return None
    except subprocess.TimeoutExpired:
        logger.warning(
            "git_intent: `git %s` timed out after %ds in %s — deletion intent unknown "
            "for this run", " ".join(args), _GIT_TIMEOUT_SEC, cwd,
        )
        return None
    except OSError as exc:
        logger.debug("git_intent: git failed in %s: %s", cwd, exc)
        return None

    if proc.returncode != 0:
        logger.debug(
            "git_intent: `git %s` exited %d in %s: %s",
            " ".join(args), proc.returncode, cwd, proc.stderr.strip()[:200],
        )
        return None
    return proc.stdout


def _repo_context(project_root: Path) -> Optional[Tuple[str, str]]:
    """(repo top-level, path of project_root inside it) or None if not a repository.

    The prefix matters: keys in the ledger are relative to the project root, while git
    reports paths relative to the repository root. When set-core deploys into a
    subdirectory of a larger repo the two differ, and comparing them unadjusted would
    silently match nothing — a guard that quietly never fires is worse than no guard.
    """
    top = _run_git(["rev-parse", "--show-toplevel"], project_root)
    if top is None:
        return None
    prefix = _run_git(["rev-parse", "--show-prefix"], project_root)
    if prefix is None:
        return None
    return top.strip(), prefix.strip()


def deleted_paths(project_root: Path) -> Optional[FrozenSet[str]]:
    """Paths deleted at some point in history, relative to `project_root`.

    Returns None when the question cannot be answered (no git, not a repository,
    timeout). Callers must treat None as "no information" and keep their previous
    behaviour — never as "nothing was deleted".
    """
    if _env_disabled():
        logger.info(
            "git_intent: SET_DEPLOY_IGNORE_GIT_HISTORY is set — history is not consulted; "
            "previously deleted framework files may be recreated",
        )
        return None

    root = Path(project_root)
    try:
        cache_key = str(root.resolve())
    except OSError:
        cache_key = str(root)

    if cache_key in _CACHE:
        return _CACHE[cache_key]

    result = _compute_deleted_paths(root)
    _CACHE[cache_key] = result
    return result


def _compute_deleted_paths(root: Path) -> Optional[FrozenSet[str]]:
    if not root.is_dir():
        return None

    context = _repo_context(root)
    if context is None:
        logger.info(
            "git_intent: %s is not a git repository (or git is unavailable) — "
            "deletion intent cannot be read from history", root,
        )
        return None
    _, prefix = context

    # `--format=` suppresses commit headers, so stdout is nothing but path lines.
    # Rename detection is on by default, which is what we want: a renamed file is
    # reported as R and correctly does NOT count as a deletion of the old path.
    out = _run_git(["log", "--diff-filter=D", "--name-only", "--format="], root)
    if out is None:
        return None

    paths = set()
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if prefix:
            if not line.startswith(prefix):
                continue        # outside the deployed subtree — not ours to reason about
            line = line[len(prefix):]
        if line:
            paths.add(line)

    logger.info(
        "git_intent: %s — %d path(s) deleted somewhere in history; absent ones will "
        "not be recreated", root, len(paths),
    )
    return frozenset(paths)


def clear_cache() -> None:
    """Drop the per-process cache. Tests mutate repositories between calls."""
    _CACHE.clear()


def _env_disabled() -> bool:
    """`SET_DEPLOY_IGNORE_GIT_HISTORY=1` turns the signal off.

    The escape hatch exists for the one legitimate case: a project that deleted a
    framework file, changed its mind, and wants the whole set back without editing
    tombstones by hand.
    """
    return os.environ.get("SET_DEPLOY_IGNORE_GIT_HISTORY", "").strip().lower() in {
        "1", "true", "yes",
    }
