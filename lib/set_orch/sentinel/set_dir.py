from __future__ import annotations

"""Sentinel runtime directory management.

Sentinel files live in the shared runtime directory:
~/.local/share/set-core/<project>/sentinel/

Migrated from project-local .set/sentinel/ to shared location.
"""

import os

from ..paths import SetRuntime


def ensure_sentinel_dir(project_path: str) -> str:
    """Create sentinel directory under shared runtime and return its path.

    Creates:
    - ~/.local/share/set-core/<project>/sentinel/
    - ~/.local/share/set-core/<project>/sentinel/archive/
    """
    rt = SetRuntime(project_path)
    sentinel_path = rt.sentinel_dir
    os.makedirs(sentinel_path, exist_ok=True)

    archive_path = rt.sentinel_archive_dir
    os.makedirs(archive_path, exist_ok=True)

    return sentinel_path


# Backward-compatible alias
ensure_set_dir = ensure_sentinel_dir

# Legacy constants (for any code that imports them directly)
# These are now derived from SetRuntime at call time, not hardcoded.
SET_DIR = ".set"
SENTINEL_DIR = os.path.join(SET_DIR, "sentinel")
