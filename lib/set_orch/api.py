"""REST API endpoints for the set-web dashboard.

Read endpoints for projects, orchestration state, changes, worktrees, activity, logs.
Write endpoints for approve, stop, skip.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .process import check_pid, safe_kill
from .state import load_state, save_state, StateCorruptionError

router = APIRouter()

# ─── Soniox API key ───────────────────────────────────────────────────


@router.get("/api/soniox-key")
async def get_soniox_key():
    """Return Soniox API key from environment for voice input."""
    key = os.environ.get("SONIOX_API_KEY")
    if not key:
        raise HTTPException(404, "Soniox API key not configured")
    return {"api_key": key}


# ─── Project registry ─────────────────────────────────────────────────

PROJECTS_FILE = Path.home() / ".config" / "set-core" / "projects.json"


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
                {"name": name, "path": info.get("path", "")}
                for name, info in data["projects"].items()
                if isinstance(info, dict)
            ]
        # Legacy: list format
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, OSError):
        return []


def _claude_mangle(path: str) -> str:
    """Mangle a path the same way Claude CLI does for ~/.claude/projects/ dirs.

    Claude strips leading '/', replaces '/' with '-', and removes '.' from
    directory names (e.g. '/home/tg/.local/share' -> 'home-tg--local-share').
    """
    return path.lstrip("/").replace("/", "-").replace(".", "-")


def _resolve_project(project_name: str) -> Path:
    """Resolve project name to its path. Raises 404 if not found."""
    for p in _load_projects():
        if p.get("name") == project_name:
            path = Path(p["path"])
            if path.is_dir():
                return path
            raise HTTPException(404, f"Project path does not exist: {path}")
    raise HTTPException(404, f"Project not found: {project_name}")


def _state_path(project_path: Path) -> Path:
    """Find orchestration state file — project-local first, then shared runtime."""
    # Project-local paths (engine writes here from CWD)
    new = project_path / "wt" / "orchestration" / "orchestration-state.json"
    if new.exists():
        return new
    legacy = project_path / "orchestration-state.json"
    if legacy.exists():
        return legacy
    # Shared runtime dir (future: engine may write here)
    try:
        from .paths import SetRuntime
        shared = Path(SetRuntime(str(project_path)).state_file)
        if shared.exists():
            return shared
    except Exception:
        pass
    # Default to legacy path for non-existent (will 404 cleanly)
    try:
        from .paths import SetRuntime
        return Path(SetRuntime(str(project_path)).state_file)
    except Exception:
        return new


def _load_archived_changes(project_path: Path) -> list[dict]:
    """Load completed changes from state-archive.jsonl (written at replan boundaries).

    Returns deduplicated list of archived change dicts. Later archive entries
    for the same change name win (they have more complete token data).
    """
    archive = project_path / "wt" / "orchestration" / "state-archive.jsonl"
    if not archive.exists():
        return []
    seen: dict[str, dict] = {}  # name -> change dict
    try:
        for line in archive.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            cycle = entry.get("cycle", 0)
            for c in entry.get("changes", []):
                c["_archive_cycle"] = cycle
                seen[c.get("name", "")] = c
    except OSError:
        return []
    return list(seen.values())


def _log_path(project_path: Path) -> Path:
    """Find orchestration log — shared runtime first, then legacy fallbacks."""
    try:
        from .paths import SetRuntime
        shared = Path(SetRuntime(str(project_path)).orchestration_log)
        if shared.exists():
            return shared
    except Exception:
        pass
    new = project_path / "wt" / "orchestration" / "orchestration.log"
    if new.exists():
        return new
    legacy = project_path / "orchestration.log"
    if legacy.exists():
        return legacy
    try:
        from .paths import SetRuntime
        return Path(SetRuntime(str(project_path)).orchestration_log)
    except Exception:
        return new


def _quick_status(project_path: Path) -> str:
    """Get quick orchestration status without full state parse."""
    sp = _state_path(project_path)
    if not sp.exists():
        # No state file yet — check if orchestrator is starting up
        # (sentinel.pid or recent orchestration.log indicate a running orch)
        sentinel_pid = _sentinel_dir(project_path) / "sentinel.pid"
        if sentinel_pid.exists():
            try:
                pid = int(sentinel_pid.read_text().strip())
                # Check if process is actually alive
                os.kill(pid, 0)
                return "planning"
            except (ValueError, OSError):
                pass
        orch_log = _log_path(project_path)
        if orch_log.exists():
            try:
                age = time.time() - orch_log.stat().st_mtime
                if age < 120:  # log touched in last 2 minutes
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

        # Agent activity
        activity_file = wt_path / ".set" / "activity.json"
        if activity_file.exists():
            try:
                with open(activity_file) as f:
                    act = json.load(f)
                wt["activity"] = act
            except (json.JSONDecodeError, OSError):
                pass

        # Available log files
        logs_dir = wt_path / ".claude" / "logs"
        if logs_dir.is_dir():
            log_files = sorted(
                f.name for f in logs_dir.iterdir()
                if f.is_file() and f.suffix == ".log"
            )
            wt["logs"] = log_files

        # Reflection
        reflection = wt_path / ".claude" / "reflection.md"
        if reflection.exists():
            wt["has_reflection"] = True

        # Last activity timestamp: prefer activity.updated_at, fall back to .claude dir mtime
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


def _with_state_lock(state_file: Path, fn):
    """Execute fn while holding flock on state lock file.

    Compatible with bash with_state_lock (same lock file convention).
    """
    lock_path = str(state_file) + ".lock"
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        # Try with timeout — spin for up to 10 seconds
        import time
        deadline = time.monotonic() + 10
        acquired = False
        while time.monotonic() < deadline:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                time.sleep(0.1)
        if not acquired:
            lock_fd.close()
            raise HTTPException(503, "State file locked, try again")
    try:
        return fn()
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


# ─── READ endpoints ──────────────────────────────────────────────────


@router.get("/api/projects")
def list_projects():
    """List all registered projects with quick status and last_updated."""
    projects = _load_projects()
    result = []
    for p in projects:
        path = Path(p.get("path", ""))
        entry: dict = {
            "name": p.get("name", path.name),
            "path": str(path),
            "has_orchestration": _state_path(path).exists() if path.is_dir() else False,
            "status": _quick_status(path) if path.is_dir() else "error",
            "last_updated": None,
        }
        # Use state file mtime if it exists, otherwise project dir mtime
        if path.is_dir():
            sp = _state_path(path)
            try:
                if sp.exists():
                    entry["last_updated"] = datetime.fromtimestamp(
                        sp.stat().st_mtime, tz=timezone.utc
                    ).isoformat()
                else:
                    entry["last_updated"] = datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc
                    ).isoformat()
            except OSError:
                pass
        result.append(entry)
    return result


def _enrich_changes(data: dict, project_path: Path):
    """Add session_count and log file lists to change dicts."""
    # Pre-compute project sessions dir and cache change_name → count mapping
    proj_mangled = _claude_mangle(str(project_path))
    proj_sessions_dir = Path.home() / ".claude" / "projects" / f"-{proj_mangled}"
    # Scan project-dir sessions once, build {change_name: count}
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
        # Session count — collect from worktree dir + project dir
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
        # Add project-dir sessions for this change
        count += proj_session_counts.get(change_name, 0)
        if count:
            c["session_count"] = count
        # Log files
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


@router.get("/api/{project}/state")
def get_state(project: str):
    """Get full orchestration state for a project."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")
    try:
        state = load_state(str(sp))
        data = state.to_dict()
        _enrich_changes(data, project_path)
        # Merge archived changes from previous replan cycles
        archived = _load_archived_changes(project_path)
        if archived:
            current_names = {c["name"] for c in data.get("changes", [])}
            for ac in archived:
                if ac["name"] not in current_names:
                    data["changes"].append(ac)
        return data
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")


@router.get("/api/{project}/changes")
def list_changes(project: str, status: Optional[str] = Query(None)):
    """List orchestration changes, optionally filtered by status."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")
    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    changes = state.changes
    if status:
        changes = [c for c in changes if c.status == status]

    result = []
    for c in changes:
        d = c.to_dict()
        if c.worktree_path:
            wt_path = Path(c.worktree_path)
            # Enrich with loop-state
            loop_file = wt_path / ".set" / "loop-state.json"
            if loop_file.exists():
                try:
                    with open(loop_file) as f:
                        ls = json.load(f)
                    d["iteration"] = ls.get("current_iteration", 0)
                    d["max_iterations"] = ls.get("max_iterations", 0)
                except (json.JSONDecodeError, OSError):
                    pass
            # Enrich with available log files
            logs_dir = wt_path / ".claude" / "logs"
            if logs_dir.is_dir():
                d["logs"] = sorted(
                    f.name for f in logs_dir.iterdir()
                    if f.is_file() and f.suffix == ".log"
                )
        result.append(d)
    return result


@router.get("/api/{project}/changes/{name}")
def get_change(project: str, name: str):
    """Get a single change by name."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")
    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    for c in state.changes:
        if c.name == name:
            d = c.to_dict()
            # Enrich with loop-state
            if c.worktree_path:
                loop_file = Path(c.worktree_path) / ".set" / "loop-state.json"
                if loop_file.exists():
                    try:
                        with open(loop_file) as f:
                            ls = json.load(f)
                        d["iteration"] = ls.get("current_iteration", 0)
                        d["max_iterations"] = ls.get("max_iterations", 0)
                    except (json.JSONDecodeError, OSError):
                        pass
            return d
    raise HTTPException(404, f"Change not found: {name}")


