"""Utility for .wt/ runtime directory management."""

import os

WT_DIR = ".wt"
SENTINEL_DIR = os.path.join(WT_DIR, "sentinel")
GITIGNORE_ENTRY = "/.wt/"


def ensure_wt_dir(project_path: str) -> str:
    """Create .wt/sentinel/ and add /.wt/ to .gitignore if missing.

    Returns the sentinel directory path.
    """
    sentinel_path = os.path.join(project_path, SENTINEL_DIR)
    os.makedirs(sentinel_path, exist_ok=True)

    archive_path = os.path.join(sentinel_path, "archive")
    os.makedirs(archive_path, exist_ok=True)

    _ensure_gitignore(project_path)
    return sentinel_path


def _ensure_gitignore(project_path: str) -> None:
    """Append /.wt/ to .gitignore if not already present."""
    gitignore_path = os.path.join(project_path, ".gitignore")

    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r") as f:
            content = f.read()
        if GITIGNORE_ENTRY in content:
            return
        # Ensure newline before our entry
        if content and not content.endswith("\n"):
            content += "\n"
    else:
        content = ""

    with open(gitignore_path, "a") as f:
        if not content:
            f.write(f"# wt-tools runtime directory\n{GITIGNORE_ENTRY}\n")
        else:
            f.write(f"\n# wt-tools runtime directory\n{GITIGNORE_ENTRY}\n")
