"""Shared helpers for the API package.

Extracted from the monolithic api.py — project registry, state paths,
worktree listing, activity reading, state locking.
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────

PROJECTS_FILE = Path.home() / ".config" / "set-core" / "projects.json"

_PURPOSE_LABELS = {
    "review": "Review",
    "smoke_fix": "Smoke Fix",
    "spec_verify": "Spec Verify",
    "classify": "Classify",
    "replan": "Replan",
    "decompose": "Decompose",
    "decompose_summary": "Summarize",
    "decompose_brief": "Planning Brief",
    "decompose_domain": "Domain Decompose",
    "decompose_merge": "Merge Plans",
    "digest": "Digest",
    "audit": "Audit",
    "build_fix": "Build Fix",
}


# ─── Project registry ────────────────────────────────────────────────


def _load_projects() -> list[dict]:
    """Load registered projects from ~/.config/set-core/projects.json.

    Thin wrapper over `set_orch.project_registry` — the implementation lives
    there so a CLI can read the registry without importing FastAPI. The
    module-level `PROJECTS_FILE` above is passed explicitly so that patching it
    on THIS module keeps working for existing callers and tests.
    """
    from ..project_registry import load_projects
    return load_projects(PROJECTS_FILE)


def _save_projects(projects: list[dict]):
    """Save projects back to projects.json. See `_load_projects` on the split."""
    from ..project_registry import save_projects
    save_projects(projects, PROJECTS_FILE)


def _claude_mangle(path: str) -> str:
    """Mangle a path the same way Claude CLI does for ~/.claude/projects/ dirs."""
    return path.lstrip("/").replace("/", "-").replace(".", "-").replace("_", "-")


def _resolve_project(project_name: str) -> Path:
    """Resolve project name to its path. Raises 404 if not found."""
    for p in _load_projects():
        if p.get("name") == project_name:
            path = Path(p["path"])
            if path.is_dir():
                return path
            raise HTTPException(404, f"Project path does not exist: {path}")
    raise HTTPException(404, f"Project not found: {project_name}")


# ─── State paths ─────────────────────────────────────────────────────


def _state_path(project_path: Path) -> Path:
    """Find orchestration state file.

    Among candidate locations (canonical LineagePaths + legacy project-local
    paths), pick the one with the newest mtime. Picking by precedence alone
    breaks for runs where the orchestrator was launched with an explicit
    legacy --state path while a stale canonical stub also exists from
    lineage migration: the legacy file is live, the canonical is frozen.
    The reader must follow the actual writer.
    """
    from ..paths import LineagePaths
    lp = LineagePaths(str(project_path))
    canonical = Path(lp.state_file)
    legacy_basename = "orchestration-" + canonical.name
    orch_rel = os.path.relpath(
        os.path.dirname(lp.coverage_report), str(project_path)
    )
    candidates = [
        canonical,
        project_path / orch_rel / legacy_basename,
        project_path / legacy_basename,
    ]
    existing = [(p, p.stat().st_mtime) for p in candidates if p.exists()]
    if existing:
        existing.sort(key=lambda x: x[1], reverse=True)
        return existing[0][0]
    return canonical


def _sentinel_dir(project_path: Path) -> Path:
    try:
        from ..paths import SetRuntime
        return Path(SetRuntime(str(project_path)).sentinel_dir)
    except Exception:
        return project_path / ".set" / "sentinel"


def _log_path(project_path: Path) -> Path:
    """Find orchestration log — shared runtime first, then legacy fallbacks."""
    try:
        from ..paths import SetRuntime
        shared = Path(SetRuntime(str(project_path)).orchestration_log)
        if shared.exists():
            return shared
    except Exception:
        pass
    new = project_path / "set" / "orchestration" / "orchestration.log"
    if new.exists():
        return new
    legacy = project_path / "orchestration.log"
    if legacy.exists():
        return legacy
    try:
        from ..paths import SetRuntime
        return Path(SetRuntime(str(project_path)).orchestration_log)
    except Exception:
        return new


def _load_archived_changes(project_path: Path) -> list[dict]:
    """Load archived changes from the state archive (LineagePaths.state_archive).

    The writer emits one flat JSON object per line (see
    ``engine._archive_completed_to_jsonl``). Later writes for the same change
    name overwrite earlier ones.  Falls back to the project-local legacy
    location for backward compat during Section 15b migration.
    """
    from ..paths import LineagePaths
    archive = Path(LineagePaths(str(project_path)).state_archive)
    if not archive.exists():
        # Legacy fallback: project_root / <basename>
        legacy = project_path / os.path.basename(str(archive))
        if legacy.exists():
            archive = legacy
    if not archive.exists():
        return []
    seen: dict[str, dict] = {}
    try:
        for line in archive.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = entry.get("name")
            if not name:
                continue
            entry["_archived"] = True
            # Section 3.4: do NOT synthesize `phase = 0` here.  Backfill
            # migration (lib/set_orch/migrations/backfill_lineage.py) is
            # the canonical fill-in-from-state-events path; entries that
            # still lack `phase` post-migration are genuinely
            # unattributed and the UI presents them under __unknown__.
            seen[name] = entry
    except OSError:
        return []
    return list(seen.values())


def _quick_status(project_path: Path) -> str:
    """Get quick orchestration status without full state parse."""
    sp = _state_path(project_path)
    if not sp.exists():
        sentinel_pid = _sentinel_dir(project_path) / "sentinel.pid"
        if sentinel_pid.exists():
            try:
                pid = int(sentinel_pid.read_text().strip())
                os.kill(pid, 0)
                return "planning"
            except (ValueError, OSError):
                pass
        orch_log = _log_path(project_path)
        if orch_log.exists():
            try:
                age = time.time() - orch_log.stat().st_mtime
                if age < 120:
                    return "planning"
            except OSError:
                pass
        return "idle"
    try:
        with open(sp) as f:
            raw = f.read()
        if "<<<<<<" in raw:
            return "corrupt"
        data = json.loads(raw)
        return data.get("status", "idle")
    except json.JSONDecodeError:
        return "corrupt"
    except OSError:
        return "error"


# ─── Worktree & activity helpers ──────────────────────────────────────


def _parse_worktree_porcelain(text: str) -> list[dict]:
    """Parse `git worktree list --porcelain` into one dict per working tree.

    Carries `prunable`, which this parser used to drop. A prunable worktree is
    one whose directory git can no longer find, so nothing can run in it — and
    dropping the line made it parse *identically to a live one*. Measured
    2026-08-23 in this repository: four worktrees listed, three of them prunable,
    and every surface reading this function presented all four as live.

    `is_main` comes from position, not from comparing paths: git always emits the
    main working tree first. Deriving it by comparing against a project root
    would be a second definition of the same fact, and the two would drift the
    first time a root was a symlink.
    """
    worktrees: list[dict] = []
    current: dict = {}
    for line in text.splitlines():
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line[9:], "branch": "", "head": "", "prunable": False}
        elif not current:
            continue
        elif line.startswith("HEAD "):
            current["head"] = line[5:]
        elif line.startswith("branch "):
            current["branch"] = line[7:].replace("refs/heads/", "")
        elif line == "bare":
            current["bare"] = True
        elif line == "detached":
            current["detached"] = True
        elif line == "prunable" or line.startswith("prunable "):
            current["prunable"] = True
            reason = line[9:].strip()
            if reason:
                current["prunable_reason"] = reason
        elif line == "":
            worktrees.append(current)
            current = {}
    if current:
        worktrees.append(current)

    for index, wt in enumerate(worktrees):
        wt["is_main"] = index == 0
    return worktrees


def _worktree_porcelain(project_path: Path) -> str:
    """The raw porcelain listing, or an empty string when git cannot answer."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.warning("worktree list failed for %s: %s", project_path, type(exc).__name__)
        return ""
    if result.returncode != 0:
        # Debug, not warning: the common non-zero here is 128 — the path is
        # simply not a git repository, which on a machine full of checkouts,
        # dot-directories and archived runs is a normal answer, not an anomaly.
        # Measured 2026-09-06 (B-139): 7 roots logged this on every fleet
        # listing, so a healthy server produced the warning continuously.
        logger.debug("worktree list returned %s for %s", result.returncode, project_path)
        return ""
    return result.stdout


