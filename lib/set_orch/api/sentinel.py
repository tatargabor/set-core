"""Sentinel control routes — ported from manager/api.py (aiohttp → FastAPI).

Routes:
    POST /api/{project}/sentinel/start
    POST /api/{project}/sentinel/stop
    POST /api/{project}/sentinel/restart
    GET  /api/{project}/sentinel/log
    GET  /api/{project}/docs
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()

# Service reference — set by lifecycle.py at startup
_service = None


def set_service(service):
    """Called by lifecycle.py to inject the service manager."""
    global _service
    _service = service


def _get_supervisor(project: str):
    if not _service:
        raise HTTPException(503, "Service not initialized")
    sup = _service.supervisors.get(project)
    if not sup:
        raise HTTPException(404, f"Project '{project}' not found")
    return sup


def _last_spec_path(project_path: Path) -> str | None:
    """Read last-used spec path from sentinel marker file."""
    marker = project_path / "set" / "orchestration" / ".sentinel-spec"
    if marker.is_file():
        return marker.read_text().strip() or None
    return None


def _save_spec_path(project_path: Path, spec: str):
    """Persist spec path for future restarts."""
    marker = project_path / "set" / "orchestration" / ".sentinel-spec"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(spec)


@router.post("/api/{project}/sentinel/start")
async def sentinel_start(project: str, body: dict = {}):
    sup = _get_supervisor(project)
    spec = body.get("spec")
    # Fall back to last-used spec if none provided
    if not spec:
        spec = _last_spec_path(Path(sup.config.path))
        if spec:
            logger.info("Sentinel start: using last spec path '%s'", spec)
    if not spec:
        raise HTTPException(400, "No spec provided and no previous spec found. Pass {\"spec\": \"docs/spec.md\"}")
    _save_spec_path(Path(sup.config.path), spec)

    reset_failed = bool(body.get("reset_failed", False))
    reset_names: list[str] = []
    if reset_failed:
        try:
            from ..engine import reset_failed_changes
            from ..paths import LineagePaths as _LP_sstart
            state_file = _LP_sstart(str(sup.config.path)).state_file
            if Path(state_file).is_file():
                reset_names = reset_failed_changes(state_file)
                logger.info(
                    "sentinel_start: reset_failed=true, reset %d change(s): %s",
                    len(reset_names), ", ".join(reset_names) or "<none>",
                )
            else:
                logger.warning("sentinel_start: reset_failed=true but no state file at %s", state_file)
        except Exception as exc:
            logger.error("sentinel_start: reset_failed_changes raised: %s", exc, exc_info=True)
            raise HTTPException(500, f"reset_failed_changes failed: {exc}")

    pid = sup.start_sentinel(spec=spec)
    response: dict = {"status": "ok", "pid": pid, "spec": spec}
    if reset_failed:
        response["reset_failed_changes"] = reset_names
    return response


@router.post("/api/{project}/sentinel/stop")
async def sentinel_stop(project: str):
    sup = _get_supervisor(project)
    sup.stop_sentinel()
    return {"status": "ok"}


@router.post("/api/{project}/sentinel/restart")
async def sentinel_restart(project: str, body: dict = {}):
    sup = _get_supervisor(project)
    sup.stop_sentinel()
    spec = body.get("spec")
    if not spec:
        spec = _last_spec_path(Path(sup.config.path))
    if not spec:
        raise HTTPException(400, "No spec provided and no previous spec found")
    _save_spec_path(Path(sup.config.path), spec)
    pid = sup.start_sentinel(spec=spec)
    return {"status": "ok", "pid": pid, "spec": spec}


@router.get("/api/{project}/sentinel/log")
async def sentinel_log(project: str, tail: int = 200, raw: str = ""):
    """Return last N lines of sentinel stdout.log, parsing stream-json format.

    Source priority:
      1. stdout.log if it has content
      2. stderr.log fallback — Python supervisor daemons started before
         the bin/set-supervisor stdout-redirect fix wrote their logs to
         stderr. Falling back here lets the dashboard show those runs
         too without forcing a daemon restart.
    """
    sup = _get_supervisor(project)
    try:
        from ..paths import SetRuntime
        rt = SetRuntime(str(sup.config.path))
        log_path = Path(rt.sentinel_dir) / "stdout.log"
        if not log_path.exists() or log_path.stat().st_size == 0:
            stderr_path = Path(rt.sentinel_dir) / "stderr.log"
            if stderr_path.exists() and stderr_path.stat().st_size > 0:
                log_path = stderr_path
            else:
                return {"lines": []}
        content = log_path.read_text()
        if raw:
            lines = content.splitlines()[-tail:]
            return {"lines": lines}
        # Parse stream-json: extract assistant text content
        output_lines: list[str] = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                etype = event.get("type", "")
                if etype == "assistant" and "message" in event:
                    for block in event["message"].get("content", []):
                        if block.get("type") == "text":
                            output_lines.extend(block["text"].splitlines())
                elif etype == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        output_lines.append(delta.get("text", ""))
                elif etype == "result":
                    for block in event.get("content", []):
                        if block.get("type") == "text":
                            output_lines.extend(block["text"].splitlines())
            except (json.JSONDecodeError, KeyError, TypeError):
                output_lines.append(line)
        return {"lines": output_lines[-tail:]}
    except Exception:
        return {"lines": []}


@router.get("/api/{project}/docs")
async def list_docs(project: str):
    """List docs directory for spec autocomplete."""
    sup = _get_supervisor(project)
    docs_dir = sup.config.path / "docs"
    entries: list[dict] = []
    if docs_dir.is_dir():
        for root, dirs, files in os.walk(docs_dir):
            depth = len(Path(root).relative_to(docs_dir).parts)
            if depth >= 2:
                dirs.clear()
                continue
            rel = Path(root).relative_to(sup.config.path)
            for d in sorted(dirs):
                entries.append({"path": str(rel / d) + "/", "type": "dir"})
            for f in sorted(files):
                entries.append({"path": str(rel / f), "type": "file"})
    return {"docs": entries}
