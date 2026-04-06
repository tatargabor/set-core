"""Hook utilities: debug logging, metrics timers, cache I/O, daemon helpers.

1:1 migration of lib/hooks/util.sh.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Optional


# ─── Logging ──────────────────────────────────────────────────

DEBUG_LOG = "/tmp/set-hook-memory.log"
_debug_enabled = os.path.exists("/tmp/set-hook-memory.debug") or os.environ.get("SET_HOOK_DEBUG") == "1"


def _log(event: str, msg: str) -> None:
    """Always-on lightweight log: one line per hook invocation."""
    try:
        with open(DEBUG_LOG, "a") as f:
            ts = time.strftime("%H:%M:%S")
            f.write(f"[{ts}] [{event}] {msg}\n")
    except OSError:
        pass


def _dbg(event: str, msg: str) -> None:
    """Verbose debug log: gated on SET_HOOK_DEBUG=1."""
    if not _debug_enabled:
        return
    _log(event, f"DBG {msg}")


# ─── Metrics timers ───────────────────────────────────────────

METRICS_ENABLED_FLAG = os.path.join(
    os.environ.get("HOME", ""), ".local", "share", "set-core", "metrics", ".enabled"
)
METRICS_ENABLED = os.path.exists(METRICS_ENABLED_FLAG)

_timer_start: float = 0.0


def metrics_timer_start() -> None:
    """Start a metrics timer."""
    global _timer_start
    if not METRICS_ENABLED:
        return
    _timer_start = time.time() * 1000


def metrics_timer_elapsed() -> int:
    """Return elapsed ms since timer_start."""
    if not METRICS_ENABLED:
        return 0
    return int(time.time() * 1000 - _timer_start)


# ─── Cache I/O ────────────────────────────────────────────────


def read_cache(cache_file: str) -> dict:
    """Read JSON cache file. Returns empty dict on error."""
    if not os.path.exists(cache_file):
        return {}
    try:
        with open(cache_file, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def write_cache(cache_file: str, data: dict) -> bool:
    """Atomic write of JSON cache file."""
    try:
        tmp = cache_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, cache_file)
        return True
    except OSError:
        return False


# ─── Metrics append ───────────────────────────────────────────


def metrics_append(
    cache_file: str,
    layer: str,
    event: str,
    query: str,
    result_count: int = 0,
    filtered_count: int = 0,
    scores: Optional[list] = None,
    duration_ms: int = 0,
    token_estimate: int = 0,
    dedup_hit: int = 0,
    context_ids: Optional[list] = None,
) -> None:
    """Append a metrics record to session cache _metrics array."""
    if not METRICS_ENABLED:
        return
    cache = read_cache(cache_file)
    metrics = cache.get("_metrics", [])
    if len(metrics) >= 500:
        return

    scores = scores or []
    avg_r = round(sum(scores) / len(scores), 4) if scores else None
    max_r = round(max(scores), 4) if scores else None
    min_r = round(min(scores), 4) if scores else None

    from datetime import datetime, timezone

    metrics.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "layer": layer,
        "event": event,
        "query": query[:500],
        "result_count": result_count,
        "filtered_count": filtered_count,
        "avg_relevance": avg_r,
        "max_relevance": max_r,
        "min_relevance": min_r,
        "duration_ms": duration_ms,
        "token_estimate": token_estimate,
        "dedup_hit": dedup_hit,
        "context_ids": context_ids or [],
    })
    cache["_metrics"] = metrics
    write_cache(cache_file, cache)


# ─── Score extraction ─────────────────────────────────────────


def extract_scores(memories: list) -> list:
    """Extract relevance scores from memory list, returns list of floats."""
    scores = []
    for m in memories:
        s = m.get("relevance_score")
        if s is not None and s != "N/A":
            try:
                scores.append(round(float(s), 4))
            except (ValueError, TypeError):
                pass
    return scores


# ─── Hook mode ───────────────────────────────────────────────

# SET_MEMORY_HOOKS: "full" (all hooks), "lite" (SessionStart+UserPrompt only), "off" (no injection)
HOOK_MODE = os.environ.get("SET_MEMORY_HOOKS", "lite").lower()


# ─── Checkpoint config ────────────────────────────────────────

CHECKPOINT_INTERVAL = 10  # Save checkpoint every N user prompts


# ─── Heuristic patterns (shared by memory_ops and stop) ──────

HEURISTIC_PATTERNS = [
    "false positive",
    "same pattern",
    "known pattern",
    "known issue",
    "was a false",
    "unlike previous",
    "same issue as",
    "this is not a real",
]
HEURISTIC_RE = re.compile(
    "|".join(re.escape(p) for p in HEURISTIC_PATTERNS), re.IGNORECASE
)


# ─── Daemon client helpers (shared by memory_ops, stop, mcp) ─

# Cached daemon client (one per process lifetime)
_daemon_client = None
_daemon_tried = False


def get_daemon_client():
    """Get or create daemon client. Returns None if unavailable.

    Cached for the process lifetime — safe to call repeatedly.
    """
    global _daemon_client, _daemon_tried
    if _daemon_tried:
        return _daemon_client
    _daemon_tried = True
    try:
        from set_memoryd.client import MemoryClient
        _daemon_client = MemoryClient.for_project()
        return _daemon_client
    except Exception:
        return None


def daemon_is_running() -> bool:
    """Check if daemon is running (socket exists). Cheap fs check."""
    try:
        from set_memoryd.lifecycle import is_running, resolve_project
        return is_running(resolve_project())
    except Exception:
        return False
