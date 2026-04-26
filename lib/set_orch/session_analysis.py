"""Post-session analysis of Claude Code session JSONL files.

Each ``claude`` invocation produces one JSONL log at
``~/.claude/projects/{cwd-encoded}/{session-id}.jsonl``. The orchestrator
runs many sessions per change (one per Ralph iteration), all under the
worktree directory. This module aggregates across all session files for
a given worktree to surface waste signals the dashboard can show.

Currently extracts:
  - Duplicate file reads — same path Read N>1 times in a single session.
    Each repeat re-injects the file content into the conversation
    prefix and inflates cache_read. Witnessed in
    micro-web-run-20260426-1704 contact-wizard-form: the agent read
    ``v0-export/components/contact-wizard.tsx`` (12K) twice in one
    session = +12K of pure cache-read multiplier × ~50 turns × cost.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _encode_cwd_to_session_dir(cwd: str) -> str:
    """Replicate Claude Code's directory-encoding for project session dirs.

    Format: replace ``/`` and ``.`` with ``-``. Examples:
      ``/home/tg/.local/foo``         → ``-home-tg--local-foo``
      ``/home/tg/code/set-core``      → ``-home-tg-code-set-core``
    """
    return cwd.replace("/", "-").replace(".", "-")


def _session_files_for_worktree(wt_path: str) -> list[Path]:
    """All session JSONL files under ``~/.claude/projects/`` whose
    encoded-cwd matches the worktree path."""
    cwd_enc = _encode_cwd_to_session_dir(wt_path.rstrip("/"))
    sessions_dir = Path.home() / ".claude" / "projects" / cwd_enc
    if not sessions_dir.is_dir():
        return []
    return [p for p in sessions_dir.glob("*.jsonl") if p.is_file()]


def detect_duplicate_reads(wt_path: str) -> dict[str, int]:
    """Walk all session JSONL files for a worktree and count Read calls
    per file path. Returns ``{path: count}`` for paths read >1 times,
    aggregated across all sessions of that worktree.

    Empty dict on missing sessions / unreadable files.
    """
    files = _session_files_for_worktree(wt_path)
    if not files:
        return {}

    read_counts: dict[str, int] = {}
    for sess_file in files:
        try:
            with sess_file.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if e.get("type") != "assistant":
                        continue
                    msg = e.get("message", {})
                    content = msg.get("content", [])
                    if not isinstance(content, list):
                        continue
                    for c in content:
                        if not isinstance(c, dict):
                            continue
                        if c.get("type") != "tool_use":
                            continue
                        if c.get("name") != "Read":
                            continue
                        path = c.get("input", {}).get("file_path", "")
                        if path:
                            read_counts[path] = read_counts.get(path, 0) + 1
        except OSError:
            logger.debug("session file unreadable: %s", sess_file, exc_info=True)
            continue

    duplicates = {p: n for p, n in read_counts.items() if n > 1}
    if duplicates:
        logger.info(
            "Duplicate reads in %s: %d file(s), worst: %s (%dx)",
            wt_path, len(duplicates),
            *max(duplicates.items(), key=lambda kv: kv[1]),
        )
    return duplicates


def update_duplicate_reads(state_file: str, change_name: str, wt_path: str) -> None:
    """Compute duplicate reads for a worktree and persist to change state.
    Safe to call repeatedly — each call recomputes from the latest session
    files (which only ever grow during a run)."""
    if not wt_path:
        return
    try:
        from .state import update_change_field
        dups = detect_duplicate_reads(wt_path)
        update_change_field(state_file, change_name, "duplicate_reads", dups)
    except Exception:  # noqa: BLE001 — defensive; never fail the verifier
        logger.debug("update_duplicate_reads raised", exc_info=True)
