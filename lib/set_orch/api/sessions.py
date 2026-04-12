"""Session listing, log reading, activity routes."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..state import load_state, StateCorruptionError
from .helpers import (
    _resolve_project,
    _state_path,
    _log_path,
    _read_activity,
    _claude_mangle,
    _extract_session_change_name,
    _PURPOSE_LABELS,
)

router = APIRouter()

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
                    "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).astimezone().isoformat(),
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
                first_line = content.split("\n")[0].strip()

                # PURPOSE tag from run_claude_logged() (highest priority)
                if first_line.startswith("[PURPOSE:"):
                    tag = first_line.split("]")[0].removeprefix("[PURPOSE:")
                    parts = tag.split(":", 1)
                    purpose = parts[0] if parts else ""
                    change = parts[1] if len(parts) > 1 else ""
                    label = _PURPOSE_LABELS.get(purpose, purpose.replace("_", " ").title())
                    full = f"{change}: {label}" if change else label
                    return label, full

                first_line = first_line.lower()

                # Orchestration role patterns (match before generic fallback)
                if "sentinel" in first_line and ("supervisor" in first_line or "orchestration" in first_line):
                    return "Sentinel", "Orchestration supervisor"
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
    """Return the canonical outcome for a Claude session.

    Returns 'success', 'error', or 'unknown'.

    Strict single source of truth: only the `<session_id>.verdict.json`
    sidecar written by the gate that produced this session is considered
    authoritative. Sessions without a sidecar return "unknown" (rendered
    as a neutral gray badge).

    Why no fallback heuristic?
    --------------------------
    Earlier versions of this function ran a keyword scan ("review fail",
    "[critical]", "fixed", "committed", ...) over the last assistant
    message. That heuristic was wrong in both directions:
      - false errors when the prose quoted a previous critical finding
        and the gate had actually decided pass (the original bug — see
        commit 692e6019)
      - false successes when the agent said "fixed" but the next gate
        re-ran and failed
    There is no reliable way to derive a binary verdict from natural
    language without rerunning the LLM verdict classifier — and that
    classifier already runs at gate-decision time and writes a sidecar.

    For Claude sessions that go through `run_claude_logged`, the
    subprocess wrapper writes a default sidecar based on the claude exit
    code so EVERY logged session has at least a coarse pass/fail. Gates
    that produce a richer verdict (review, spec_verify) overwrite the
    default with their canonical outcome. Sessions that bypass
    `run_claude_logged` (legacy ad-hoc calls) stay "unknown" until they
    are migrated.
    """
    try:
        from ..gate_verdict import read_verdict_sidecar
        v = read_verdict_sidecar(session_path)
        if v is not None:
            return v.to_outcome()
    except Exception:
        pass
    return "unknown"


def _extract_session_tokens(path: Path) -> dict:
    """Extract token usage from a JSONL session file."""
    input_tokens = 0
    output_tokens = 0
    cache_read = 0
    cache_create = 0
    try:
        with open(path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "assistant":
                    continue
                usage = entry.get("message", {}).get("usage", {})
                if not usage:
                    continue
                input_tokens += usage.get("input_tokens", 0)
                output_tokens += usage.get("output_tokens", 0)
                cache_read += usage.get("cache_read_input_tokens", 0)
                cache_create += usage.get("cache_creation_input_tokens", 0)
    except OSError:
        pass
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read,
        "cache_create_tokens": cache_create,
    }


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
                tokens = _extract_session_tokens(f)
                files.append({
                    "id": f.stem,
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).astimezone().isoformat(),
                    "label": label,
                    "full_label": full_label,
                    "model": model,
                    "outcome": "active" if is_active else _session_outcome(f),
                    **tokens,
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
    """List all Claude session files across the project and all change worktrees.

    Aggregates sessions from:
    1. Project-level sessions dir (sentinel, planner, digest)
    2. Per-change worktree session dirs (implementation, gate review, etc.)

    Each session entry includes a 'change' field with the change name (or empty
    for project-level sessions).
    """
    project_path = _resolve_project(project)
    seen_ids: set[str] = set()
    all_sessions: list[dict] = []

    # Source 1: Project-level sessions
    proj_mangled = _claude_mangle(str(project_path))
    proj_dir = Path.home() / ".claude" / "projects" / f"-{proj_mangled}"
    if proj_dir.is_dir():
        for entry in _list_session_files(proj_dir):
            seen_ids.add(entry["id"])
            entry["change"] = ""
            all_sessions.append(entry)

    # Source 2: Per-change worktree sessions
    sp = _state_path(project_path)
    if sp.exists():
        try:
            state = load_state(str(sp))
            for change in state.changes:
                if change.worktree_path:
                    mangled = _claude_mangle(change.worktree_path)
                    d = Path.home() / ".claude" / "projects" / f"-{mangled}"
                    if d.is_dir():
                        for entry in _list_session_files(d):
                            if entry["id"] not in seen_ids:
                                seen_ids.add(entry["id"])
                                entry["change"] = change.name
                                all_sessions.append(entry)
        except (StateCorruptionError, Exception):
            pass

    all_sessions.sort(key=lambda x: x["mtime"], reverse=True)
    return {"sessions": all_sessions}


@router.get("/api/{project}/sessions/{session_id}")
def get_project_session(
    project: str, session_id: str,
    tail: int = Query(200, ge=1, le=2000),
):
    """Read a Claude session log (searches project dir + all change worktrees)."""
    project_path = _resolve_project(project)

    # Build list of candidate directories
    dirs: list[Path] = []
    proj_mangled = _claude_mangle(str(project_path))
    proj_dir = Path.home() / ".claude" / "projects" / f"-{proj_mangled}"
    if proj_dir.is_dir():
        dirs.append(proj_dir)
    sp = _state_path(project_path)
    if sp.exists():
        try:
            state = load_state(str(sp))
            for change in state.changes:
                if change.worktree_path:
                    mangled = _claude_mangle(change.worktree_path)
                    d = Path.home() / ".claude" / "projects" / f"-{mangled}"
                    if d.is_dir() and d not in dirs:
                        dirs.append(d)
        except Exception:
            pass

    # Search for the session file in all dirs
    for d in dirs:
        target = d / f"{session_id}.jsonl"
        if target.is_file():
            lines = _parse_session_jsonl(target, tail)
            return {"lines": lines, "session_id": session_id}

    raise HTTPException(404, f"Session not found: {session_id}")


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
