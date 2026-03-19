"""Sentinel runtime directory management.

Sentinel files live in the shared runtime directory:
~/.local/share/wt-tools/<project>/sentinel/

Migrated from project-local .wt/sentinel/ to shared location.
"""

import os

from ..paths import WtRuntime


def ensure_sentinel_dir(project_path: str) -> str:
    """Create sentinel directory under shared runtime and return its path.

    Creates:
    - ~/.local/share/wt-tools/<project>/sentinel/
    - ~/.local/share/wt-tools/<project>/sentinel/archive/
    """
    rt = WtRuntime(project_path)
    sentinel_path = rt.sentinel_dir
    os.makedirs(sentinel_path, exist_ok=True)

    archive_path = rt.sentinel_archive_dir
    os.makedirs(archive_path, exist_ok=True)

    return sentinel_path


# Backward-compatible alias
ensure_wt_dir = ensure_sentinel_dir

# Legacy constants (for any code that imports them directly)
# These are now derived from WtRuntime at call time, not hardcoded.
WT_DIR = ".wt"
SENTINEL_DIR = os.path.join(WT_DIR, "sentinel")
