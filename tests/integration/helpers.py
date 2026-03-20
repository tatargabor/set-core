"""Shared helpers for integration tests."""

import json
import subprocess
from pathlib import Path


def run_git(repo: Path, *args: str) -> str:
    """Run a git command in a repo and return stdout."""
    result = subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {repo}: {result.stderr}"
        )
    return result.stdout.strip()


def change_dict(
    name: str,
    status: str = "pending",
    depends_on: list[str] | None = None,
    worktree_path: str | None = None,
    **extras,
) -> dict:
    """Build a change dict for state files."""
    d = {
        "name": name,
        "scope": f"Test change {name}",
        "complexity": "S",
        "change_type": "feature",
        "depends_on": depends_on or [],
        "status": status,
        "worktree_path": worktree_path,
        "ralph_pid": None,
        "started_at": None,
        "completed_at": None,
        "tokens_used": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_create_tokens": 0,
        "verify_retry_count": 0,
        "merge_retry_count": 0,
        "redispatch_count": 0,
        "test_result": None,
        "smoke_result": None,
        "review_result": None,
        "build_result": None,
    }
    d.update(extras)
    return d


def grep_conflict_markers(repo: Path) -> list[str]:
    """Find any conflict markers in tracked files."""
    result = subprocess.run(
        ["git", "-C", str(repo), "grep", "-rn", "<<<<<<<"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip().splitlines() if result.stdout.strip() else []
