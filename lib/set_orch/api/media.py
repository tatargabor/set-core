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

@router.get("/api/{project}/changes/{name}/screenshots")
def get_change_screenshots(project: str, name: str):
    """List test artifacts for a change (screenshots, traces, reports)."""
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
            # Try profile-collected artifacts first
            artifacts = c.extras.get("test_artifacts")
            if artifacts:
                return {"artifacts": artifacts, "smoke": [], "e2e": [
                    a for a in artifacts if a.get("type") == "image"
                ]}

            # Fallback: live scan from worktree (if no cached artifacts)
            wt_path = c.worktree_path
            if wt_path and os.path.isdir(wt_path):
                try:
                    from ..profile_loader import load_profile
                    profile = load_profile(wt_path)
                    artifacts = profile.collect_test_artifacts(wt_path)
                    if artifacts:
                        # Cache for next request
                        from ..state import locked_state
                        with locked_state(str(sp)) as _st:
                            _ch = next((x for x in _st.changes if x.name == name), None)
                            if _ch:
                                _ch.extras["test_artifacts"] = artifacts
                                images = [a for a in artifacts if a.get("type") == "image"]
                                _ch.extras["e2e_screenshot_count"] = len(images)
                        return {"artifacts": artifacts, "smoke": [], "e2e": [
                            a for a in artifacts if a.get("type") == "image"
                        ]}
                except Exception:
                    pass

            # Final fallback: legacy screenshot dirs
            result: dict = {"artifacts": [], "smoke": [], "e2e": []}
            e2e_dir = getattr(c, "e2e_screenshot_dir", None) or c.extras.get("e2e_screenshot_dir")
            if e2e_dir:
                ed = Path(e2e_dir) if os.path.isabs(e2e_dir) else project_path / e2e_dir
                if ed.is_dir():
                    for f in sorted(ed.rglob("*.png")):
                        item = {"path": str(f), "name": f.name, "type": "image", "test": f.parent.name}
                        result["e2e"].append(item)
                        result["artifacts"].append(item)
            return result
    raise HTTPException(404, f"Change not found: {name}")


_ALLOWED_EXTENSIONS = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".zip": "application/zip",
    ".json": "application/json",
    ".html": "text/html",
    ".log": "text/plain",
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
    # Security: only serve files within the project repo or its worktrees
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
    if not any(resolved.is_relative_to(root) for root in allowed_roots):
        raise HTTPException(403, "Access denied")
    filename = full_path.name
    return FR(str(full_path), media_type=media_type, filename=filename)

