"""Git utilities shared across orchestration modules."""

import subprocess


def git_has_uncommitted_work(wt_path: str) -> tuple[bool, str]:
    """Check if a worktree has uncommitted or untracked files.

    Runs ``git status --porcelain`` and parses the output into counts.

    Returns:
        (has_work, summary) — e.g. (True, "3 modified, 7 untracked")
        Fail-open on timeout/error: returns (False, "").
    """
    try:
        result = subprocess.run(
            ["git", "-C", wt_path, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return (False, "")

    if result.returncode != 0:
        return (False, "")

    lines = [l for l in result.stdout.splitlines() if l.strip()]
    if not lines:
        return (False, "")

    modified = 0
    untracked = 0
    for line in lines:
        if line.startswith("??"):
            untracked += 1
        else:
            modified += 1

    parts = []
    if modified:
        parts.append(f"{modified} modified")
    if untracked:
        parts.append(f"{untracked} untracked")
    summary = ", ".join(parts)

    return (True, summary)
