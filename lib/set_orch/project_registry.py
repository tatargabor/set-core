"""Reading and writing the project registry — no web framework attached.

The registry (``~/.config/set-core/projects.json``) is core state: the CLI, the
orchestrator and the web API all need it, and only one of those can import
FastAPI. It used to live in ``api/helpers.py``, which meant reaching it from a
plain shell command pulled the whole HTTP layer in — and on a machine where the
API's dependencies are not installed, that is not a slow import, it is an
ImportError. Layer 1 owns this; the API imports from here, never the reverse.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROJECTS_FILE = Path.home() / ".config" / "set-core" / "projects.json"


def load_projects(registry_file: Optional[Path] = None) -> list[dict]:
    """Load registered projects.

    Format: {"projects": {"name": {"path": ..., ...}}, "default": ...}
    Returns a list of dicts, each carrying `name` plus every stored field —
    including ones this module knows nothing about, such as `archived`.
    """
    src = Path(registry_file) if registry_file else PROJECTS_FILE
    if not src.exists():
        return []
    try:
        with open(src) as f:
            data = json.load(f)
        if isinstance(data, dict) and "projects" in data:
            return [
                {"name": name, "path": info.get("path", ""),
                 **{k: v for k, v in info.items() if k != "path"}}
                for name, info in data["projects"].items()
                if isinstance(info, dict)
            ]
        # Legacy: list format
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("project registry unreadable: %s (%s)", src, exc)
        return []


def save_projects(projects: list[dict], registry_file: Optional[Path] = None) -> None:
    """Write projects back, preserving `default` and any unknown top-level keys.

    Entry fields are passed through verbatim — a known-key allowlist here would
    silently drop whatever a newer version of set-core stores.
    """
    dest = Path(registry_file) if registry_file else PROJECTS_FILE
    dest.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if dest.exists():
        try:
            with open(dest) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    if not isinstance(existing, dict):
        existing = {}
    projects_dict = {}
    for p in projects:
        name = p["name"]
        projects_dict[name] = {k: v for k, v in p.items() if k != "name"}
    existing["projects"] = projects_dict
    with open(dest, "w") as f:
        json.dump(existing, f, indent=2)


def backup_registry(registry_file: Optional[Path] = None) -> Optional[str]:
    """Copy the registry aside before it is written. Raises if the copy fails.

    An abort is the correct outcome of a failure here: an operation that cannot
    be undone must not start. Returns None only when there is no registry yet.
    """
    src = Path(registry_file) if registry_file else PROJECTS_FILE
    if not src.exists():
        return None
    dest = src.with_name(f"{src.name}.bak-{int(time.time())}")
    shutil.copy2(src, dest)
    logger.info("registry backed up: %s", dest)
    return str(dest)