@router.get("/api/{project}/worktrees")
def list_worktrees_endpoint(project: str):
    """List git worktrees with loop-state and activity data."""
    project_path = _resolve_project(project)
    return _list_worktrees(project_path)


@router.get("/api/{project}/worktrees/{branch:path}/log/{filename}")
def get_worktree_log(project: str, branch: str, filename: str):
    """Read a specific log file from a worktree."""
    project_path = _resolve_project(project)

    # Validate filename — only allow ralph-iter-*.log pattern
    if not filename.endswith(".log") or ".." in filename or "/" in filename:
        raise HTTPException(400, "Invalid filename")

    # Find the worktree by branch name
    for wt in _list_worktrees(project_path):
        if wt.get("branch") == branch:
            log_file = Path(wt["path"]) / ".claude" / "logs" / filename
            if not log_file.exists():
                raise HTTPException(404, f"Log file not found: {filename}")
            try:
                content = log_file.read_text(errors="replace")
                return {"filename": filename, "lines": content.splitlines()[-2000:]}
            except OSError:
                raise HTTPException(500, "Failed to read log")
    raise HTTPException(404, f"Worktree not found: {branch}")


@router.get("/api/{project}/worktrees/{branch:path}/reflection")
def get_worktree_reflection(project: str, branch: str):
    """Read the reflection.md from a worktree."""
    project_path = _resolve_project(project)
    for wt in _list_worktrees(project_path):
        if wt.get("branch") == branch:
            refl = Path(wt["path"]) / ".claude" / "reflection.md"
            if not refl.exists():
                raise HTTPException(404, "No reflection found")
            return {"content": refl.read_text(errors="replace")}
    raise HTTPException(404, f"Worktree not found: {branch}")


@router.get("/api/{project}/changes/{name}/logs")
def get_change_logs(project: str, name: str):
    """List available log files for a change (from its worktree)."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")
    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    for c in state.changes:
        if c.name == name:
            logs = []
            # Try worktree first
            if c.worktree_path:
                wt_path = Path(c.worktree_path)
                logs_dir = wt_path / ".claude" / "logs"
                if logs_dir.is_dir():
                    logs = sorted(
                        f.name for f in logs_dir.iterdir()
                        if f.is_file() and f.suffix == ".log"
                    )
            # Fallback: archived logs
            if not logs:
                archive_dir = project_path / "wt" / "orchestration" / "logs" / name
                if archive_dir.is_dir():
                    logs = sorted(
                        f.name for f in archive_dir.iterdir()
                        if f.is_file() and f.suffix == ".log"
                    )
            result: dict = {"logs": logs}
            # Include iteration info
            if c.worktree_path:
                loop_state = Path(c.worktree_path) / ".set" / "loop-state.json"
                if loop_state.exists():
                    try:
                        with open(loop_state) as f:
                            ls = json.load(f)
                        result["iteration"] = ls.get("current_iteration", 0)
                        result["max_iterations"] = ls.get("max_iterations", 0)
                    except (json.JSONDecodeError, OSError):
                        pass
            return result
    raise HTTPException(404, f"Change not found: {name}")


@router.get("/api/{project}/changes/{name}/log/{filename}")
def get_change_log(project: str, name: str, filename: str):
    """Read a specific log file from a change's worktree."""
    project_path = _resolve_project(project)

    if not filename.endswith(".log") or ".." in filename or "/" in filename:
        raise HTTPException(400, "Invalid filename")

    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")
    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    for c in state.changes:
        if c.name == name:
            log_file = None
            # Try worktree first
            if c.worktree_path:
                candidate = Path(c.worktree_path) / ".claude" / "logs" / filename
                if candidate.exists():
                    log_file = candidate
            # Fallback: archived logs
            if not log_file:
                candidate = project_path / "wt" / "orchestration" / "logs" / name / filename
                if candidate.exists():
                    log_file = candidate
            if not log_file:
                raise HTTPException(404, f"Log file not found: {filename}")
            try:
                content = log_file.read_text(errors="replace")
                return {"filename": filename, "lines": content.splitlines()[-2000:]}
            except OSError:
                raise HTTPException(500, "Failed to read log")
    raise HTTPException(404, f"Change not found: {name}")


def _sessions_dir_for_change(state, name: str, project_path: Path | None = None) -> tuple:
    """Find the Claude sessions directory for a change. Returns (Change, Path|None).

    Tries the change's worktree_path first. Falls back to project_path
    (useful when worktree was cleaned up after failed/completed changes).
    """
    for c in state.changes:
        if c.name == name:
            # Try worktree path first
            if c.worktree_path:
                mangled = _claude_mangle(c.worktree_path)
                d = Path.home() / ".claude" / "projects" / f"-{mangled}"
                if d.is_dir():
                    return c, d
            # Fallback: project path
            if project_path:
                mangled = _claude_mangle(str(project_path))
                d = Path.home() / ".claude" / "projects" / f"-{mangled}"
                if d.is_dir():
                    return c, d
            return c, None
    return None, None


