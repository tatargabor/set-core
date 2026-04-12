"""Archive-before-overwrite helper for tracked files.

Provides `archive_and_write()` — snapshots the existing content to an
archive directory, then writes the new content atomically via tempfile +
os.replace. Optional metadata sidecar and rolling retention policy.

Callers always pass `archive_dir` explicitly. The helper does not guess paths.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from .git_utils import resolve_head_commit

logger = logging.getLogger(__name__)

_Content = Union[str, bytes]


def archive_and_write(
    path: str,
    content: _Content,
    *,
    archive_dir: str,
    reason: Optional[str] = None,
    max_archives: Optional[int] = None,
) -> Optional[str]:
    """Archive existing file, then write new content atomically.

    Returns the archive path if a snapshot was taken, else None.

    Behavior:
    1. If `path` exists, copy it to `<archive_dir>/<ts><suffix>`. Archiving
       failure is logged WARNING and the write continues (data preservation
       beats metadata).
    2. Write `content` atomically via NamedTemporaryFile + os.replace.
       Write failure propagates.
    3. If archiving succeeded AND `reason` is set, write `<archive>.meta.json`
       sidecar with `{reason, ts, commit}`. Sidecar failures are WARNING.
    4. If `max_archives` is set, prune the archive dir to keep the N newest
       (sort by name — the timestamp-encoded prefix is chronological).
    """
    p = Path(path)
    archive_path: Optional[str] = None

    if p.exists():
        try:
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            suffix = p.suffix
            archive_name = f"{ts}{suffix}"
            ad = Path(archive_dir)
            ad.mkdir(parents=True, exist_ok=True)
            archive_target = ad / archive_name
            # Disambiguate on collision (multiple writes same second).
            n = 0
            while archive_target.exists():
                n += 1
                archive_target = ad / f"{ts}-{n}{suffix}"
            shutil.copy2(p, archive_target)
            archive_path = str(archive_target)
        except OSError as exc:
            logger.warning(
                "archive_and_write: snapshot of %s failed: %s", path, exc
            )

    parent = p.parent
    parent.mkdir(parents=True, exist_ok=True)

    if isinstance(content, bytes):
        mode = "wb"
        data: _Content = content
    else:
        mode = "w"
        data = content

    tmp = tempfile.NamedTemporaryFile(
        mode=mode,
        dir=str(parent),
        prefix=f".{p.name}.",
        suffix=".tmp",
        delete=False,
    )
    tmp_path = tmp.name
    try:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp_path, path)
    except BaseException:
        try:
            tmp.close()
        except OSError:
            pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    if archive_path and reason:
        try:
            commit = resolve_head_commit(str(parent))
            # Local-with-offset per eccdbea8 timestamp unification.
            # Note: the archive FILENAME (line ~57) stays in UTC "Z" form
            # so directory listings sort chronologically by plain name.
            meta = {
                "reason": reason,
                "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "commit": commit,
            }
            with open(archive_path + ".meta.json", "w") as f:
                json.dump(meta, f, indent=2)
                f.write("\n")
        except OSError as exc:
            logger.warning(
                "archive_and_write: sidecar write for %s failed: %s",
                archive_path,
                exc,
            )

    if max_archives is not None and max_archives >= 0:
        try:
            suffix = p.suffix
            pattern = os.path.join(archive_dir, f"*{suffix}")
            files = [
                f
                for f in glob.glob(pattern)
                if not f.endswith(".meta.json")
            ]
            files.sort()
            to_prune = files[: max(0, len(files) - max_archives)]
            for old in to_prune:
                try:
                    os.unlink(old)
                    sidecar = old + ".meta.json"
                    if os.path.exists(sidecar):
                        os.unlink(sidecar)
                except OSError as exc:
                    logger.warning(
                        "archive_and_write: prune failed for %s: %s", old, exc
                    )
        except OSError as exc:
            logger.warning(
                "archive_and_write: retention sweep failed in %s: %s",
                archive_dir,
                exc,
            )

    return archive_path
