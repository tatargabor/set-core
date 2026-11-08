"""Every known project's wave boards, summarised for the fleet's header.

A wave board is a tracked job file, `docs/waveboard/<job>.json` (schema
`set-wave-board/1`, written by `bin/set-wave-board`), in the repository that runs
the job. The fleet is the cross-project screen, so it is where the boards of all
projects are seen together (asked for by the user, 2026-10-11).

Three properties are the contract, and each one is a rule rather than a taste:

- **Summaries only.** Counts, the job, the board's title and its page URL — never
  an item's title or note. Item content stays on the board page itself. Dependency
  edges between boards are given by item id only (`deps_out`, `deps_in`).
- **Unreadable is an entry, not an omission.** A board this reader cannot parse is
  returned with a reason. Dropping it would make a broken board and an absent one
  look the same, and the header would report a calm it never measured.
- **Nothing is written, and nothing is persisted.** The data is read at request
  time and leaves only in the response; the log carries counts and job names.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

SCHEMA = "set-wave-board/1"
STATUSES = ("todo", "doing", "done", "blocked", "skipped")
#: An item in one of these does not hold its wave open.
FINISHED = ("done", "skipped")
JOB_DIR = Path("docs") / "waveboard"

# ── staleness (change `wave-board-staleness`, D1–D4) ─────────────────────────
# The same rule as `bin/set-wave-board stale`, which does not import set_orch;
# `tests/unit/test_fleet_waveboards.py` runs both on one repository and holds them together.

DEFAULT_STALE_COMMITS = 3
GIT_TIMEOUT = 5


def stale_threshold() -> int:
    raw = os.environ.get("SET_WAVEBOARD_STALE_COMMITS", "").strip()
    try:
        return max(1, int(raw)) if raw else DEFAULT_STALE_COMMITS
    except ValueError:
        return DEFAULT_STALE_COMMITS


def _parse_time(value: Any) -> Optional[_dt.datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        t = _dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.replace(tzinfo=_dt.timezone.utc) if t.tzinfo is None else t.astimezone(_dt.timezone.utc)


def _is_manual(item: Dict[str, Any]) -> bool:
    """Open, and sync cannot move it: no evidence, or blocked (sticky)."""
    status = item.get("status")
    if status in FINISHED:
        return False
    return not item.get("evidence") or status == "blocked"


def _last_change(data: Dict[str, Any]) -> Optional[_dt.datetime]:
    times = [_parse_time(item.get("updated"))
             for wave in (data.get("waves") or []) if isinstance(wave, dict)
             for item in (wave.get("items") or []) if isinstance(item, dict)]
    reviewed = data.get("reviewed")
    if isinstance(reviewed, dict):
        times.append(_parse_time(reviewed.get("at")))
    found = [t for t in times if t is not None]
    return max(found) if found else _parse_time(data.get("created"))


def _commits_since(root: Path, since: Optional[_dt.datetime]) -> Optional[int]:
    """Commits on HEAD strictly newer than `since`; None when it cannot be counted.

    Logged at DEBUG, not WARNING: the route is polled every minute, and the null in the
    response is what makes the failure visible (design D10).
    """
    if since is None:
        return None
    after = (since + _dt.timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S +0000")
    try:
        r = subprocess.run(["git", "rev-list", "--count", f"--since={after}", "HEAD"],
                           cwd=str(root), capture_output=True, text=True, timeout=GIT_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("waveboards: cannot count commits in %s: %s", root, type(exc).__name__)
        return None
    if r.returncode != 0:
        logger.debug("waveboards: git rev-list failed in %s (exit %s)", root, r.returncode)
        return None
    try:
        return int(r.stdout.strip())
    except ValueError:
        return None


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

    manual = sum(1 for wave in waves if isinstance(wave, dict)
                 for item in (wave.get("items") if isinstance(wave.get("items"), list) else [])
                 if isinstance(item, dict) and _is_manual(item))
    root = path.parent.parent.parent
    commits = _commits_since(root, _last_change(data))
    reviewed = data.get("reviewed")
    reviewed_at = reviewed.get("at") if isinstance(reviewed, dict) else None

    # Dependencies (change `wave-board-shared-linked`, D9): collected here by id only, resolved
    # across every board of the same read in `read_waveboards`.
    statuses: Dict[str, Any] = {}
    raw_deps: List[Dict[str, Any]] = []
    for wave in waves:
        if not isinstance(wave, dict):
            continue
        for item in (wave.get("items") if isinstance(wave.get("items"), list) else []):
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            statuses[item["id"]] = item.get("status")
            for ref in (item.get("depends_on") if isinstance(item.get("depends_on"), list) else []):
                if isinstance(ref, dict) and isinstance(ref.get("job"), str) and isinstance(ref.get("item"), str):
                    target = ref.get("project") if isinstance(ref.get("project"), str) else project
                    raw_deps.append({"item": item["id"], "open": item.get("status") not in FINISHED,
                                     "on": {"project": target, "job": ref["job"], "item": ref["item"]}})

    url = data.get("artifact_url")
    return {
        "_statuses": statuses,
        "_deps": raw_deps,
        "project": project,
        "job": str(data.get("job") or job),
        "title": str(data.get("title") or job),
        "artifact_url": url if isinstance(url, str) and url.startswith("https://") else None,
        "counts": counts,
        "other": other,
        "waves": len(waves),
        "current_wave": current,
        "updated": latest,
        "reviewed": reviewed_at if isinstance(reviewed_at, str) else None,
        "manual_open": manual,
        "commits_since_change": commits,
        "stale": manual > 0 and commits is not None and commits >= stale_threshold(),
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
    link_dependencies(boards)
    logger.debug("waveboards: %d board(s), %d unreadable",
                 len(boards), sum(1 for b in boards if b.get("unreadable")))
    return boards


def link_dependencies(boards: List[Dict[str, Any]]) -> None:
    """Resolve every board's `depends_on` against the boards of this read, in place.

    Met means the referenced item is `done`; a reference to a board or item this read does
    not hold is unmet with a null status and counted in `deps_unresolved` — never met.
    """
    index = {(b["project"], b["job"]): b for b in boards if not b.get("unreadable")}
    for b in index.values():
        b["deps_in"] = []
    for b in index.values():
        out: List[Dict[str, Any]] = []
        waiting_items = set()
        unresolved = 0
        for d in b.get("_deps", []):
            on = d["on"]
            target = index.get((on["project"], on["job"]))
            status = (target.get("_statuses") or {}).get(on["item"]) if target else None
            known = target is not None and on["item"] in (target.get("_statuses") or {})
            met = status == "done"
            if not known:
                unresolved += 1
            if d["open"] and not met:
                waiting_items.add(d["item"])
            out.append({"item": d["item"], "on": on, "status": status if known else None, "met": met})
            if target is not None and known:
                target["deps_in"].append({"item": on["item"], "met": met,
                                          "by": {"project": b["project"], "job": b["job"], "item": d["item"]}})
        b["deps_out"] = out
        b["waiting"] = len(waiting_items)
        b["deps_unresolved"] = unresolved
    for b in boards:
        b.pop("_statuses", None)
        b.pop("_deps", None)
    edges = sum(len(b.get("deps_out", [])) for b in index.values())
    if edges:
        logger.debug("waveboards: %d dependency edge(s), %d unresolved", edges,
                     sum(b.get("deps_unresolved", 0) for b in index.values()))
