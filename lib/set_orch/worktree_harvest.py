"""Post-merge worktree harvest.

Copies valuable worktree-local files (reflection, loop-state, activity,
review findings) to a persistent archive under the orchestration runtime
directory so they survive `git worktree remove`.

Non-blocking: all exceptions are caught by the caller in
`merger.cleanup_worktree()`. Harvest failure never blocks a merge.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from .git_utils import resolve_head_commit

logger = logging.getLogger(__name__)


def _now_iso_local() -> str:
    """Local-time-with-offset ISO timestamp (matches eccdbea8 contract)."""
    return datetime.now(timezone.utc).astimezone().isoformat()


HARVEST_ARTIFACTS: List[Tuple[str, bool]] = [
    (".set/reflection.md", True),
    (".set/loop-state.json", True),
    (".set/activity.json", True),
    (".claude/review-findings.md", True),
]


def _resolve_dest_root(project_path: str, change_name: str) -> Path:
    """Derive the harvest destination under <orchestration_dir>/archives/worktrees/.

    Runs outside the hot path (only on merge completion) so importing
    `SetRuntime` here is safe.
    """
    from .paths import SetRuntime

    rt = SetRuntime(project_path)
    return Path(rt.orchestration_dir) / "archives" / "worktrees" / change_name


def harvest_worktree(
    change_name: str,
    wt_path: str,
    project_path: str,
    *,
    reason: str = "merge",
) -> Optional[Path]:
    """Harvest tracked files from a worktree to the orchestration archive.

    Returns the destination path on success, None on unrecoverable error.
    Callers should wrap in try/except because merge flow must not break.
    """
    dest_root = _resolve_dest_root(project_path, change_name)

    # Idempotency: merge_change calls cleanup_worktree which calls harvest,
    # AND engine._finalize_run calls cleanup_all_worktrees which also
    # iterates merged changes and calls cleanup_worktree — so a single
    # successful merge triggers harvest TWICE for the same change.
    #
    # Strategy:
    #   - If dest exists with a valid meta file → already harvested, skip.
    #   - If dest exists without meta → partial/interrupted prior harvest;
    #     RESUME into the same dir (overwrite, never create a duplicate).
    #
    # The earlier implementation created a timestamped sibling dir as a
    # fallback, which produced collision pairs like
    #   archives/worktrees/add-item/
    #   archives/worktrees/add-item.20260412T182459Z/
    # on nano-run-20260412-1941. A duplicate is never valuable (same
    # source commit, same files), so resume-in-place is the correct fix.
    meta_check = dest_root / ".harvest-meta.json"
    if dest_root.exists() and meta_check.is_file():
        logger.info(
            "Harvest skipped for %s — already archived at %s",
            change_name, dest_root,
        )
        return dest_root

    if dest_root.exists():
        logger.warning(
            "Harvest destination exists without meta for %s — resuming in-place at %s",
            change_name, dest_root,
        )

    dest_root.mkdir(parents=True, exist_ok=True)

    harvested: list[str] = []
    wt = Path(wt_path)
    for rel, optional in HARVEST_ARTIFACTS:
        src = wt / rel
        if not src.exists():
            if not optional:
                logger.warning(
                    "Required harvest artifact missing for %s: %s", change_name, rel
                )
            continue
        dst = dest_root / Path(rel).name
        try:
            shutil.copy2(src, dst)
            harvested.append(rel)
        except OSError as exc:
            logger.warning(
                "Failed to copy %s → %s: %s", src, dst, exc
            )

    commit = resolve_head_commit(wt_path)

    meta = {
        "harvested_at": _now_iso_local(),
        "reason": reason,
        "wt_path": wt_path,
        "wt_name": change_name,
        "files": harvested,
        "commit": commit,
    }
    meta_path = dest_root / ".harvest-meta.json"
    try:
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
            f.write("\n")
    except OSError as exc:
        logger.warning("Failed to write harvest meta for %s: %s", change_name, exc)

    logger.info(
        "Harvested %d files from %s to %s",
        len(harvested),
        change_name,
        dest_root,
    )
    return dest_root
