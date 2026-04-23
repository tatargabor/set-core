"""Idempotent removal of a change's on-disk artifacts.

A change's disk footprint is a git worktree directory and a `change/<name>`
git branch. When a change is reset mid-run (circuit-breaker auto-retry,
manual reset), the state is cleared but these artifacts stay behind. The
dispatcher then detects the collision and spawns a `-N` suffix variant,
which produces two parallel worktrees for the same logical change.

This module is the single source of truth for removing those artifacts.
It is called from any reset-to-pending path that wants a clean re-dispatch
(e.g. `IssueManager._retry_parent_after_resolved`). The recovery CLI uses
its own plan-driven paths because the plan may list archived-suffix
worktrees that do not match the canonical naming conventions.

Idempotency: every operation tolerates the artifact already being gone.
Repeated calls are no-ops — safe to invoke even when another component
just cleaned up the same change.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .subprocess_utils import run_command, run_git

logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    """Outcome of a `cleanup_change_artifacts` call."""

    worktree_removed: bool = False
    branch_removed: bool = False
    warnings: list[str] = field(default_factory=list)


def _list_registered_worktrees(project_path: str) -> set[str]:
    """Return the set of directory paths currently listed by `git worktree list`."""
    r = run_git("worktree", "list", "--porcelain", cwd=project_path, best_effort=True)
    if r.exit_code != 0:
        return set()
    paths: set[str] = set()
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            paths.add(line[len("worktree "):].strip())
    return paths


def _candidate_worktree_paths(change_name: str, project_path: str) -> list[str]:
    """Build both naming conventions for a change's worktree path.

    Bash `set-new` creates `{project}-wt-{change}`.
    Python dispatcher direct-add creates `{project}-{change}`.
    Both conventions must be considered when cleaning up, since which one
    exists depends on which code path created it.
    """
    project_path = os.path.abspath(project_path).rstrip("/")
    return [
        f"{project_path}-wt-{change_name}",
        f"{project_path}-{change_name}",
    ]


def cleanup_change_artifacts(change_name: str, project_path: str) -> CleanupResult:
    """Remove a change's worktree directory and `change/<name>` branch.

    Args:
        change_name: Change slug (e.g. "auth-login").
        project_path: Absolute path to the main repo root.

    Returns:
        CleanupResult describing what was removed or already absent.

    Side effects:
        - `git worktree remove --force` for any registered worktree at the
          canonical paths (`{project}-wt-{name}` or `{project}-{name}`).
        - `rm -rf` fallback when the directory exists on disk but is NOT
          registered in `git worktree list` (rare — happens when a prior
          `git worktree remove` was interrupted).
        - `git worktree prune` unconditionally to drop stale entries from
          `.git/worktrees/`.
        - `git branch -D change/<name>` when the branch exists.

    Idempotency: missing artifacts are treated as success (no-ops). Calling
    this twice in sequence is safe — the second call returns a result with
    both booleans False.
    """
    result = CleanupResult()

    if not change_name or not project_path:
        result.warnings.append(
            f"cleanup_change_artifacts called with empty args: "
            f"change_name={change_name!r} project_path={project_path!r}"
        )
        logger.warning(result.warnings[-1])
        return result

    if not os.path.isdir(project_path):
        result.warnings.append(f"project_path does not exist: {project_path}")
        logger.warning(result.warnings[-1])
        return result

    # --- Worktree removal (both conventions) ----------------------------
    registered = _list_registered_worktrees(project_path)
    candidates = _candidate_worktree_paths(change_name, project_path)

    for wt_path in candidates:
        if not os.path.isdir(wt_path):
            logger.debug(
                "cleanup_change_artifacts: worktree path absent, skipping: %s", wt_path,
            )
            continue

        if wt_path in registered:
            r = run_git(
                "worktree", "remove", "--force", wt_path,
                cwd=project_path, best_effort=True,
            )
            if r.exit_code == 0:
                result.worktree_removed = True
                logger.info(
                    "cleanup_change_artifacts: removed worktree %s (change=%s)",
                    wt_path, change_name,
                )
            else:
                msg = (
                    f"git worktree remove failed for {wt_path} "
                    f"(exit={r.exit_code}): {r.stderr.strip()[:200]}"
                )
                result.warnings.append(msg)
                logger.warning("cleanup_change_artifacts: %s", msg)
                # Fall through to rm -rf as a last resort
                if os.path.isdir(wt_path):
                    shutil.rmtree(wt_path, ignore_errors=True)
                    if not os.path.isdir(wt_path):
                        result.worktree_removed = True
                        logger.warning(
                            "cleanup_change_artifacts: rm -rf fallback removed %s",
                            wt_path,
                        )
        else:
            # Directory exists but not registered — orphan from an
            # interrupted remove. Use rm -rf.
            msg = (
                f"worktree {wt_path} exists but is not registered in "
                f"git worktree list; using rm -rf fallback"
            )
            result.warnings.append(msg)
            logger.warning("cleanup_change_artifacts: %s", msg)
            shutil.rmtree(wt_path, ignore_errors=True)
            if not os.path.isdir(wt_path):
                result.worktree_removed = True

    # Always prune to drop stale `.git/worktrees/` entries
    run_git("worktree", "prune", cwd=project_path, best_effort=True)

    # --- Branch deletion ------------------------------------------------
    branch = f"change/{change_name}"
    branch_check = run_git(
        "rev-parse", "--verify", branch,
        cwd=project_path, best_effort=True,
    )
    if branch_check.exit_code == 0:
        r = run_git("branch", "-D", branch, cwd=project_path, best_effort=True)
        if r.exit_code == 0:
            result.branch_removed = True
            logger.info(
                "cleanup_change_artifacts: deleted branch %s (change=%s)",
                branch, change_name,
            )
        else:
            msg = (
                f"git branch -D {branch} failed (exit={r.exit_code}): "
                f"{r.stderr.strip()[:200]}"
            )
            result.warnings.append(msg)
            logger.warning("cleanup_change_artifacts: %s", msg)
    else:
        logger.debug(
            "cleanup_change_artifacts: branch %s already absent, skipping",
            branch,
        )

    if not result.worktree_removed and not result.branch_removed and not result.warnings:
        logger.debug(
            "cleanup_change_artifacts: no artifacts found for %s in %s",
            change_name, project_path,
        )

    return result
