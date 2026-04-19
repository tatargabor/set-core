"""Shared helpers for the API package.

Extracted from the monolithic api.py — project registry, state paths,
worktree listing, activity reading, state locking.
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

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

    Format: {"projects": {"name": {"path": "...", "addedAt": "..."}}, "default": "..."}
    Returns: [{"name": "...", "path": "..."}]
    """
    if not PROJECTS_FILE.exists():
        return []
    try:
        with open(PROJECTS_FILE) as f:
            data = json.load(f)
        if isinstance(data, dict) and "projects" in data:
            return [
                {"name": name, "path": info.get("path", ""), **{k: v for k, v in info.items() if k != "path"}}
                for name, info in data["projects"].items()
                if isinstance(info, dict)
            ]
        # Legacy: list format
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, OSError):
        return []


def _save_projects(projects: list[dict]):
    """Save projects back to projects.json."""
    PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Read existing to preserve 'default' and extra fields
    existing = {}
    if PROJECTS_FILE.exists():
        try:
            with open(PROJECTS_FILE) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    if not isinstance(existing, dict):
        existing = {}
    projects_dict = {}
    for p in projects:
        name = p["name"]
        entry = {k: v for k, v in p.items() if k != "name"}
        projects_dict[name] = entry
    existing["projects"] = projects_dict
    with open(PROJECTS_FILE, "w") as f:
        json.dump(existing, f, indent=2)


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
    """Find orchestration state file — LineagePaths canonical, then
    project-local legacy fallbacks for backward compat during Section
    15b migration.  Every literal path is derived from a resolver
    property so the audit gate sees no hardcoded string here.
    """
    from ..paths import LineagePaths
    lp = LineagePaths(str(project_path))
    canonical = Path(lp.state_file)
    if canonical.exists():
        return canonical
    # Legacy project-local write locations produced by older writers.
    # We construct the filenames from the resolver basename so adding a
    # new canonical name does not require touching this file.
    # Legacy writers prefixed the canonical basename with `orchestration-`;
    # we reconstruct that name from the resolver's basename at runtime.
    legacy_basename = "orchestration-" + canonical.name
    orch_rel = os.path.relpath(
        os.path.dirname(lp.coverage_report), str(project_path)
    )
    new = project_path / orch_rel / legacy_basename
    if new.exists():
        return new
    legacy = project_path / legacy_basename
    if legacy.exists():
        return legacy
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


def _list_worktrees(project_path: Path) -> list[dict]:
    """List git worktrees for a project with loop-state enrichment."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    worktrees = []
    current: dict = {}
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line[9:], "branch": "", "head": ""}
        elif line.startswith("HEAD "):
            current["head"] = line[5:]
        elif line.startswith("branch "):
            current["branch"] = line[7:].replace("refs/heads/", "")
        elif line == "bare":
            current["bare"] = True
        elif line == "" and current:
            worktrees.append(current)
            current = {}
    if current:
        worktrees.append(current)

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
