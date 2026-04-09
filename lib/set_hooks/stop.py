"""Hook stop pipeline: metrics flush, commit-based memory save, checkpoint.

Uses set-memoryd daemon client for fast remember (bypass CLI subprocess overhead).
Falls back to CLI subprocess if daemon is unavailable.

Transcript-based insight extraction was removed (2026-04-09) — the auto-extracted
memories had ~0.1% citation rate and dominated the memory store with noise
(regex matched every `## ` markdown heading). Valuable learnings come from
commit messages, design choices, and explicit user feedback, all saved here.
"""

import os
import subprocess
from typing import Optional

from .util import (
    _log, _dbg, read_cache, write_cache,
    get_daemon_client, daemon_is_running,
)


def _remember_via_daemon_or_cli(
    content: str,
    mem_type: str = "Learning",
    tags: str = "",
) -> bool:
    """Remember via daemon (fast) or CLI subprocess (fallback). Returns True on success."""
    # Try daemon
    client = get_daemon_client()
    if client is not None:
        try:
            client.remember(content, memory_type=mem_type, tags=tags)
            return True
        except Exception:
            pass

    # Fallback to CLI — only if daemon is NOT running (avoids RocksDB lock conflict)
    if daemon_is_running():
        return False
    try:
        subprocess.run(
            ["set-memory", "remember", "--type", mem_type, "--tags", tags],
            input=content,
            text=True,
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        return False


def flush_metrics(
    cache_file: str,
    session_id: str,
    transcript_path: str = "",
    set_tools_root: str = "",
) -> None:
    """Collect session metrics, call lib.metrics.flush_session()."""
    cache = read_cache(cache_file)
    metrics = cache.get("_metrics", [])
    if not metrics:
        _dbg("stop", "metrics: no data")
        return

    injected_content = cache.get("_injected_content", {})

    # Resolve project name — prefer CLAUDE_PROJECT_DIR to avoid cross-project leakage
    project = "unknown"
    claude_project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if claude_project_dir:
        project = os.path.basename(claude_project_dir)
    else:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                project = os.path.basename(result.stdout.strip())
        except Exception:
            pass

    # Import lib.metrics (add set_tools_root to path if needed)
    import sys

    if set_tools_root and set_tools_root not in sys.path:
        sys.path.insert(0, set_tools_root)

    # Compute per-layer aggregates
    layer_agg = {}
    for m in metrics:
        layer = m.get("layer", "?")
        if layer not in layer_agg:
            layer_agg[layer] = {"injections": 0, "tokens": 0, "dedup_hits": 0, "empty": 0}
        agg = layer_agg[layer]
        if m.get("token_estimate", 0) > 0:
            agg["injections"] += 1
            agg["tokens"] += m.get("token_estimate", 0)
        elif m.get("dedup_hit", 0):
            agg["dedup_hits"] += 1
        else:
            agg["empty"] += 1

    if layer_agg:
        parts = []
        for layer, agg in sorted(layer_agg.items()):
            parts.append(f"{layer}: {agg['injections']}inj/{agg['tokens']}tok/{agg['dedup_hits']}dup/{agg['empty']}empty")
        _log("stop", f"metrics-agg: {', '.join(parts)}")

    try:
        from lib.metrics import flush_session, scan_transcript_citations

        # Scan transcript for citations + passive matches
        citations = []
        mem_matches = []
        if transcript_path and os.path.exists(transcript_path):
            results = scan_transcript_citations(
                transcript_path, session_id, injected_content
            )
            for r in results:
                if r.get("context_id"):
                    mem_matches.append(r)
                else:
                    citations.append(r)

        flush_session(session_id, project, metrics, citations, mem_matches)
        _log("stop", f"metrics: flushed {len(metrics)} records")
    except ImportError:
        _dbg("stop", "metrics: lib.metrics not available")
    except Exception as e:
        _dbg("stop", f"metrics: error: {e}")


def save_commit_memories(set_tools_root: str = "") -> int:
    """Find git commits in session, save with source:commit tag.

    Returns number of commits saved.
    """
    try:
        from set_orch.paths import SetRuntime
        _rt = SetRuntime()
        marker_file = _rt.last_memory_commit_file
        design_marker = os.path.join(_rt.designs_cache_dir, ".saved")
        codemap_marker = os.path.join(_rt.codemaps_cache_dir, ".saved")
    except Exception:
        marker_file = ".set-core/.last-memory-commit"
        design_marker = ".set-core/.saved-designs"
        codemap_marker = ".set-core/.saved-codemaps"

    last_hash = ""
    if os.path.isfile(marker_file):
        try:
            with open(marker_file, "r") as f:
                last_hash = f.read().strip()
        except OSError:
            pass

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return 0
        current_hash = result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return 0

    if current_hash == last_hash:
        return 0

    # Get commits
    if last_hash:
        try:
            subprocess.run(
                ["git", "cat-file", "-t", last_hash],
                capture_output=True,
                timeout=5,
            )
            result = subprocess.run(
                ["git", "log", "--oneline", f"{last_hash}..HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            result = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                capture_output=True,
                text=True,
                timeout=10,
            )
    else:
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True,
            text=True,
            timeout=10,
        )

    if result.returncode != 0:
        return 0

    saved = 0
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split(" ", 1)
        if len(parts) < 2:
            continue
        commit_hash, msg = parts

        change_name = "general"
        if ":" in msg:
            change_name = msg.split(":")[0]

        # Save design choices if available
        _save_design_choices(change_name, design_marker)
        saved += 1

    # Update marker
    os.makedirs(os.path.dirname(marker_file), exist_ok=True)
    try:
        with open(marker_file, "w") as f:
            f.write(current_hash)
    except OSError:
        pass

    return saved


def save_checkpoint(
    cache_file: str,
    turn_count: int,
    last_checkpoint: int,
) -> bool:
    """Periodic summary of files/topics (every N turns). Returns True if saved."""
    cache = read_cache(cache_file)
    metrics = cache.get("_metrics", [])

    files_read = set()
    commands_run = 0
    topics = []
    l2_count = 0

    for m in metrics:
        if m.get("event") == "UserPromptSubmit":
            l2_count += 1
            if l2_count <= last_checkpoint:
                continue
            q = m.get("query", "")
            if q and len(q) > 10:
                words = q.split()[:6]
                topics.append(" ".join(words))
        elif m.get("event") == "PostToolUse" and l2_count > last_checkpoint:
            q = m.get("query", "")
            if "/" in q and not q.startswith("git "):
                files_read.add(q)
            elif q:
                commands_run += 1

    parts = []
    if files_read:
        flist = ", ".join(sorted(files_read)[:8])
        if len(files_read) > 8:
            flist += f" (+{len(files_read) - 8} more)"
        parts.append(f"Files: {flist}")
    if commands_run:
        parts.append(f"Commands: {commands_run}")
    if topics:
        seen = set()
        unique = []
        for t in topics:
            key = t[:30].lower()
            if key not in seen:
                seen.add(key)
                unique.append(t[:60])
        if unique:
            parts.append(f"Topics: {chr(10).join(unique[:5])}")

    if not parts:
        parts.append("(conversation-only, no tool activity)")

    summary = (
        f"[session checkpoint, turns {last_checkpoint + 1}-{turn_count}] "
        + " | ".join(parts)
    )
    summary = summary[:800]

    if _remember_via_daemon_or_cli(
        summary, mem_type="Context", tags="phase:checkpoint,source:hook"
    ):
        _log("stop", f"checkpoint: saved turns {last_checkpoint + 1}-{turn_count}")
        from .session import set_last_checkpoint_turn
        set_last_checkpoint_turn(cache_file, turn_count)
        return True
    return False


# ─── Internal helpers ─────────────────────────────────────────


def _save_design_choices(change_name: str, design_marker: str) -> None:
    """Extract and save design choices from design.md."""
    design_file = f"openspec/changes/{change_name}/design.md"
    if not os.path.isfile(design_file):
        return

    # Check marker
    if os.path.isfile(design_marker):
        try:
            with open(design_marker, "r") as f:
                if change_name in f.read():
                    return
        except OSError:
            pass

    try:
        with open(design_file, "r") as f:
            content = f.read()
    except OSError:
        return

    choices = []
    for line in content.splitlines():
        if line.startswith("**Choice**"):
            choice = line.replace("**Choice**:", "").replace("**Choice**", "").strip()
            if choice:
                choices.append(choice)

    if choices:
        text = f"{change_name}: {'. '.join(choices)}"
        if len(text) > 300:
            text = text[:297] + "..."
        _remember_via_daemon_or_cli(
            text,
            mem_type="Decision",
            tags=f"change:{change_name},phase:apply,source:hook,decisions",
        )

    # Update marker
    os.makedirs(os.path.dirname(design_marker) or ".", exist_ok=True)
    try:
        with open(design_marker, "a") as f:
            f.write(f"{change_name}\n")
    except OSError:
        pass
