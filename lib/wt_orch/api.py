"""REST API endpoints for the wt-web dashboard.

Read endpoints for projects, orchestration state, changes, worktrees, activity, logs.
Write endpoints for approve, stop, skip.
"""

from __future__ import annotations

import fcntl
import json
import os
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

PROJECTS_FILE = Path.home() / ".config" / "wt-tools" / "projects.json"


def _load_projects() -> list[dict]:
    """Load registered projects from ~/.config/wt-tools/projects.json.

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
    """Find orchestration state file — new location first, legacy fallback."""
    new = project_path / "wt" / "orchestration" / "orchestration-state.json"
    if new.exists():
        return new
    legacy = project_path / "orchestration-state.json"
    if legacy.exists():
        return legacy
    return new  # default for non-existent (will 404 cleanly)


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
    """Find orchestration log — new location first, legacy fallback."""
    new = project_path / "wt" / "orchestration" / "orchestration.log"
    if new.exists():
        return new
    legacy = project_path / "orchestration.log"
    if legacy.exists():
        return legacy
    return new


def _quick_status(project_path: Path) -> str:
    """Get quick orchestration status without full state parse."""
    sp = _state_path(project_path)
    if not sp.exists():
        # No state file yet — check if orchestrator is starting up
        # (sentinel.pid or recent orchestration.log indicate a running orch)
        sentinel_pid = project_path / "sentinel.pid"
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
        loop_state = wt_path / ".claude" / "loop-state.json"
        if loop_state.exists():
            try:
                with open(loop_state) as f:
                    ls = json.load(f)
                wt["iteration"] = ls.get("current_iteration", 0)
                wt["max_iterations"] = ls.get("max_iterations", 0)
            except (json.JSONDecodeError, OSError):
                pass

        # Agent activity
        activity_file = wt_path / ".claude" / "activity.json"
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
    for c in data.get("changes", []):
        wt_path = c.get("worktree_path")
        # Session count (only for changes that have/had a worktree)
        sessions_dir = None
        if wt_path:
            mangled = _claude_mangle(wt_path)
            d = Path.home() / ".claude" / "projects" / f"-{mangled}"
            if d.is_dir():
                sessions_dir = d
            elif c.get("status") in ("done", "merged", "failed", "verify-failed"):
                # Worktree cleaned up, fall back to project path
                mangled = _claude_mangle(str(project_path))
                d = Path.home() / ".claude" / "projects" / f"-{mangled}"
                if d.is_dir():
                    sessions_dir = d
        if sessions_dir:
            try:
                c["session_count"] = sum(
                    1 for f in sessions_dir.iterdir()
                    if f.is_file() and f.suffix == ".jsonl"
                )
            except OSError:
                pass
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
            loop_file = wt_path / ".claude" / "loop-state.json"
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
                loop_file = Path(c.worktree_path) / ".claude" / "loop-state.json"
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
                loop_state = Path(c.worktree_path) / ".claude" / "loop-state.json"
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
                files.append({
                    "id": f.stem,
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                    "label": label,
                    "full_label": full_label,
                    "outcome": _session_outcome(f),
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

    change, sessions_dir = _sessions_dir_for_change(state, name, project_path)
    if change is None:
        raise HTTPException(404, f"Change not found: {name}")
    if not sessions_dir:
        return {"sessions": []}
    return {"sessions": _list_session_files(sessions_dir)}


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

    change, sessions_dir = _sessions_dir_for_change(state, name, project_path)
    if change is None:
        raise HTTPException(404, f"Change not found: {name}")
    if not sessions_dir:
        return {"lines": [], "session_id": None, "sessions": []}

    session_files = _list_session_files(sessions_dir)
    if not session_files:
        return {"lines": [], "session_id": None, "sessions": []}

    # Select target file
    if session_id:
        target = sessions_dir / f"{session_id}.jsonl"
        if not target.is_file():
            raise HTTPException(404, f"Session not found: {session_id}")
    else:
        target = sessions_dir / f"{session_files[0]['id']}.jsonl"

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

    # Prepend start timestamp, append end timestamp
    if first_ts:
        output.insert(0, f"--- session start: {_format_ts(first_ts)} ---")
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
    sentinel_pid_file = project_path / "sentinel.pid"
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
    """Run wt-memory CLI with project-scoped CWD, return parsed JSON or raw string."""
    try:
        result = subprocess.run(
            ["wt-memory"] + args,
            capture_output=True, text=True, timeout=timeout,
            cwd=str(project_path),
        )
        out = result.stdout.strip()
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "wt-memory failed"}
        try:
            return json.loads(out)
        except (json.JSONDecodeError, TypeError):
            return out
    except FileNotFoundError:
        return {"error": "wt-memory not found"}
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout}s"}


@router.get("/api/{project}/memory")
def get_memory_overview(project: str):
    """Aggregate memory stats, health, and sync status in a single call."""
    project_path = _resolve_project(project)

    # Run all three wt-memory commands in parallel (was sequential → 3-5s+ first load)
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
        result = safe_kill(int(orch_pid), "wt-orchestrate")
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
    pid_file = Path(project_path) / "sentinel.pid"
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
        result = safe_kill(target.ralph_pid, "wt-loop")
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
    return project_path / ".wt" / "sentinel"


@router.get("/api/{project}/sentinel/events")
async def sentinel_events(project: str, since: Optional[float] = None):
    """Read sentinel events from .wt/sentinel/events.jsonl.

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
    """Read sentinel findings from .wt/sentinel/findings.json.

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
    """Read sentinel status from .wt/sentinel/status.json.

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
        "from": "wt-web",
        "content": body.message,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with open(inbox_file, "a") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    return {"status": "sent"}