def list_worktree_locations(project_path: Path) -> list[dict]:
    """The working trees of one repository — identity only, no filesystem reads.

    This is what the start guard and the start form both ask, so that what the
    screen offers and what the endpoint accepts are the same list rather than two
    definitions of it. Deliberately does NOT filter prunable entries: a filter
    downstream of a source looks exactly like a source that returned nothing, and
    the caller that shows the list wants to be able to say *why* one is missing.
    """
    return [
        {
            "path": wt["path"],
            "branch": wt.get("branch", ""),
            "is_main": bool(wt.get("is_main")),
            "prunable": bool(wt.get("prunable")),
        }
        for wt in _parse_worktree_porcelain(_worktree_porcelain(project_path))
    ]


def _list_worktrees(project_path: Path) -> list[dict]:
    """List git worktrees for a project with loop-state enrichment."""
    worktrees = _parse_worktree_porcelain(_worktree_porcelain(project_path))

    # Enrich with loop-state
    for wt in worktrees:
        wt_path = Path(wt["path"])
        loop_state = wt_path / ".set" / "loop-state.json"
        if loop_state.exists():
            try:
                with open(loop_state) as f:
                    ls = json.load(f)
                wt["iteration"] = ls.get("current_iteration", 0)
                wt["max_iterations"] = ls.get("max_iterations", 0)
            except (json.JSONDecodeError, OSError):
                pass

        activity_file = wt_path / ".set" / "activity.json"
        if activity_file.exists():
            try:
                with open(activity_file) as f:
                    act = json.load(f)
                wt["activity"] = act
            except (json.JSONDecodeError, OSError):
                pass

        logs_dir = wt_path / ".claude" / "logs"
        if logs_dir.is_dir():
            log_files = sorted(
                f.name for f in logs_dir.iterdir()
                if f.is_file() and f.suffix == ".log"
            )
            wt["logs"] = log_files

        reflection = wt_path / ".claude" / "reflection.md"
        if reflection.exists():
            wt["has_reflection"] = True

        if not wt.get("activity", {}).get("updated_at"):
            claude_dir = wt_path / ".claude"
            try:
                mtime = claude_dir.stat().st_mtime if claude_dir.exists() else wt_path.stat().st_mtime
                wt.setdefault("activity", {})["updated_at"] = datetime.fromtimestamp(
                    mtime, tz=timezone.utc
                ).isoformat()
            except OSError:
                pass

    return worktrees


