"""Section 3 — backfill `spec_lineage_id` + `phase` onto legacy archive entries.

Run once per project tree.  Reads `orchestration-plan.json::input_path` to
derive the lineage id for every legacy `state-archive.jsonl` entry that
lacks `spec_lineage_id`.  Entries that cannot be attributed (no plan
file, no recoverable hint) are tagged `__unknown__`.

Idempotent: rerunning the migration on an already-migrated archive is a
no-op (entries that already carry `spec_lineage_id` are skipped).

Section 3.4 also drops the legacy `phase = 0` fallback emitted by old
readers — reader code should now return entries verbatim, deferring to
this migration to populate `phase` where recoverable.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from set_orch.types import canonicalise_spec_path

logger = logging.getLogger(__name__)


_MIGRATION_MARKER = ".migrated-lineage"


def _archive_path(project_path: str) -> str:
    """Return the project's `state-archive.jsonl` path.

    Mirrors the engine's archive resolution (state-relative).  When
    SetRuntime points elsewhere, the runtime's archive path is checked
    too.
    """
    runtime_archive = None
    try:
        from set_orch.paths import SetRuntime
        rt = SetRuntime(project_path)
        runtime_archive = os.path.join(rt.orchestration_dir, "state-archive.jsonl")
    except Exception:
        pass
    if runtime_archive and os.path.isfile(runtime_archive):
        return runtime_archive
    # Project-local fallback (some test fixtures place state alongside the plan).
    return os.path.join(project_path, "state-archive.jsonl")


def _lineage_from_plan(project_path: str) -> Optional[str]:
    """Read `orchestration-plan.json::input_path` and canonicalise it."""
    candidates = [
        os.path.join(project_path, "orchestration-plan.json"),
    ]
    try:
        from set_orch.paths import SetRuntime
        rt = SetRuntime(project_path)
        candidates.insert(0, os.path.join(rt.orchestration_dir, "orchestration-plan.json"))
    except Exception:
        pass
    for plan_path in candidates:
        if not os.path.isfile(plan_path):
            continue
        try:
            with open(plan_path, "r", encoding="utf-8") as fh:
                plan = json.load(fh)
            ip = plan.get("input_path")
            if ip:
                try:
                    return canonicalise_spec_path(ip, project_path)
                except (ValueError, OSError):
                    return None
        except (OSError, json.JSONDecodeError):
            continue
    return None


def _phase_hints_from_state_events(project_path: str) -> dict[str, int]:
    """Recover `phase` for legacy archive entries from state-events history.

    Returns a name → phase map for changes that ever appeared in the
    state-events JSONL (live or rotated cycles).  Used as a best-effort
    fill when the archive entry itself has no `phase` field.
    """
    runtime_dir = None
    try:
        from set_orch.paths import SetRuntime
        rt = SetRuntime(project_path)
        runtime_dir = rt.orchestration_dir
    except Exception:
        pass

    hints: dict[str, int] = {}
    if not runtime_dir:
        return hints

    import glob as _glob
    files = []
    files.extend(sorted(_glob.glob(os.path.join(runtime_dir, "orchestration-state-events-cycle*.jsonl"))))
    live = os.path.join(runtime_dir, "orchestration-state-events.jsonl")
    if os.path.isfile(live):
        files.append(live)

    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    name = ev.get("change") or ""
                    data = ev.get("data") or {}
                    p = data.get("phase")
                    if isinstance(p, int) and name and name not in hints:
                        hints[name] = p
        except OSError:
            continue
    return hints


def migrate_legacy_archive(project_path: str, *, force: bool = False) -> dict:
    """Backfill `spec_lineage_id` + `phase` onto a project's archive entries.

    Returns a stats dict: {"scanned": N, "updated": M, "unknown": K,
    "skipped_already_tagged": S, "skipped_no_archive": bool}.

    Pass `force=True` to bypass the `.migrated-lineage` idempotency
    marker (useful in tests).
    """
    stats = {
        "scanned": 0,
        "updated": 0,
        "unknown": 0,
        "skipped_already_tagged": 0,
        "skipped_no_archive": False,
    }
    runtime_dir = None
    try:
        from set_orch.paths import SetRuntime
        rt = SetRuntime(project_path)
        runtime_dir = rt.orchestration_dir
    except Exception:
        pass
    marker_path = os.path.join(
        runtime_dir or project_path, _MIGRATION_MARKER,
    )
    if os.path.exists(marker_path) and not force:
        logger.debug("backfill_lineage: skip (marker exists at %s)", marker_path)
        stats["skipped_marker"] = True
        return stats

    archive = _archive_path(project_path)
    if not os.path.isfile(archive):
        stats["skipped_no_archive"] = True
        try:
            os.makedirs(os.path.dirname(marker_path), exist_ok=True)
            open(marker_path, "w").close()
        except OSError:
            pass
        return stats

    derived_lineage = _lineage_from_plan(project_path)
    phase_hints = _phase_hints_from_state_events(project_path)

    try:
        with open(archive, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        logger.warning("backfill_lineage: cannot read %s: %s", archive, exc)
        return stats

    out_lines: list[str] = []
    for raw in lines:
        raw_strip = raw.rstrip("\n")
        if not raw_strip.strip():
            out_lines.append(raw_strip)
            continue
        stats["scanned"] += 1
        try:
            entry = json.loads(raw_strip)
        except json.JSONDecodeError:
            out_lines.append(raw_strip)
            continue

        if "spec_lineage_id" in entry and entry["spec_lineage_id"]:
            stats["skipped_already_tagged"] += 1
            out_lines.append(raw_strip)
            continue

        if derived_lineage:
            entry["spec_lineage_id"] = derived_lineage
            stats["updated"] += 1
        else:
            entry["spec_lineage_id"] = "__unknown__"
            stats["unknown"] += 1
            logger.warning(
                "backfill_lineage: cannot attribute %s — tagged __unknown__",
                entry.get("name", "?"),
            )

        # 3.2 — recover phase from state-events when missing.
        if "phase" not in entry or entry.get("phase") is None:
            name = entry.get("name") or ""
            if name in phase_hints:
                entry["phase"] = phase_hints[name]

        out_lines.append(json.dumps(entry))

    try:
        with open(archive, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out_lines) + "\n")
    except OSError as exc:
        logger.warning("backfill_lineage: cannot rewrite %s: %s", archive, exc)
        return stats

    try:
        os.makedirs(os.path.dirname(marker_path), exist_ok=True)
        with open(marker_path, "w") as fh:
            fh.write(json.dumps({
                "ran_at": __import__("datetime").datetime.now().astimezone().isoformat(),
                "stats": stats,
                "derived_lineage": derived_lineage,
            }) + "\n")
    except OSError as exc:
        logger.debug("backfill_lineage: marker write failed: %s", exc)

    logger.info(
        "backfill_lineage: project=%s lineage=%s scanned=%d updated=%d unknown=%d",
        project_path, derived_lineage, stats["scanned"],
        stats["updated"], stats["unknown"],
    )
    return stats


def maybe_migrate_on_startup(project_path: str) -> None:
    """Best-effort migration entrypoint for set-web service startup.

    Called once per project the first time the web process touches it.
    Failures are logged at WARNING and do not block service startup.
    """
    try:
        migrate_legacy_archive(project_path)
    except Exception as exc:
        logger.warning(
            "backfill_lineage: maybe_migrate_on_startup raised for %s: %s",
            project_path, exc,
        )
