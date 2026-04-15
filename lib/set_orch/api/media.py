"""Media routes: screenshots, worktree logs, reflections, soniox key."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..state import load_state, StateCorruptionError
from .helpers import _resolve_project, _state_path, _list_worktrees

router = APIRouter()

@router.get("/api/soniox-key")
async def get_soniox_key():
    """Return Soniox API key from environment for voice input."""
    key = os.environ.get("SONIOX_API_KEY")
    if not key:
        raise HTTPException(404, "Soniox API key not configured")
    return {"api_key": key}

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

def _classify_artifact(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext == ".png":
        return "image"
    if ext in (".webm", ".mp4"):
        return "video"
    if ext == ".zip":
        return "trace"
    if ext == ".md":
        return "report"
    if ext in (".log", ".txt"):
        return "log"
    return None


def _scan_attempt_dir(root: Path) -> list[dict]:
    """Walk `<root>/attempt-N/**` and return attempt-tagged artifact dicts.

    Two storage layouts both land here:
      (a) modules/web gates.py:588 writes every successful gate run to
          `<runtime>/screenshots/e2e/<change>/attempt-N/<test-dir>/*.png`
      (b) gate_runner._archive_attempt_artifacts writes pre-retry archives to
          `<runtime>/screenshots/attempts/<change>/attempt-N/test-results/...`
    Both use the same `attempt-N/` nesting so this single scanner handles both.
    """
    if not root.is_dir():
        return []
    collected: list[dict] = []
    for attempt_dir in sorted(root.glob("attempt-*")):
        if not attempt_dir.is_dir():
            continue
        try:
            attempt_num = int(attempt_dir.name.removeprefix("attempt-"))
        except ValueError:
            continue
        for f in sorted(attempt_dir.rglob("*")):
            if not f.is_file():
                continue
            kind = _classify_artifact(f)
            if not kind:
                continue
            collected.append({
                "path": str(f),
                "name": f.name,
                "type": kind,
                "test": f.parent.name,
                "attempt": attempt_num,
            })
    return collected


def _scan_archived_attempts(project_path: Path, change_name: str) -> list[dict]:
    """Collect all attempt-tagged artifacts for `change_name`.

    Checks both storage locations:
      1. Pre-retry archive (`attempts/<change>/attempt-N/`)
      2. Per-attempt e2e screenshot dir (`screenshots/e2e/<change>/attempt-N/`)
    """
    items: list[dict] = []
    # Location 1: gate_runner archive (project_path/set/... fallback when
    # SetRuntime isn't available at archive-time).
    items += _scan_attempt_dir(
        project_path / "set" / "orchestration" / "attempts" / change_name
    )
    # Location 2: runtime-resolved per-attempt e2e screenshots (preferred
    # path — this is where modules/web/gates.py writes every e2e gate run).
    try:
        from ..paths import SetRuntime
        rt_screenshots = Path(SetRuntime(str(project_path)).screenshots_dir)
        items += _scan_attempt_dir(rt_screenshots / "e2e" / change_name)
        items += _scan_attempt_dir(rt_screenshots / "attempts" / change_name)
    except Exception:
        pass
    # Location 3: merger's post-merge archive (flat test-results dump, no
    # attempt-N nesting). Only consulted when no per-attempt data exists —
    # this covers older merged changes whose E2E gate ran before the
    # per-attempt runtime-copy logic landed. Treat the whole dump as the
    # final (highest) attempt so the UI groups it alongside newer runs.
    if not items:
        merger_dump = project_path / "set" / "orchestration" / "artifacts" / change_name / "test-results"
        if merger_dump.is_dir():
            for f in sorted(merger_dump.rglob("*")):
                if not f.is_file():
                    continue
                kind = _classify_artifact(f)
                if not kind:
                    continue
                items.append({
                    "path": str(f),
                    "name": f.name,
                    "type": kind,
                    "test": f.parent.name,
                    "attempt": 1,
                })
    # Deduplicate on path — the same file could land in multiple roots if a
    # run was interrupted and resumed.
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        key = item["path"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


@router.get("/api/{project}/changes/{name}/screenshots")
def get_change_screenshots(project: str, name: str):
    """List test artifacts for a change — runtime archive only.

    Reads exclusively from the runtime screenshot archive populated by
    the E2E gate and the pre-retry archive. The worktree's live
    `test-results/` is NEVER served: Playwright overwrites it on every
    run, so paths there go stale the moment the agent re-runs tests.
    If no archived attempts exist yet, returns an empty list — the UI
    should show "no artifacts" until the first E2E gate completes.
    """
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
            archived = _scan_archived_attempts(project_path, name)
            archived.sort(key=lambda x: (x.get("attempt", 0), x.get("name", "")))
            images = [a for a in archived if a.get("type") == "image"]
            return {
                "artifacts": archived,
                "smoke": [],
                "e2e": images,
                "attempts": sorted({a.get("attempt", 0) for a in archived}),
            }
    raise HTTPException(404, f"Change not found: {name}")


_ALLOWED_EXTENSIONS = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".webm": "video/webm",
    ".mp4": "video/mp4",
    ".zip": "application/zip",
    ".json": "application/json",
    ".html": "text/html",
    ".log": "text/plain",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


@router.get("/api/{project}/screenshots/{file_path:path}")
def serve_screenshot(project: str, file_path: str):
    """Serve a test artifact file (screenshot, trace, report)."""
    from fastapi.responses import FileResponse as FR

    if ".." in file_path:
        raise HTTPException(400, "Invalid path")

    # Absolute paths lose their leading "/" when captured by FastAPI's {path:path}
    # parameter (e.g., "/home/tg/..." becomes "home/tg/..."). Restore it.
    if not os.path.isabs(file_path) and file_path.startswith("home/"):
        file_path = "/" + file_path

    full_path = Path(file_path) if os.path.isabs(file_path) else _resolve_project(project) / file_path
    media_type = _ALLOWED_EXTENSIONS.get(full_path.suffix.lower())
    if not full_path.exists() or media_type is None:
        raise HTTPException(404, "Artifact not found")
    # Security: only serve files within the project repo, its worktrees,
    # or the runtime screenshots/logs dir (per-attempt archives live there
    # and outlive the worktrees).
    resolved = full_path.resolve()
    project_path = _resolve_project(project)
    allowed_roots = [project_path.resolve()]
    # Add worktree paths from state
    sp = _state_path(project_path)
    if sp.exists():
        try:
            state = load_state(str(sp))
            for c in state.changes:
                if c.worktree_path:
                    wt = Path(c.worktree_path).resolve()
                    if wt.is_dir():
                        allowed_roots.append(wt)
        except Exception:
            pass
    # Per-attempt archive + runtime screenshot dirs live under
    # ~/.local/share/set-core/runtime/<project>/. Without this whitelist
    # the gallery 403s on every archived attempt's image/md/trace.
    try:
        from ..paths import SetRuntime
        rt_root = Path(SetRuntime(str(project_path)).root)
        if rt_root.is_dir():
            allowed_roots.append(rt_root.resolve())
    except Exception:
        pass
    if not any(resolved.is_relative_to(root) for root in allowed_roots):
        raise HTTPException(403, "Access denied")
    filename = full_path.name
    return FR(str(full_path), media_type=media_type, filename=filename)