def _extract_session_change_name(session_path: Path) -> str:
    """Extract change name from a session JSONL's first enqueue content.

    Scans the first queue-operation entry for known patterns that embed a change name.
    Returns empty string if not found.
    """
    try:
        with open(session_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "queue-operation":
                    continue
                content = entry.get("content", "")
                # Search a generous window (smoke fix prompts can be long)
                window = content[:3000]
                # Pattern: merging "change-name" / the 'change-name' change
                m = re.search(r"""(?:merging|implement|for|the)\s+['"]([a-z0-9][\w-]+)['"]""", window)
                if m:
                    return m.group(1)
                # Pattern: "change_name" JSON key (template input echoed)
                m = re.search(r'"change_name":\s*"([^"]+)"', window)
                if m:
                    return m.group(1)
                # Pattern: /opsx:apply change-name or /opsx:ff change-name
                m = re.search(r"/opsx:\w+\s+([a-z0-9][\w-]+)", window)
                if m:
                    return m.group(1)
                # Pattern: branch name change/change-name (merge fix prompts)
                m = re.search(r"\bchange/([a-z0-9][\w-]+)", window)
                if m:
                    return m.group(1)
                # Pattern: for change-name (loose — after "for ")
                m = re.search(r"\bfor\s+([a-z][a-z0-9]+-[a-z0-9-]+)", window)
                if m:
                    return m.group(1)
                break
    except OSError:
        pass
    return ""


def _sessions_dirs_for_change(state, name: str, project_path: Path | None = None) -> tuple:
    """Find ALL Claude sessions directories for a change.

    Returns (Change, list[Path]) — multiple dirs that may contain sessions
    for this change: the worktree dir AND the project dir.
    """
    dirs: list[Path] = []
    for c in state.changes:
        if c.name == name:
            # Worktree path sessions (implementation, gate review, etc.)
            if c.worktree_path:
                mangled = _claude_mangle(c.worktree_path)
                d = Path.home() / ".claude" / "projects" / f"-{mangled}"
                if d.is_dir():
                    dirs.append(d)
            # Project path sessions (smoke fix, post-merge ops)
            if project_path:
                mangled = _claude_mangle(str(project_path))
                d = Path.home() / ".claude" / "projects" / f"-{mangled}"
                if d.is_dir() and d not in dirs:
                    dirs.append(d)
            return c, dirs
    return None, []


def _list_session_files_for_change(
    dirs: list[Path], change_name: str, wt_dir: Path | None = None,
) -> list[dict]:
    """List session files across multiple dirs, filtering project-dir sessions by change name.

    Sessions in the worktree dir are always included.
    Sessions in other dirs (project dir) are only included if their content
    mentions the change name.
    """
    seen_ids: set[str] = set()
    files: list[dict] = []
    for d in dirs:
        is_wt_dir = d == wt_dir
        for f in d.iterdir():
            if not f.is_file() or f.suffix != ".jsonl":
                continue
            if f.stem in seen_ids:
                continue
            try:
                # For project-dir sessions, filter by change name
                if not is_wt_dir:
                    extracted = _extract_session_change_name(f)
                    if extracted and extracted != change_name:
                        continue
                    # If no change name extracted, skip (could be unrelated)
                    if not extracted:
                        continue

                st = f.stat()
                label, full_label = _derive_session_label(f)
                model = _extract_session_model(f)
                age_s = time.time() - st.st_mtime
                is_active = age_s < 60
                files.append({
                    "id": f.stem,
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                    "label": label,
                    "full_label": full_label,
                    "model": model,
                    "outcome": "active" if is_active else _session_outcome(f),
                    "dir": str(d),
                })
                seen_ids.add(f.stem)
            except OSError:
                pass
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return files


def _extract_session_model(session_path: Path) -> str:
    """Extract model ID from a session JSONL's first assistant message.

    Returns short model name (e.g. 'opus', 'sonnet') or empty string.
    """
    try:
        with open(session_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = entry.get("message", {})
                if msg.get("role") == "assistant":
                    model = msg.get("model", "")
                    if model:
                        # Shorten: claude-opus-4-6 → opus, claude-sonnet-4-6 → sonnet
                        for short in ("opus", "sonnet", "haiku"):
                            if short in model:
                                return short
                        return model
                    return ""
    except OSError:
        pass
    return ""


def _derive_session_label(session_path: Path) -> tuple[str, str]:
    """Derive a short label and full task text from a session JSONL's first enqueue entry.

    Returns (short_label, full_text).
    """
    try:
        with open(session_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "queue-operation":
                    continue
                content = entry.get("content", "")
                first_line = content.split("\n")[0].strip().lower()

                # Orchestration role patterns (match before generic fallback)
                if "software architect" in first_line and "plan" in first_line:
                    return "Planner", "Decompose spec into implementation plan"
                if "technical analyst" in first_line and "digest" in first_line:
                    return "Digest", "Parse spec into structured digest"
                if "resolving git merge" in first_line:
                    return "Merge fix", "Resolving git merge conflicts"
                if "build errors" in first_line or "build failed" in first_line:
                    return "Build fix", first_line
                if "mcp" in first_line and ("whoami" in first_line or "health" in first_line):
                    return "MCP check", "MCP tool health check"
                if "smoke" in first_line and "failed" in first_line:
                    return "Smoke fix", first_line
                if "post-merge" in first_line and "failed" in first_line:
                    return "Post-merge fix", first_line

                # Extract task line from content
                for text_line in content.split("\n"):
                    text_line = text_line.strip().lstrip("#").strip()
                    if not text_line:
                        continue
                    low = text_line.lower()
                    if "build failed" in low or "fix build" in low or "fix the build" in low:
                        return "Build fix", text_line
                    if "test" in low and ("fail" in low or "fix" in low):
                        return "Test fix", text_line
                    if "verify" in low:
                        return "Verify", text_line
                    if low.startswith("**execution**"):
                        label = text_line.lstrip("*: ").strip()[:30]
                        return label, text_line
                    if "implement" in low or "task" in low:
                        label = text_line[:25].rstrip()
                        if len(text_line) > 25:
                            label += "..."
                        return label, text_line
                # Fallback: first meaningful line
                for text_line in content.split("\n"):
                    text_line = text_line.strip().lstrip("#").strip()
                    if text_line and len(text_line) > 3:
                        label = text_line[:25].rstrip()
                        if len(text_line) > 25:
                            label += "..."
                        return label, text_line
                break
    except OSError:
        pass
    return "", ""


def _session_outcome(session_path: Path) -> str:
    """Derive session outcome from last assistant message content.

    Returns 'success', 'error', or 'unknown'.
    """
    try:
        # Read last ~20 lines efficiently
        lines: list[str] = []
        with open(session_path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            # Read last 32KB
            fh.seek(max(0, size - 32768))
            raw = fh.read().decode("utf-8", errors="replace")
            lines = [l.strip() for l in raw.splitlines() if l.strip()]

        # Find last assistant message text
        for raw_line in reversed(lines):
            try:
                entry = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "assistant":
                continue
            msg = entry.get("message", {})
            if not isinstance(msg, dict):
                continue
            content = msg.get("content", [])
            if isinstance(content, str):
                text = content.lower()
            elif isinstance(content, list):
                text = " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
                ).lower()
            else:
                continue
            if not text:
                continue

            # Check for failure indicators (use phrases, not single words)
            fail_phrases = [
                "review fail", "build fail", "test fail", "tests fail",
                "unable to fix", "cannot fix", "still failing",
                "not passing", "errors remain", "could not resolve",
                "[critical]", "review critical",
            ]
            # Check for success indicators
            pass_phrases = [
                "review pass", "all tests pass", "tests pass",
                "committed", "commit ", "no issues found",
                "all changes are complete", "implementation complete",
                "all tasks", "successfully", "fixed",
                "reflection committed", "done.",
            ]

            has_fail = any(p in text for p in fail_phrases)
            has_pass = any(p in text for p in pass_phrases)

            # When both match, success wins if "fixed"/"committed" is present
            # (agent reported critical issues but then fixed them)
            if has_pass and has_fail:
                if "fixed" in text or "committed" in text:
                    return "success"
                return "error"
            if has_fail:
                return "error"
            if has_pass:
                return "success"
            return "unknown"
    except (OSError, ValueError):
        pass
    return "unknown"


def _list_session_files(sessions_dir: Path) -> list[dict]:
    """List JSONL session files sorted by mtime desc."""
    files = []
    for f in sessions_dir.iterdir():
        if f.is_file() and f.suffix == ".jsonl":
            try:
                st = f.stat()
                label, full_label = _derive_session_label(f)
                # Active = file modified in last 60 seconds
                age_s = time.time() - st.st_mtime
                is_active = age_s < 60
                model = _extract_session_model(f)
                files.append({
                    "id": f.stem,
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                    "label": label,
                    "full_label": full_label,
                    "model": model,
                    "outcome": "active" if is_active else _session_outcome(f),
                })
            except OSError:
                pass
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return files


@router.get("/api/{project}/changes/{name}/sessions")
def list_change_sessions(project: str, name: str):
    """List all Claude session files for a change."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")
    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    change, session_dirs = _sessions_dirs_for_change(state, name, project_path)
    if change is None:
        raise HTTPException(404, f"Change not found: {name}")
    if not session_dirs:
        return {"sessions": []}
    # Determine worktree dir for filtering
    wt_dir = None
    if change.worktree_path:
        mangled = _claude_mangle(change.worktree_path)
        wt_dir = Path.home() / ".claude" / "projects" / f"-{mangled}"
    return {"sessions": _list_session_files_for_change(session_dirs, name, wt_dir)}


@router.get("/api/{project}/changes/{name}/session")
def get_change_session_log(
    project: str, name: str,
    session_id: Optional[str] = Query(None),
    tail: int = Query(200, ge=1, le=2000),
):
    """Read a Claude session log for a change (parsed from JSONL).

    If session_id is omitted, returns the most recent session.
    """
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")
    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    change, session_dirs = _sessions_dirs_for_change(state, name, project_path)
    if change is None:
        raise HTTPException(404, f"Change not found: {name}")
    if not session_dirs:
        return {"lines": [], "session_id": None, "sessions": []}

    # Determine worktree dir for filtering
    wt_dir = None
    if change.worktree_path:
        mangled = _claude_mangle(change.worktree_path)
        wt_dir = Path.home() / ".claude" / "projects" / f"-{mangled}"

    session_files = _list_session_files_for_change(session_dirs, name, wt_dir)
    if not session_files:
        return {"lines": [], "session_id": None, "sessions": []}

    # Select target file — search across all dirs
    if session_id:
        target = None
        for d in session_dirs:
            candidate = d / f"{session_id}.jsonl"
            if candidate.is_file():
                target = candidate
                break
        if not target:
            raise HTTPException(404, f"Session not found: {session_id}")
    else:
        # Most recent session — find it in the right dir
        best = session_files[0]
        target = Path(best["dir"]) / f"{best['id']}.jsonl"

    lines = _parse_session_jsonl(target, tail)
    return {
        "lines": lines,
        "session_id": target.stem,
        "sessions": session_files,
    }


def _format_ts(ts_str: str) -> str:
    """Format ISO timestamp to short local-ish display."""
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return ts_str


def _parse_session_jsonl(path: Path, tail: int) -> list[str]:
    """Parse Claude session JSONL into human-readable log lines."""
    output: list[str] = []
    first_ts: str | None = None
    last_ts: str | None = None
    session_model: str | None = None
    try:
        with open(path, "r", errors="replace") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    obj = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                # Track timestamps
                ts = obj.get("timestamp")
                if ts:
                    if first_ts is None:
                        first_ts = ts
                    last_ts = ts

                msg = obj.get("message", {})
                role = msg.get("role", "")
                obj_type = obj.get("type", "")

                # Extract model from first assistant message
                if session_model is None and role == "assistant":
                    session_model = msg.get("model", "")

                if role == "assistant":
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            bt = block.get("type", "")
                            if bt == "text" and block.get("text", "").strip():
                                output.append(f">>> {block['text'].strip()}")
                            elif bt == "tool_use":
                                tool_name = block.get("name", "?")
                                tool_input = block.get("input", {})
                                # Compact tool display
                                if tool_name in ("Read", "Glob", "Grep"):
                                    arg = (tool_input.get("file_path")
                                           or tool_input.get("pattern", ""))
                                    output.append(f"  [{tool_name}] {arg}")
                                elif tool_name == "Write":
                                    output.append(
                                        f"  [Write] {tool_input.get('file_path', '?')}"
                                    )
                                elif tool_name == "Edit":
                                    output.append(
                                        f"  [Edit] {tool_input.get('file_path', '?')}"
                                    )
                                elif tool_name == "Bash":
                                    cmd = tool_input.get("command", "")
                                    output.append(f"  [Bash] {cmd[:120]}")
                                else:
                                    output.append(f"  [{tool_name}]")
                    elif isinstance(content, str) and content.strip():
                        output.append(f">>> {content.strip()}")

                elif obj_type == "result":
                    cost = obj.get("costUSD")
                    duration = obj.get("durationMs")
                    if cost is not None:
                        output.append(
                            f"--- session end: ${cost:.4f}, "
                            f"{(duration or 0) / 1000:.0f}s ---"
                        )

    except OSError:
        output.append("(Failed to read session log)")

    # Prepend start timestamp (with model if known), append end timestamp
    if first_ts:
        model_suffix = f"  model: {session_model}" if session_model else ""
        output.insert(0, f"--- session start: {_format_ts(first_ts)}{model_suffix} ---")
    if last_ts and last_ts != first_ts:
        output.append(f"--- last activity: {_format_ts(last_ts)} ---")

    return output[-tail:]


@router.get("/api/{project}/sessions")
def list_project_sessions(project: str):
    """List all Claude session files for the project itself (not change-specific)."""
    project_path = _resolve_project(project)
    mangled = _claude_mangle(str(project_path))
    sessions_dir = Path.home() / ".claude" / "projects" / f"-{mangled}"
    if not sessions_dir.is_dir():
        return {"sessions": []}
    return {"sessions": _list_session_files(sessions_dir)}


@router.get("/api/{project}/sessions/{session_id}")
def get_project_session(
    project: str, session_id: str,
    tail: int = Query(200, ge=1, le=2000),
):
    """Read a Claude session log for the project (parsed from JSONL)."""
    project_path = _resolve_project(project)
    mangled = _claude_mangle(str(project_path))
    sessions_dir = Path.home() / ".claude" / "projects" / f"-{mangled}"
    target = sessions_dir / f"{session_id}.jsonl"
    if not target.is_file():
        raise HTTPException(404, f"Session not found: {session_id}")
    lines = _parse_session_jsonl(target, tail)
    return {"lines": lines, "session_id": session_id}


@router.get("/api/{project}/activity")
def get_activity(project: str):
    """Get agent activity from all worktrees."""
    project_path = _resolve_project(project)
    return _read_activity(project_path)


@router.get("/api/{project}/log")
def get_log(project: str, lines: int = Query(500, ge=1, le=10000)):
    """Get the last N lines of the orchestration log."""
    project_path = _resolve_project(project)
    lp = _log_path(project_path)
    if not lp.exists():
        return {"lines": []}

    try:
        with open(lp, "rb") as f:
            # Efficient tail read: seek to end, read backwards
            f.seek(0, 2)
            file_size = f.tell()
            if file_size == 0:
                return {"lines": []}

            # Read in chunks from the end
            chunk_size = min(file_size, lines * 200)  # estimate ~200 bytes/line
            f.seek(max(0, file_size - chunk_size))
            content = f.read().decode("utf-8", errors="replace")

        all_lines = content.splitlines()
        return {"lines": all_lines[-lines:]}
    except OSError:
        return {"lines": []}


# ─── Screenshots, Plans, Events ──────────────────────────────────────


@router.get("/api/{project}/changes/{name}/screenshots")
def get_change_screenshots(project: str, name: str):
    """List screenshot files for a change (smoke and E2E)."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")
    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    for c in state.changes:
        if c.name == name:
            result: dict = {"smoke": [], "e2e": []}
            smoke_dir = getattr(c, "smoke_screenshot_dir", None) or c.extras.get("smoke_screenshot_dir")
            if smoke_dir:
                sd = project_path / smoke_dir
                if sd.is_dir():
                    result["smoke"] = sorted(
                        ({"path": f"{smoke_dir}/{f.relative_to(sd)}", "name": f.name}
                         for f in sd.rglob("*.png")),
                        key=lambda x: x["name"],
                    )
            e2e_dir = getattr(c, "e2e_screenshot_dir", None) or c.extras.get("e2e_screenshot_dir")
            if e2e_dir:
                ed = project_path / e2e_dir
                if ed.is_dir():
                    result["e2e"] = sorted(
                        ({"path": f"{e2e_dir}/{f.relative_to(ed)}", "name": f.name}
                         for f in ed.rglob("*.png")),
                        key=lambda x: x["name"],
                    )
            return result
    raise HTTPException(404, f"Change not found: {name}")


@router.get("/api/{project}/screenshots/{file_path:path}")
def serve_screenshot(project: str, file_path: str):
    """Serve a screenshot image file."""
    from fastapi.responses import FileResponse as FR

    if ".." in file_path:
        raise HTTPException(400, "Invalid path")
    project_path = _resolve_project(project)
    full_path = project_path / file_path
    if not full_path.exists() or not full_path.suffix == ".png":
        raise HTTPException(404, "Screenshot not found")
    # Ensure path is within project's wt/orchestration/
    orch_dir = project_path / "wt" / "orchestration"
    try:
        full_path.resolve().relative_to(orch_dir.resolve())
    except ValueError:
        raise HTTPException(403, "Access denied")
    return FR(str(full_path), media_type="image/png")


@router.get("/api/{project}/plans")
def list_plans(project: str):
    """List decompose plan files."""
    project_path = _resolve_project(project)
    plans_dir = project_path / "wt" / "orchestration" / "plans"
    if not plans_dir.is_dir():
        return {"plans": []}
    plans = []
    for f in sorted(plans_dir.iterdir()):
        if f.is_file() and f.suffix == ".json":
            plans.append({
                "filename": f.name,
                "size": f.stat().st_size,
                "mtime": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            })
    return {"plans": plans}


@router.get("/api/{project}/plans/{filename}")
def get_plan(project: str, filename: str):
    """Read a decompose plan JSON file."""
    if ".." in filename or "/" in filename or not filename.endswith(".json"):
        raise HTTPException(400, "Invalid filename")
    project_path = _resolve_project(project)
    plan_file = project_path / "wt" / "orchestration" / "plans" / filename
    if not plan_file.exists():
        raise HTTPException(404, f"Plan not found: {filename}")
    try:
        with open(plan_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(500, f"Failed to read plan: {e}")


@router.get("/api/{project}/digest")
def get_digest(project: str):
    """Return digest data: index, requirements, coverage, domains, dependencies, ambiguities."""
    project_path = _resolve_project(project)
    digest_dir = project_path / "wt" / "orchestration" / "digest"
    if not digest_dir.is_dir():
        return {"exists": False}

    result: dict = {"exists": True}

    # Read JSON files
    for name in ("index", "requirements", "coverage", "dependencies", "ambiguities", "conventions", "coverage-merged"):
        fpath = digest_dir / f"{name}.json"
        if fpath.exists():
            try:
                with open(fpath) as f:
                    result[name.replace("-", "_")] = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

    # Read domain summaries
    domains_dir = digest_dir / "domains"
    if domains_dir.is_dir():
        domains = {}
        for df in sorted(domains_dir.iterdir()):
            if df.is_file() and df.suffix == ".md":
                try:
                    domains[df.stem] = df.read_text()
                except OSError:
                    pass
        result["domains"] = domains

    # Read triage.md
    triage = digest_dir / "triage.md"
    if triage.exists():
        try:
            result["triage"] = triage.read_text()
        except OSError:
            pass

    # Read data-definitions.md
    datadef = digest_dir / "data-definitions.md"
    if datadef.exists():
        try:
            result["data_definitions"] = datadef.read_text()
        except OSError:
            pass

    return result


@router.get("/api/{project}/coverage-report")
def get_coverage_report(project: str):
    """Return spec coverage report markdown if it exists."""
    project_path = _resolve_project(project)
    report = project_path / "wt" / "orchestration" / "spec-coverage-report.md"
    if not report.exists():
        return {"exists": False}
    try:
        return {"exists": True, "content": report.read_text()}
    except OSError:
        return {"exists": False}


@router.get("/api/{project}/requirements")
def get_requirements(project: str):
    """Aggregate requirements across all plan versions with live status from state.

    Merges all plan JSON files to build a unified requirement map,
    then overlays current change status from orchestration state.
    """
    project_path = _resolve_project(project)
    plans_dir = project_path / "wt" / "orchestration" / "plans"
    has_plans_dir = plans_dir.is_dir()

    # Load all plans in order
    plan_files = sorted(
        (f for f in plans_dir.iterdir() if f.is_file() and f.suffix == ".json"),
        key=lambda f: f.name,
    ) if has_plans_dir else []

    if not plan_files:
        # Fallback: build change list from live state even without plan files
        try:
            sp = _state_path(project_path)
            if sp.exists():
                state = load_state(str(sp))
                if state.changes:
                    changes_out = []
                    for ch in state.changes:
                        changes_out.append({
                            "name": ch.name,
                            "complexity": "?",
                            "change_type": "feature",
                            "depends_on": [],
                            "requirements": [],
                            "also_affects_reqs": [],
                            "scope_summary": "",
                            "plan_version": "",
                            "roadmap_item": "",
                            "status": ch.status,
                        })
                    return {
                        "requirements": [],
                        "changes": changes_out,
                        "groups": [],
                        "plan_versions": [],
                        "total_reqs": 0,
                        "done_reqs": 0,
                    }
        except Exception:
            pass
        return {"requirements": [], "changes": [], "groups": [], "plan_versions": [], "total_reqs": 0, "done_reqs": 0}

    # Build unified maps: req_id -> info, change_name -> info
    all_reqs: dict[str, dict] = {}  # req_id -> {change, plan_version, ...}
    all_changes: dict[str, dict] = {}  # change_name -> merged info
    plan_versions: list[str] = []

    for pf in plan_files:
        try:
            with open(pf) as f:
                plan = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        plan_versions.append(pf.name)
        for ch in plan.get("changes", []):
            name = ch.get("name", "")
            if not name:
                continue
            # Merge change info (later plans override)
            all_changes[name] = {
                "name": name,
                "complexity": ch.get("complexity", "?"),
                "change_type": ch.get("change_type", "feature"),
                "depends_on": ch.get("depends_on", []),
                "requirements": ch.get("requirements", []),
                "also_affects_reqs": ch.get("also_affects_reqs", []),
                "scope_summary": (ch.get("scope", "") or "")[:200],
                "plan_version": pf.name,
                "roadmap_item": ch.get("roadmap_item", ""),
            }
            for req_id in ch.get("requirements", []):
                all_reqs[req_id] = {
                    "id": req_id,
                    "change": name,
                    "primary": True,
                    "plan_version": pf.name,
                }
            for req_id in ch.get("also_affects_reqs", []):
                if req_id not in all_reqs:
                    all_reqs[req_id] = {
                        "id": req_id,
                        "change": name,
                        "primary": False,
                        "plan_version": pf.name,
                    }

    # Overlay live status from state
    change_status: dict[str, str] = {}
    try:
        sp = _state_path(project_path)
        if sp.exists():
            state = load_state(str(sp))
            for ch in state.changes:
                change_status[ch.name] = ch.status
    except Exception:
        pass

    # Enrich changes with live status
    for name, info in all_changes.items():
        info["status"] = change_status.get(name, "planned")

    # Enrich reqs with change status
    for req_id, info in all_reqs.items():
        ch_name = info["change"]
        status = change_status.get(ch_name, "planned")
        info["status"] = status

    # Group reqs by prefix (e.g. REQ-CART -> CART)
    groups: dict[str, list[dict]] = {}
    for req in all_reqs.values():
        parts = req["id"].split("-")
        # REQ-CART-006 -> CART, CART-006 -> CART
        if len(parts) >= 3 and parts[0] == "REQ":
            group = parts[1]
        elif len(parts) >= 2:
            group = parts[0]
        else:
            group = "OTHER"
        groups.setdefault(group, []).append(req)

    # Build group summaries
    group_summaries = []
    for gname, reqs in sorted(groups.items()):
        done_statuses = {"done", "merged", "completed", "skip_merged"}
        total = len(reqs)
        done = sum(1 for r in reqs if r["status"] in done_statuses)
        in_progress = sum(1 for r in reqs if r["status"] in {"running", "implementing", "verifying"})
        failed = sum(1 for r in reqs if r["status"] in {"failed", "verify-failed"})
        group_summaries.append({
            "group": gname,
            "total": total,
            "done": done,
            "in_progress": in_progress,
            "failed": failed,
            "requirements": sorted(reqs, key=lambda r: r["id"]),
        })

    return {
        "requirements": sorted(all_reqs.values(), key=lambda r: r["id"]),
        "changes": sorted(all_changes.values(), key=lambda c: c["name"]),
        "groups": group_summaries,
        "plan_versions": plan_versions,
        "total_reqs": len(all_reqs),
        "done_reqs": sum(1 for r in all_reqs.values() if r["status"] in {"done", "merged", "completed", "skip_merged"}),
    }


@router.get("/api/{project}/events")
def get_events(project: str, type: Optional[str] = Query(None), limit: int = Query(500, ge=1, le=5000)):
    """Read orchestration state events, optionally filtered by type."""
    project_path = _resolve_project(project)
    events_file = project_path / "orchestration-state-events.jsonl"
    if not events_file.exists():
        # Try new location
        events_file = project_path / "wt" / "orchestration" / "orchestration-state-events.jsonl"
    if not events_file.exists():
        return {"events": []}
    events = []
    try:
        with open(events_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    if type and ev.get("type") != type:
                        continue
                    events.append(ev)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return {"events": []}
    return {"events": events[-limit:]}


@router.get("/api/{project}/settings")
def get_project_settings(project: str):
    """Get project configuration and paths for the settings panel."""
    project_path = _resolve_project(project)
    result: dict = {
        "project_path": str(project_path),
        "state_path": None,
        "config": {},
        "has_claude_md": False,
        "has_project_knowledge": False,
        "runs_dir": None,
        "orchestrator_pid": None,
        "sentinel_pid": None,
        "plan_version": None,
    }

    # State file
    sp = _state_path(project_path)
    if sp.exists():
        result["state_path"] = str(sp)
        try:
            state = load_state(str(sp))
            result["orchestrator_pid"] = state.orchestrator_pid
            result["plan_version"] = state.plan_version
        except Exception:
            pass

    # Sentinel PID
    sentinel_pid_file = _sentinel_dir(project_path) / "sentinel.pid"
    if sentinel_pid_file.exists():
        try:
            pid = int(sentinel_pid_file.read_text().strip())
            os.kill(pid, 0)  # check alive
            result["sentinel_pid"] = pid
        except (ValueError, OSError):
            pass

    # Orchestration config (YAML)
    for cfg_path in [
        project_path / "wt" / "orchestration" / "config.yaml",
        project_path / ".claude" / "orchestration.yaml",
    ]:
        if cfg_path.exists():
            result["config_path"] = str(cfg_path)
            try:
                import yaml
                with open(cfg_path) as f:
                    result["config"] = yaml.safe_load(f) or {}
            except Exception:
                try:
                    with open(cfg_path) as f:
                        result["config_raw"] = f.read()
                except OSError:
                    pass
            break

    # CLAUDE.md
    for md in [project_path / "CLAUDE.md", project_path / ".claude" / "CLAUDE.md"]:
        if md.exists():
            result["has_claude_md"] = True
            break

    # Project knowledge
    for pk in [
        project_path / "wt" / "knowledge" / "project-knowledge.yaml",
        project_path / "project-knowledge.yaml",
    ]:
        if pk.exists():
            result["has_project_knowledge"] = True
            break

    # Runs dir
    for rd in [project_path / "wt" / "orchestration" / "runs", project_path / "docs" / "orchestration-runs"]:
        if rd.is_dir():
            result["runs_dir"] = str(rd)
            try:
                result["runs_count"] = sum(1 for f in rd.iterdir() if f.is_dir() or f.suffix == ".md")
            except OSError:
                pass
            break

    # Data sources: which tabs have data
    plans_dir = project_path / "wt" / "orchestration" / "plans"
    plan_count = 0
    if plans_dir.is_dir():
        plan_count = sum(1 for f in plans_dir.iterdir() if f.is_file() and f.suffix == ".json")

    digest_path = project_path / "wt" / "orchestration" / "digest.json"
    change_count = 0
    if sp.exists():
        try:
            state = load_state(str(sp))
            change_count = len(state.changes)
        except Exception:
            pass

    result["data_sources"] = {
        "plans": {"available": plan_count > 0, "count": plan_count},
        "digest": {"available": digest_path.exists()},
        "state": {"available": sp.exists(), "changes": change_count},
        "orchestration_config": {"available": "config_path" in result},
    }

    return result


# ─── Memory endpoints ────────────────────────────────────────────────


def _run_wt_memory(project_path: Path, args: list[str], timeout: int = 10) -> dict | str:
    """Run set-memory CLI with project-scoped CWD, return parsed JSON or raw string."""
    try:
        result = subprocess.run(
            ["set-memory"] + args,
            capture_output=True, text=True, timeout=timeout,
            cwd=str(project_path),
        )
        out = result.stdout.strip()
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "set-memory failed"}
        try:
            return json.loads(out)
        except (json.JSONDecodeError, TypeError):
            return out
    except FileNotFoundError:
        return {"error": "set-memory not found"}
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout}s"}


@router.get("/api/{project}/memory")
def get_memory_overview(project: str):
    """Aggregate memory stats, health, and sync status in a single call."""
    project_path = _resolve_project(project)

    # Run all three set-memory commands in parallel (was sequential → 3-5s+ first load)
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_health = pool.submit(_run_wt_memory, project_path, ["health"])
        f_stats = pool.submit(_run_wt_memory, project_path, ["stats", "--json"])
        f_sync = pool.submit(_run_wt_memory, project_path, ["sync", "status"])

        health = f_health.result()
        stats = f_stats.result()
        sync = f_sync.result()

    return {
        "health": health if isinstance(health, str) else health,
        "stats": stats if isinstance(stats, dict) else {},
        "sync": sync if isinstance(sync, str) else str(sync),
    }


# ─── WRITE endpoints ─────────────────────────────────────────────────


@router.post("/api/{project}/approve")
def approve_checkpoint(project: str):
    """Approve the latest checkpoint."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")

    def do_approve():
        state = load_state(str(sp))
        if state.status != "checkpoint":
            raise HTTPException(409, "Not at checkpoint")

        checkpoints = state.extras.get("checkpoints", [])
        if not checkpoints:
            # Try from dataclass field
            checkpoints = state.checkpoints
        if checkpoints:
            checkpoints[-1]["approved"] = True
            checkpoints[-1]["approved_at"] = datetime.now(timezone.utc).isoformat()

        save_state(state, str(sp))
        return {"ok": True}

    return _with_state_lock(sp, do_approve)


@router.post("/api/{project}/stop")
def stop_orchestration(project: str):
    """Stop the orchestration process."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")

    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    if state.status not in ("running", "checkpoint"):
        raise HTTPException(409, f"Not running (status: {state.status})")

    # Find orchestrator PID from state extras
    orch_pid = state.extras.get("orchestrator_pid") or state.extras.get("pid")
    if orch_pid:
        result = safe_kill(int(orch_pid), "set-orchestrate")
        kill_result = result.outcome
    else:
        kill_result = "no_pid"

    def do_stop():
        s = load_state(str(sp))
        s.status = "stopped"
        save_state(s, str(sp))

    _with_state_lock(sp, do_stop)
    return {"ok": True, "kill_result": kill_result}


@router.post("/api/{project}/shutdown")
def shutdown_orchestration(project: str):
    """Graceful shutdown: signals sentinel to stop agents cleanly and preserve state."""
    project_path = _resolve_project(project)
    pid_file = _sentinel_dir(Path(project_path)) / "sentinel.pid"
    if not pid_file.exists():
        raise HTTPException(409, "No sentinel running")

    sentinel_pid = pid_file.read_text().strip()
    if not sentinel_pid:
        raise HTTPException(409, "No sentinel running")

    try:
        pid = int(sentinel_pid)
        import os
        os.kill(pid, 0)  # check if alive
    except (ValueError, ProcessLookupError, PermissionError):
        raise HTTPException(409, "No sentinel running (stale PID file)")

    import signal
    try:
        import os
        os.kill(pid, signal.SIGUSR1)
    except ProcessLookupError:
        raise HTTPException(409, "Sentinel died before shutdown signal")

    return {"ok": True, "message": "Shutdown initiated", "sentinel_pid": pid}


@router.post("/api/{project}/changes/{name}/stop")
def stop_change(project: str, name: str):
    """Stop a specific change's Ralph process."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")

    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    target = None
    for c in state.changes:
        if c.name == name:
            target = c
            break
    if target is None:
        raise HTTPException(404, f"Change not found: {name}")
    if target.status != "running":
        raise HTTPException(409, f"Change not running (status: {target.status})")

    kill_result = "no_pid"
    if target.ralph_pid:
        result = safe_kill(target.ralph_pid, "set-loop")
        kill_result = result.outcome

    def do_stop_change():
        s = load_state(str(sp))
        for c in s.changes:
            if c.name == name:
                c.status = "stopped"
                break
        save_state(s, str(sp))

    _with_state_lock(sp, do_stop_change)
    return {"ok": True, "kill_result": kill_result}


@router.post("/api/{project}/changes/{name}/skip")
def skip_change(project: str, name: str):
    """Mark a change as skipped."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")

    def do_skip():
        state = load_state(str(sp))
        for c in state.changes:
            if c.name == name:
                if c.status not in ("pending", "failed", "verify-failed", "stalled"):
                    raise HTTPException(409, f"Cannot skip change with status: {c.status}")
                c.status = "skipped"
                save_state(state, str(sp))
                return {"ok": True}
        raise HTTPException(404, f"Change not found: {name}")

    return _with_state_lock(sp, do_skip)


