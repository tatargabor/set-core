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
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from .git_utils import resolve_head_commit

logger = logging.getLogger(__name__)


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

    # Idempotency guard: merge_change calls cleanup_worktree which calls
    # harvest, AND engine._finalize_run calls cleanup_all_worktrees which
    # also iterates merged changes and calls cleanup_worktree — so a
    # single successful merge triggers harvest TWICE for the same change.
    # If the destination already exists with a valid meta file, skip.
    # Caught on nano-run-20260412-1941 where add-item got harvested twice
    # 874ms apart, producing a timestamped-collision fallback directory.
    meta_check = dest_root / ".harvest-meta.json"
    if dest_root.exists() and meta_check.is_file():
        logger.info(
            "Harvest skipped for %s — already archived at %s",
            change_name, dest_root,
        )
        return dest_root

    if dest_root.exists():
        # Destination exists but meta is missing — partial harvest from a
        # crashed prior run. Use timestamped fallback so we don't
        # overwrite whatever is there.
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        dest_root = dest_root.with_name(f"{change_name}.{ts}")
        logger.warning(
            "Harvest destination exists without meta for %s — using timestamped fallback %s",
            change_name,
            dest_root,
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
        "harvested_at": datetime.utcnow().isoformat() + "Z",
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
