"""Git utilities shared across orchestration modules."""

import subprocess

# Paths that are always dirty during agent execution (framework-internal).
# These are written by Ralph loop, Claude Code session, wt-tools hooks, and
# the OpenSpec apply skill — never by application code.
_FRAMEWORK_NOISE_PREFIXES = (
    ".claude/",
    ".wt-tools/",
    "CLAUDE.md",
    "openspec/changes/",
    "node_modules/",  # pnpm/npm install modifies symlinks — never application work
    "coverage/",      # test coverage output — never application work
)


def _is_framework_noise(porcelain_line: str) -> bool:
    """Return True if a ``git status --porcelain`` line is framework noise."""
    # Format: "XY path" or "XY path -> renamed" — path starts at column 3.
    path = porcelain_line[3:].strip().strip('"')
    return path.startswith(_FRAMEWORK_NOISE_PREFIXES)


def git_has_uncommitted_work(wt_path: str) -> tuple[bool, str]:
    """Check if a worktree has uncommitted or untracked files.

    Runs ``git status --porcelain`` and parses the output into counts.
    Framework-internal paths (.claude/, .wt-tools/, CLAUDE.md,
    openspec/changes/) are excluded — they are always dirty during agent
    execution and do not indicate real uncommitted application work.

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

    lines = [l for l in result.stdout.splitlines()
             if l.strip() and not _is_framework_noise(l)]
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