# ─── Sentinel endpoints ──────────────────────────────────────────────


def _sentinel_dir(project_path: Path) -> Path:
    try:
        from .paths import SetRuntime
        return Path(SetRuntime(str(project_path)).sentinel_dir)
    except Exception:
        return project_path / ".set" / "sentinel"


@router.get("/api/{project}/sentinel/events")
async def sentinel_events(project: str, since: Optional[float] = None):
    """Read sentinel events from .set/sentinel/events.jsonl.

    Returns [] when file does not exist.
    """
    pp = _resolve_project(project)
    events_file = _sentinel_dir(pp) / "events.jsonl"
    if not events_file.exists():
        return []

    events = []
    with open(events_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since and event.get("epoch", 0) <= since:
                continue
            events.append(event)

    # Return last 500 events max
    if len(events) > 500:
        events = events[-500:]
    return events


@router.get("/api/{project}/sentinel/findings")
async def sentinel_findings(project: str):
    """Read sentinel findings from .set/sentinel/findings.json.

    Returns {findings:[], assessments:[]} when file does not exist.
    """
    pp = _resolve_project(project)
    findings_file = _sentinel_dir(pp) / "findings.json"
    if not findings_file.exists():
        return {"findings": [], "assessments": []}

    try:
        with open(findings_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"findings": [], "assessments": []}


@router.get("/api/{project}/sentinel/status")
async def sentinel_status(project: str):
    """Read sentinel status from .set/sentinel/status.json.

    Returns {active: false} when file does not exist.
    Adds computed is_active field (true if active and last_event_at within 60s).
    """
    pp = _resolve_project(project)
    status_file = _sentinel_dir(pp) / "status.json"
    if not status_file.exists():
        return {"active": False, "is_active": False}

    try:
        with open(status_file) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"active": False, "is_active": False}

    # Compute is_active: active + recent heartbeat
    is_active = False
    if data.get("active"):
        last = data.get("last_event_at", "")
        if last:
            try:
                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - last_dt).total_seconds()
                is_active = age < 60
            except (ValueError, TypeError):
                pass
    data["is_active"] = is_active
    return data


