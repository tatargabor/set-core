"""Lineage discovery + filter helpers for the dashboard API.

Implements Section 13 of run-history-and-phase-continuity:
  - GET /api/{project}/lineages — list every lineage with metadata
  - `apply_lineage_filter(records, lineage_id)` — reusable filter for
    endpoints that accept `?lineage=`.

Lineages are discovered from three sources, in order of authority:
  1. The live state's `spec_lineage_id`
  2. Every entry in the state archive (LineagePaths.state_archive)
  3. Every line in the supervisor status history (LineagePaths.supervisor_status_history)

A synthetic `__legacy__` lineage is returned when NO record carries a
`spec_lineage_id` field (corresponds to AC-43).  `__unknown__` shows up
only when the post-migration archive still has unattributed entries.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from .helpers import (
    _load_archived_changes,
    _resolve_project,
    _state_path,
)

logger = logging.getLogger(__name__)
router = APIRouter()


_ALL = "__all__"
_LEGACY = "__legacy__"
_UNKNOWN = "__unknown__"


def _read_state_lineage_and_status(state_path: Path) -> tuple[Optional[str], Optional[str]]:
    """Return (spec_lineage_id, status) from state.json, tolerating absence."""
    if not state_path.exists():
        return None, None
    try:
        with open(state_path) as fh:
            data = json.load(fh)
        return data.get("spec_lineage_id"), data.get("status")
    except (OSError, json.JSONDecodeError):
        return None, None


def _supervisor_status_history(project_path: Path) -> list[dict]:
    history = project_path / ".set" / "supervisor" / "status-history.jsonl"
    out: list[dict] = []
    if not history.is_file():
        return out
    try:
        with open(history, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return out


def _collect_lineages(project_path: Path, *, sentinel_running: bool = False) -> list[dict]:
    """Return one dict per discovered lineage, sorted live → most-recent."""
    state_path = _state_path(project_path)
    live_lineage, _ = _read_state_lineage_and_status(state_path)

    lineages: dict[str, dict[str, Any]] = {}

    def _bump(lid: str, *, ts: str = "", merged: bool = False) -> None:
        rec = lineages.setdefault(lid, {
            "id": lid,
            "display_name": lid,
            "first_seen_at": "",
            "last_seen_at": "",
            "is_live": False,
            "change_count": 0,
            "merged_count": 0,
        })
        rec["change_count"] += 1
        if merged:
            rec["merged_count"] += 1
        if ts:
            if not rec["first_seen_at"] or ts < rec["first_seen_at"]:
                rec["first_seen_at"] = ts
            if not rec["last_seen_at"] or ts > rec["last_seen_at"]:
                rec["last_seen_at"] = ts

    # 1. Live state contributions.
    try:
        if state_path.exists():
            with open(state_path) as fh:
                state_data = json.load(fh)
            for c in state_data.get("changes", []):
                lid = c.get("spec_lineage_id") or live_lineage
                if not lid:
                    continue
                ts = c.get("started_at") or c.get("completed_at") or ""
                _bump(lid, ts=ts, merged=c.get("status") == "merged")
    except (OSError, json.JSONDecodeError):
        pass

    # 2. Archive contributions.
    archived = _load_archived_changes(project_path)
    for entry in archived:
        lid = entry.get("spec_lineage_id") or _LEGACY
        ts = entry.get("archived_at") or entry.get("completed_at") or ""
        _bump(lid, ts=ts, merged=entry.get("status") == "merged")

    # 3. Supervisor status history (records sessions even with zero merges).
    for rec in _supervisor_status_history(project_path):
        lid = rec.get("spec_lineage_id") or rec.get("spec") or ""
        if not lid:
            continue
        # Don't double-count change_count: status-history doesn't represent
        # changes.  Just adjust seen-at timestamps.
        existing = lineages.setdefault(lid, {
            "id": lid, "display_name": lid,
            "first_seen_at": "", "last_seen_at": "",
            "is_live": False, "change_count": 0, "merged_count": 0,
        })
        ts = rec.get("rotated_at") or ""
        if ts:
            if not existing["first_seen_at"] or ts < existing["first_seen_at"]:
                existing["first_seen_at"] = ts
            if not existing["last_seen_at"] or ts > existing["last_seen_at"]:
                existing["last_seen_at"] = ts

    # 4. Legacy fallback: zero records carry a lineage at all.
    if not lineages:
        lineages[_LEGACY] = {
            "id": _LEGACY,
            "display_name": "Previous cycles (no lineage)",
            "first_seen_at": "",
            "last_seen_at": "",
            "is_live": False,
            "change_count": 0,
            "merged_count": 0,
        }

    # 5. Mark live + add diagnostic for __unknown__.
    for lid, rec in lineages.items():
        if lid == live_lineage and sentinel_running:
            rec["is_live"] = True
        if lid == _UNKNOWN:
            rec["diagnostic"] = (
                "These entries could not be attributed during backfill "
                "migration — review the state archive (LineagePaths.state_archive) "
                "by hand or purge them with a manual edit."
            )

    # Order: live first, then by last_seen_at desc, then by id.
    return sorted(
        lineages.values(),
        key=lambda r: (
            0 if r["is_live"] else 1,
            -_ts_to_key(r.get("last_seen_at", "")),
            r["id"],
        ),
    )


def _ts_to_key(ts: str) -> int:
    """Cheap sortable int from an ISO timestamp string."""
    if not ts:
        return 0
    # Leverage lexicographic ISO ordering by stripping non-digits.
    digits = "".join(ch for ch in ts if ch.isdigit())
    try:
        return int(digits[:14] or 0)
    except ValueError:
        return 0


def _is_sentinel_running(project_path: Path) -> bool:
    """Best-effort check: status.json's daemon_pid is alive."""
    status_path = project_path / ".set" / "supervisor" / "status.json"
    if not status_path.exists():
        return False
    try:
        with open(status_path) as fh:
            data = json.load(fh)
        pid = int(data.get("daemon_pid", 0))
        if pid <= 0:
            return False
        # Posix `kill -0` equivalent
        os.kill(pid, 0)
        return True
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def resolve_lineage_default(project_path: Path) -> Optional[str]:
    """Per Section 13.4: live lineage when sentinel running, else newest."""
    state_path = _state_path(project_path)
    live_lineage, _ = _read_state_lineage_and_status(state_path)
    if live_lineage and _is_sentinel_running(project_path):
        return live_lineage
    lineages = _collect_lineages(project_path)
    if not lineages:
        return None
    return lineages[0]["id"]


def apply_lineage_filter(
    records: list[dict], lineage_id: Optional[str], *,
    field: str = "spec_lineage_id",
) -> list[dict]:
    """Return records whose `field` equals `lineage_id`, or all when `__all__`.

    Records with no `field` value are bucketed as `__legacy__` and only
    survive the filter when `lineage_id == "__legacy__"` or `__all__`.
    """
    if lineage_id == _ALL or lineage_id is None:
        return list(records)
    out: list[dict] = []
    for r in records:
        record_lineage = r.get(field)
        if record_lineage is None:
            record_lineage = _LEGACY
        if record_lineage == lineage_id:
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# /api/{project}/lineages endpoint
# ---------------------------------------------------------------------------


@router.get("/api/{project}/lineages")
def get_lineages(project: str):
    """Return every lineage discovered for the project, with metadata."""
    project_path = _resolve_project(project)
    if not project_path.exists():
        raise HTTPException(404, f"Project not found: {project}")
    sentinel_running = _is_sentinel_running(project_path)
    lineages = _collect_lineages(project_path, sentinel_running=sentinel_running)
    return {
        "lineages": lineages,
        "sentinel_running": sentinel_running,
        "default": resolve_lineage_default(project_path),
    }