def _read_activity(project_path: Path) -> list[dict]:
    """Read agent activity from all worktrees."""
    activities = []
    for wt in _list_worktrees(project_path):
        if "activity" in wt:
            activities.append({
                "worktree": wt["path"],
                "branch": wt.get("branch", ""),
                **wt["activity"],
            })
    return activities


# ─── State locking ────────────────────────────────────────────────────


async def _with_state_lock(state_file: Path, fn):
    """Execute fn while holding flock on state lock file.

    Uses asyncio.sleep() for retry delays so the Uvicorn event loop
    is never blocked during lock contention.
    """
    lock_path = str(state_file) + ".lock"
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        deadline = time.monotonic() + 10
        acquired = False
        while time.monotonic() < deadline:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                await asyncio.sleep(0.1)
        if not acquired:
            lock_fd.close()
            raise HTTPException(503, "State file locked, try again")
    try:
        return fn()
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


# ─── Change enrichment ────────────────────────────────────────────────


def _extract_session_change_name(session_path: Path) -> str:
    """Extract change name from a session JSONL file (first init message)."""
    try:
        with open(session_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get("type") == "system" and msg.get("subtype") == "init":
                    cwd = msg.get("cwd", "")
                    if "/worktrees/" in cwd or "/wt-" in cwd:
                        return Path(cwd).name
                    break
    except OSError:
        pass
    return ""


def _enrich_changes(data: dict, project_path: Path):
    """Add session_count and log file lists to change dicts."""
    proj_mangled = _claude_mangle(str(project_path))
    proj_sessions_dir = Path.home() / ".claude" / "projects" / f"-{proj_mangled}"
    proj_session_counts: dict[str, int] = {}
    if proj_sessions_dir.is_dir():
        try:
            for f in proj_sessions_dir.iterdir():
                if f.is_file() and f.suffix == ".jsonl":
                    extracted = _extract_session_change_name(f)
                    if extracted:
                        proj_session_counts[extracted] = proj_session_counts.get(extracted, 0) + 1
        except OSError:
            pass

    for c in data.get("changes", []):
        wt_path = c.get("worktree_path")
        change_name = c.get("name", "")
        count = 0
        if wt_path:
            mangled = _claude_mangle(wt_path)
            d = Path.home() / ".claude" / "projects" / f"-{mangled}"
            if d.is_dir():
                try:
                    count += sum(
                        1 for f in d.iterdir()
                        if f.is_file() and f.suffix == ".jsonl"
                    )
                except OSError:
                    pass
        count += proj_session_counts.get(change_name, 0)
        if count:
            c["session_count"] = count
        if wt_path:
            logs_dir = Path(wt_path) / ".claude" / "logs"
            if logs_dir.is_dir():
                try:
                    c["logs"] = sorted(
                        f.name for f in logs_dir.iterdir()
                        if f.is_file() and f.suffix == ".log"
                    )
                except OSError:
                    pass