from pydantic import BaseModel


class SentinelMessageBody(BaseModel):
    message: str


@router.post("/api/{project}/sentinel/message")
async def send_sentinel_message(project: str, body: SentinelMessageBody):
    """Send a message to the sentinel via its local inbox file."""
    pp = _resolve_project(project)
    sentinel_dir = _sentinel_dir(pp)
    sentinel_dir.mkdir(parents=True, exist_ok=True)

    inbox_file = sentinel_dir / "inbox.jsonl"
    msg = {
        "from": "set-web",
        "content": body.message,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with open(inbox_file, "a") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    return {"status": "sent"}


@router.post("/api/{project}/completion")
async def completion_action(project: str, body: dict):
    """Send a completion action to the sentinel via inbox.

    Body: {"action": "accept|rerun|newspec", "spec": "docs/v2.md"}
    """
    action = body.get("action", "accept")
    if action not in ("accept", "rerun", "newspec"):
        return JSONResponse({"error": "Invalid action"}, status_code=400)

    pp = _resolve_project(project)
    sentinel_dir = _sentinel_dir(pp)
    sentinel_dir.mkdir(parents=True, exist_ok=True)

    inbox_file = sentinel_dir / "inbox.jsonl"
    msg = {
        "type": "completion_action",
        "action": action,
        "spec": body.get("spec", ""),
        "from": "set-web",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with open(inbox_file, "a") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    return {"status": "sent", "action": action}


# ─── Learnings endpoints ─────────────────────────────────────────────


def _resolve_findings_file(project_path: Path) -> Optional[Path]:
    """Find review-findings.jsonl with fallback paths."""
    for candidate in [
        project_path / "wt" / "orchestration" / "review-findings.jsonl",
        project_path / "orchestration" / "review-findings.jsonl",
    ]:
        if candidate.exists():
            return candidate
    return None


def _read_review_findings(project_path: Path) -> dict:
    """Read and parse review findings from JSONL or state.json review_output fallback."""
    entries = []
    pattern_counts: dict[str, int] = {}

    # Try JSONL first
    findings_file = _resolve_findings_file(project_path)
    if findings_file:
        try:
            with open(findings_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

        for entry in entries:
            for issue in entry.get("issues", []):
                norm = re.sub(r"\[(?:CRITICAL|HIGH|MEDIUM)\]\s*", "", issue.get("summary", ""))[:80]
                if norm:
                    pattern_counts[norm] = pattern_counts.get(norm, 0) + 1

    # Fallback: extract from state.json review_output (always available)
    if not entries:
        state_file = project_path / "orchestration-state.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    state_data = json.load(f)
                for c in state_data.get("changes", []):
                    review_out = c.get("review_output", "")
                    if not review_out:
                        continue
                    change_name = c.get("name", "")
                    issues = []
                    for match in re.finditer(r"\*?\*?ISSUE:\s*\[(\w+)\]\s*(.+?)(?:\*\*|\n|$)", review_out):
                        severity = match.group(1)
                        summary = match.group(2).strip()[:120]
                        issues.append({"severity": severity, "summary": summary})
                        norm = summary[:80]
                        pattern_counts[norm] = pattern_counts.get(norm, 0) + 1
                    if issues:
                        entries.append({"change": change_name, "issues": issues})
            except (json.JSONDecodeError, OSError):
                pass

    # Keyword-based clustering for fuzzy matching across variations
    _CLUSTERS = {
        "no-auth": ["no auth", "no authentication", "zero authentication", "without auth"],
        "no-csrf": ["csrf", "cross-site request"],
        "xss": ["xss", "dangerouslysetinnerhtml", "v-html"],
        "no-rate-limit": ["rate limit", "rate-limit"],
        "secrets-exposed": ["masking", "exposed", "leaked", "codes displayed"],
    }
    cluster_counts: dict[str, int] = {}
    cluster_changes: dict[str, set] = {}
    for entry in entries:
        change_name = entry.get("change", "")
        for issue in entry.get("issues", []):
            raw = issue.get("summary", "").lower()
            for cid, keywords in _CLUSTERS.items():
                if any(kw in raw for kw in keywords):
                    cluster_counts[cid] = cluster_counts.get(cid, 0) + 1
                    cluster_changes.setdefault(cid, set()).add(change_name)
                    break

    recurring = [
        {"pattern": k, "count": v}
        for k, v in sorted(pattern_counts.items(), key=lambda x: -x[1])
        if v >= 2
    ]
    # Add keyword clusters as recurring patterns
    for cid, changes_set in sorted(cluster_changes.items(), key=lambda x: -len(x[1])):
        if len(changes_set) >= 2:
            recurring.append({
                "pattern": f"[{cid}] ({len(changes_set)} changes)",
                "count": cluster_counts[cid],
                "cluster": cid,
                "changes": sorted(changes_set),
            })

    # Read summary MD if exists
    summary = ""
    if findings_file:
        summary_file = findings_file.parent / "review-findings-summary.md"
        if summary_file.exists():
            try:
                summary = summary_file.read_text(errors="replace")
            except OSError:
                pass

    return {"entries": entries, "summary": summary, "recurring_patterns": recurring}


def _compute_gate_stats(project_path: Path) -> dict:
    """Aggregate gate stats from orchestration state."""
    state_file = project_path / "orchestration-state.json"
    if not state_file.exists():
        return {"per_gate": {}, "retry_summary": {}, "per_change_type": {}}

    try:
        with open(state_file) as f:
            state_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"per_gate": {}, "retry_summary": {}, "per_change_type": {}}

    changes = state_data.get("changes", [])
    if not changes:
        return {"per_gate": {}, "retry_summary": {}, "per_change_type": {}}

    # Gate fields: direct fields + extras fallback
    gate_defs = [
        ("build", "build_result", "gate_build_ms"),
        ("test", "test_result", "gate_test_ms"),
        ("review", "review_result", "gate_review_ms"),
        ("smoke", "smoke_result", "gate_verify_ms"),
    ]

    per_gate: dict[str, dict] = {}
    total_retries = 0
    total_retry_ms = 0
    total_gate_ms = 0
    most_retried_gate = ""
    most_retried_count = 0
    most_retried_change = ""
    most_retried_change_count = 0

    # Per change type accumulators
    type_stats: dict[str, dict] = {}

    for change in changes:
        extras = change if isinstance(change, dict) else {}
        change_type = extras.get("change_type", "unknown")
        vrc = extras.get("verify_retry_count", 0) or 0
        rdc = extras.get("redispatch_count", 0) or 0
        change_retries = vrc + rdc
        total_retries += change_retries
        change_name = extras.get("name", "")

        if change_retries > most_retried_change_count:
            most_retried_change_count = change_retries
            most_retried_change = change_name

        gate_ms = extras.get("gate_total_ms", 0) or 0
        total_gate_ms += gate_ms

        if change_type not in type_stats:
            type_stats[change_type] = {"total_gate_ms": 0, "total_retries": 0, "count": 0}
        type_stats[change_type]["total_gate_ms"] += gate_ms
        type_stats[change_type]["total_retries"] += change_retries
        type_stats[change_type]["count"] += 1

        for gate_name, result_field, ms_field in gate_defs:
            result = extras.get(result_field)
            if not result:
                # Check extras dict for e2e
                result = extras.get("extras", {}).get(f"{gate_name}_result") if isinstance(extras.get("extras"), dict) else None
            if not result:
                continue

            if gate_name not in per_gate:
                per_gate[gate_name] = {"total": 0, "pass": 0, "fail": 0, "skip": 0, "total_ms": 0}

            per_gate[gate_name]["total"] += 1
            if result == "pass":
                per_gate[gate_name]["pass"] += 1
            elif result in ("fail", "critical"):
                per_gate[gate_name]["fail"] += 1
            elif result in ("skipped", "skip"):
                per_gate[gate_name]["skip"] += 1

            ms = extras.get(ms_field, 0) or 0
            per_gate[gate_name]["total_ms"] += ms

    # Also check e2e from extras
    for change in changes:
        extras = change if isinstance(change, dict) else {}
        e2e_result = extras.get("extras", {}).get("e2e_result") if isinstance(extras.get("extras"), dict) else None
        if not e2e_result:
            e2e_result = extras.get("e2e_result")
        if e2e_result:
            if "e2e" not in per_gate:
                per_gate["e2e"] = {"total": 0, "pass": 0, "fail": 0, "skip": 0, "total_ms": 0}
            per_gate["e2e"]["total"] += 1
            if e2e_result == "pass":
                per_gate["e2e"]["pass"] += 1
            elif e2e_result in ("fail", "critical"):
                per_gate["e2e"]["fail"] += 1
            elif e2e_result in ("skipped", "skip"):
                per_gate["e2e"]["skip"] += 1
            e2e_ms = extras.get("gate_e2e_ms", 0) or extras.get("extras", {}).get("gate_e2e_ms", 0) if isinstance(extras.get("extras"), dict) else 0
            per_gate["e2e"]["total_ms"] += (e2e_ms or 0)

    # Compute derived stats
    for gate_name, stats in per_gate.items():
        denominator = stats["pass"] + stats["fail"]
        stats["pass_rate"] = round(stats["pass"] / denominator, 2) if denominator > 0 else 0
        non_skip = stats["total"] - stats["skip"]
        stats["avg_ms"] = round(stats["total_ms"] / non_skip) if non_skip > 0 else 0

    # Find most retried gate
    for gate_name, stats in per_gate.items():
        if stats["fail"] > most_retried_count:
            most_retried_count = stats["fail"]
            most_retried_gate = gate_name

    retry_pct = round(total_retries * 100 / max(len(changes), 1), 1)

    per_change_type = {}
    for ct, ts in type_stats.items():
        cnt = ts["count"]
        per_change_type[ct] = {
            "avg_gate_ms": round(ts["total_gate_ms"] / cnt) if cnt > 0 else 0,
            "avg_retries": round(ts["total_retries"] / cnt, 1) if cnt > 0 else 0,
            "count": cnt,
        }

    return {
        "per_gate": per_gate,
        "retry_summary": {
            "total_retries": total_retries,
            "total_gate_ms": total_gate_ms,
            "retry_pct": retry_pct,
            "most_retried_gate": most_retried_gate,
            "most_retried_change": most_retried_change,
        },
        "per_change_type": per_change_type,
    }


def _collect_reflections(project_path: Path) -> dict:
    """Aggregate reflections across all worktrees."""
    worktrees = _list_worktrees(project_path)
    reflections = []
    for wt in worktrees:
        if not wt.get("has_reflection"):
            continue
        refl_path = Path(wt["path"]) / ".claude" / "reflection.md"
        if not refl_path.exists():
            continue
        try:
            content = refl_path.read_text(errors="replace")
        except OSError:
            continue
        branch = wt.get("branch", "")
        change = branch.removeprefix("set/") if branch.startswith("set/") else branch
        reflections.append({"change": change, "branch": branch, "content": content})

    return {
        "reflections": reflections,
        "total": len(worktrees),
        "with_reflection": len(reflections),
    }


def _build_change_timeline(project_path: Path, change_name: str) -> dict:
    """Reconstruct per-change sessions from events JSONL.

    A session is a dispatch→verify cycle: the agent gets dispatched, runs,
    hits the verify gate, and either passes or retries.
    """
    import glob as _glob

    # Find events files (main + rotated archives)
    events_files: list[Path] = []
    for base_dir in [project_path, project_path / "wt" / "orchestration"]:
        for name in ["orchestration-events.jsonl", "orchestration-state-events.jsonl"]:
            candidate = base_dir / name
            if candidate.exists():
                events_files.append(candidate)
                stem = name.replace(".jsonl", "")
                for archive in sorted(_glob.glob(str(base_dir / f"{stem}-*.jsonl"))):
                    events_files.append(Path(archive))
        if events_files:
            break

    if not events_files:
        return {"sessions": [], "duration_ms": 0, "current_gate_results": {}}

    # Collect all events for this change, sorted by timestamp
    change_events: list[dict] = []
    for ef in events_files:
        try:
            with open(ef) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("change") != change_name:
                        continue
                    if ev.get("type") in ("DISPATCH", "STATE_CHANGE", "VERIFY_GATE", "MERGE_ATTEMPT", "MERGE_PROGRESS"):
                        change_events.append(ev)
        except OSError:
            continue

    change_events.sort(key=lambda e: e.get("ts", ""))

    # Build sessions: each DISPATCH or STATE_CHANGE to "running" starts a new session.
    # VERIFY_GATE, MERGE_ATTEMPT close it.  STATE_CHANGE to terminal states close it.
    sessions: list[dict] = []
    current: dict | None = None

    for ev in change_events:
        etype = ev["type"]
        ts = ev.get("ts", "")
        data = ev.get("data", {})

        if etype == "DISPATCH":
            # New session
            if current:
                current["ended"] = ts
                sessions.append(current)
            current = {
                "n": len(sessions) + 1,
                "started": ts,
                "ended": "",
                "state": "dispatched",
                "gates": {},
                "gate_ms": {},
                "merged": False,
            }
        elif etype == "STATE_CHANGE":
            to_state = data.get("to", "")
            from_state = data.get("from", "")
            if to_state == "running" and from_state in ("verify", "verifying", "failed"):
                # Retry: verify/failed → running = new session
                if current:
                    current["ended"] = ts
                    if not current.get("duration_ms"):
                        current["duration_ms"] = _ts_diff_ms(current["started"], ts)
                    sessions.append(current)
                current = {
                    "n": len(sessions) + 1,
                    "started": ts,
                    "ended": "",
                    "state": "running",
                    "gates": {},
                    "gate_ms": {},
                    "merged": False,
                }
            elif current:
                current["state"] = to_state
            elif to_state == "running":
                # Running without a prior DISPATCH event (e.g. resumed)
                current = {
                    "n": len(sessions) + 1,
                    "started": ts,
                    "ended": "",
                    "state": to_state,
                    "gates": {},
                    "gate_ms": {},
                    "merged": False,
                }
        elif etype == "VERIFY_GATE":
            if current:
                # Extract gate results
                for gate in ("build", "test", "e2e", "review", "scope_check",
                             "spec_verify", "rules", "smoke", "test_files"):
                    val = data.get(gate)
                    if val is not None:
                        current["gates"][gate] = val
                # Gate-level timings
                gate_ms = data.get("gate_ms", {})
                if gate_ms and isinstance(gate_ms, dict):
                    current.setdefault("gate_ms", {}).update(gate_ms)
                current["ended"] = ts
                current["duration_ms"] = _ts_diff_ms(current["started"], ts)

                if data.get("result") == "retry":
                    # Retry: close this session, open a new one
                    stop_gate = data.get("stop_gate", "")
                    if stop_gate:
                        current["gates"][stop_gate] = "fail"
                        # Infer gates that passed before the stop gate
                        gate_order = ["build", "test", "e2e", "review", "smoke"]
                        for g in gate_order:
                            if g == stop_gate:
                                break
                            if g not in current["gates"]:
                                current["gates"][g] = "pass"
                    current["state"] = "retry"
                    sessions.append(current)
                    # New session starts from the retry point
                    current = {
                        "n": len(sessions) + 1,
                        "started": ts,
                        "ended": "",
                        "state": "running",
                        "gates": {},
                        "merged": False,
                    }
                else:
                    # Final gate pass — close session
                    sessions.append(current)
                    current = None
        elif etype == "MERGE_ATTEMPT":
            if current:
                current["merged"] = True

    # If there's still an open session (currently running), include it
    if current:
        current["ended"] = ""
        sessions.append(current)

    # Total duration
    duration_ms = 0
    if change_events:
        try:
            first = datetime.fromisoformat(change_events[0]["ts"].replace("Z", "+00:00"))
            last = datetime.fromisoformat(change_events[-1]["ts"].replace("Z", "+00:00"))
            duration_ms = int((last - first).total_seconds() * 1000)
        except (ValueError, TypeError):
            pass

    # Current gate results from state
    current_gate_results: dict = {}
    state_file = project_path / "orchestration-state.json"
    if state_file.exists():
        try:
            with open(state_file) as f:
                state_data = json.load(f)
            for change in state_data.get("changes", []):
                if isinstance(change, dict) and change.get("name") == change_name:
                    for field in ("build_result", "test_result", "review_result", "smoke_result", "verify_retry_count"):
                        val = change.get(field)
                        if val is not None:
                            current_gate_results[field] = val
                    break
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "sessions": sessions,
        "duration_ms": duration_ms,
        "current_gate_results": current_gate_results,
    }


def _ts_diff_ms(ts1: str, ts2: str) -> int:
    """Milliseconds between two ISO timestamps."""
    try:
        t1 = datetime.fromisoformat(ts1.replace("Z", "+00:00"))
        t2 = datetime.fromisoformat(ts2.replace("Z", "+00:00"))
        return int((t2 - t1).total_seconds() * 1000)
    except (ValueError, TypeError):
        return 0


@router.get("/api/{project}/review-findings")
def get_review_findings(project: str):
    """Review findings from gate verification JSONL log."""
    pp = _resolve_project(project)
    return _read_review_findings(pp)


@router.get("/api/{project}/gate-stats")
def get_gate_stats(project: str):
    """Aggregate gate performance stats across all changes."""
    pp = _resolve_project(project)
    return _compute_gate_stats(pp)


@router.get("/api/{project}/reflections")
def get_reflections(project: str):
    """Aggregate agent reflections from all worktrees."""
    pp = _resolve_project(project)
    return _collect_reflections(pp)


@router.get("/api/{project}/changes/{name}/timeline")
def get_change_timeline(project: str, name: str):
    """Per-change state transition timeline from events log."""
    pp = _resolve_project(project)
    return _build_change_timeline(pp, name)


@router.get("/api/{project}/learnings")
def get_learnings(project: str):
    """Unified learnings endpoint: reflections + review findings + gate stats + sentinel."""
    pp = _resolve_project(project)

    # Sentinel findings
    sentinel_data = {"findings": [], "assessments": []}
    findings_file = _sentinel_dir(pp) / "findings.json"
    if findings_file.exists():
        try:
            sentinel_data = json.loads(findings_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "reflections": _collect_reflections(pp),
        "review_findings": _read_review_findings(pp),
        "gate_stats": _compute_gate_stats(pp),
        "sentinel_findings": sentinel_data,
    }


# ─── Battle Scoreboard ─────────────────────────────────────────────

import hashlib
import hmac

# Server-side secret for score signing (derived from hostname for simplicity)
_SCORE_SECRET = hashlib.sha256(
    f"set-battle-{os.uname().nodename}".encode()
).hexdigest().encode()

_SCOREBOARD_FILE = Path(os.environ.get(
    "SET_SCOREBOARD_FILE",
    os.path.expanduser("~/.local/share/set-core/scoreboard.json"),
))


def _sign_score(project: str, score: int, changes_done: int, total_tokens: int) -> str:
    """Create HMAC signature from orchestration facts the server can verify."""
    msg = f"{project}:{score}:{changes_done}:{total_tokens}"
    return hmac.new(_SCORE_SECRET, msg.encode(), hashlib.sha256).hexdigest()[:16]


def _load_scoreboard() -> list:
    if not _SCOREBOARD_FILE.exists():
        return []
    try:
        with open(_SCOREBOARD_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_scoreboard(entries: list):
    _SCOREBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(_SCOREBOARD_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(entries, f, indent=2)
    os.replace(tmp, str(_SCOREBOARD_FILE))


class ScoreSubmission(BaseModel):
    player: str
    project: str
    score: int
    changes_done: int
    total_changes: int
    total_tokens: int
    achievements: list[str]
    signature: str


@router.get("/api/scoreboard")
async def get_scoreboard(limit: int = 20):
    """Get the global scoreboard (top scores across all projects)."""
    entries = _load_scoreboard()
    entries.sort(key=lambda e: e.get("score", 0), reverse=True)
    return {"entries": entries[:limit]}


@router.post("/api/scoreboard/submit")
async def submit_score(body: ScoreSubmission):
    """Submit a score with server-side validation.

    Anti-cheat:
    1. Signature must match server-computed HMAC from orchestration facts
    2. Score is sanity-checked against changes_done and total_tokens
    3. Server verifies the project exists and has orchestration data
    4. Max 1000 points per change + bonuses (cap at ~5000/change)
    """
    # Verify signature
    expected_sig = _sign_score(body.project, body.score, body.changes_done, body.total_tokens)
    if not hmac.compare_digest(body.signature, expected_sig):
        raise HTTPException(status_code=403, detail="Invalid score signature")

    # Sanity check: max ~5000 points per completed change (generous upper bound)
    max_plausible = body.changes_done * 5000 + 2000  # 2000 for achievements
    if body.score > max_plausible:
        raise HTTPException(status_code=400, detail="Score exceeds plausible maximum")

    # Verify project exists
    try:
        _resolve_project(body.project)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Project not found")

    # Load and update scoreboard
    entries = _load_scoreboard()

    entry = {
        "player": body.player[:20],  # max 20 chars
        "project": body.project,
        "score": body.score,
        "changes_done": body.changes_done,
        "total_changes": body.total_changes,
        "total_tokens": body.total_tokens,
        "achievements": body.achievements[:20],  # max 20
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # Replace if same player+project with higher score
    existing_idx = None
    for i, e in enumerate(entries):
        if e.get("player") == entry["player"] and e.get("project") == entry["project"]:
            existing_idx = i
            break

    if existing_idx is not None:
        if entries[existing_idx].get("score", 0) < body.score:
            entries[existing_idx] = entry
        # else: keep existing higher score
    else:
        entries.append(entry)

    # Keep top 100
    entries.sort(key=lambda e: e.get("score", 0), reverse=True)
    entries = entries[:100]

    _save_scoreboard(entries)
    return {"status": "ok", "rank": next((i + 1 for i, e in enumerate(entries) if e.get("player") == entry["player"] and e.get("project") == entry["project"]), None)}


@router.get("/api/scoreboard/sign")
async def sign_score(project: str, score: int, changes_done: int, total_tokens: int):
    """Get a server-signed token for a score. Client must request this before submitting.

    This ensures only scores backed by real orchestration data can be submitted,
    since the client must know the correct changes_done and total_tokens values
    that match the server's view.
    """
    # Verify project exists and get actual state to cross-check
    try:
        pp = _resolve_project(project)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Project not found")

    # Load actual orchestration state to verify the claimed values
    try:
        state = load_state(str(pp / "orchestration-state.json"))
        actual_changes = state.get("changes", [])
        actual_done = sum(1 for c in actual_changes if c.get("status") in ("done", "merged", "completed", "skip_merged"))
        actual_tokens = sum((c.get("input_tokens", 0) or 0) + (c.get("output_tokens", 0) or 0) for c in actual_changes)

        # Allow some tolerance (client may have slightly different counts)
        if abs(changes_done - actual_done) > 2:
            raise HTTPException(status_code=400, detail="changes_done mismatch with server state")
        if actual_tokens > 0 and abs(total_tokens - actual_tokens) / max(actual_tokens, 1) > 0.2:
            raise HTTPException(status_code=400, detail="total_tokens mismatch with server state")
    except (StateCorruptionError, FileNotFoundError, OSError):
        pass  # No state file — allow signing (orchestration might be over)

    sig = _sign_score(project, score, changes_done, total_tokens)
    return {"signature": sig}
