"""Every known project's wave boards, summarised for the fleet's header.

A wave board is a tracked job file, `docs/waveboard/<job>.json` (schema
`set-wave-board/1`, written by `bin/set-wave-board`), in the repository that runs
the job. The fleet is the cross-project screen, so it is where the boards of all
projects are seen together (asked for by the user, 2026-10-11).

Three properties are the contract, and each one is a rule rather than a taste:

- **Summaries only.** Counts, the job, the board's title and its page URL — never
  an item's title or note. Item content stays on the board page itself.
- **Unreadable is an entry, not an omission.** A board this reader cannot parse is
  returned with a reason. Dropping it would make a broken board and an absent one
  look the same, and the header would report a calm it never measured.
- **Nothing is written, and nothing is persisted.** The data is read at request
  time and leaves only in the response; the log carries counts and job names.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

SCHEMA = "set-wave-board/1"
STATUSES = ("todo", "doing", "done", "blocked", "skipped")
#: An item in one of these does not hold its wave open.
FINISHED = ("done", "skipped")
JOB_DIR = Path("docs") / "waveboard"


def _unreadable(project: str, job: str, reason: str) -> Dict[str, Any]:
    return {"project": project, "job": job, "unreadable": True, "reason": reason}


def summarise_board(project: str, path: Path) -> Dict[str, Any]:
    """One board's summary, or an unreadable entry saying why not."""
    job = path.stem
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("waveboards: %s/%s could not be read: %s", project, job, type(exc).__name__)
        return _unreadable(project, job, f"could not be read ({type(exc).__name__})")
    except json.JSONDecodeError as exc:
        logger.warning("waveboards: %s/%s is not valid JSON (line %s)", project, job, exc.lineno)
        return _unreadable(project, job, f"not valid JSON (line {exc.lineno})")
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        found = data.get("schema") if isinstance(data, dict) else type(data).__name__
        logger.warning("waveboards: %s/%s has schema %r, expected %s", project, job, found, SCHEMA)
        return _unreadable(project, job, f"schema is {found!r}, not {SCHEMA}")

    counts = {s: 0 for s in STATUSES}
    other = 0
    current: Optional[Dict[str, str]] = None
    latest: Optional[str] = None
    waves = data.get("waves") if isinstance(data.get("waves"), list) else []
    for wave in waves:
        if not isinstance(wave, dict):
            continue
        items = wave.get("items") if isinstance(wave.get("items"), list) else []
        open_here = False
        for item in items:
            if not isinstance(item, dict):
                continue
            status = item.get("status")
            if status in counts:
                counts[status] += 1
            else:
                # Counted, not dropped: an item in a status this reader does not
                # know is still an item, and leaving it out would shrink the board.
                other += 1
            if status not in FINISHED:
                open_here = True
            updated = item.get("updated")
            if isinstance(updated, str) and (latest is None or updated > latest):
                latest = updated
        if open_here and current is None:
            current = {"id": str(wave.get("id") or ""), "title": str(wave.get("title") or "")}

    url = data.get("artifact_url")
    return {
        "project": project,
        "job": str(data.get("job") or job),
        "title": str(data.get("title") or job),
        "artifact_url": url if isinstance(url, str) and url.startswith("https://") else None,
        "counts": counts,
        "other": other,
        "waves": len(waves),
        "current_wave": current,
        "updated": latest,
        "unreadable": False,
    }


def read_waveboards(projects: Iterable[Any]) -> List[Dict[str, Any]]:
    """Every board of every project given; each project needs `.name` and `.root`.

    A project without a `docs/waveboard/` directory contributes nothing — that is
    the ordinary case, not an error.
    """
    boards: List[Dict[str, Any]] = []
    seen_roots = set()
    for project in projects:
        root = getattr(project, "root", None)
        name = getattr(project, "name", None) or (os.path.basename(root) if root else None)
        if not root or not name:
            continue
        real = os.path.realpath(root)
        if real in seen_roots:
            continue
        seen_roots.add(real)
        job_dir = Path(root) / JOB_DIR
        if not job_dir.is_dir():
            continue
        for path in sorted(job_dir.glob("*.json")):
            boards.append(summarise_board(name, path))
    logger.debug("waveboards: %d board(s), %d unreadable",
                 len(boards), sum(1 for b in boards if b.get("unreadable")))
    return boards
