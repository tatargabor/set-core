"""Hook session management: dedup cache, context ID generation, content tracking.

1:1 migration of lib/hooks/session.sh.
"""

import hashlib
import json
import os
import random
from typing import Optional

from .util import read_cache, write_cache, _dbg


def dedup_clear(cache_file: str) -> None:
    """Clear dedup keys (preserving turn_count, metrics, frustration_history)."""
    _dbg("session", "dedup_clear: clearing dedup keys")
    cache = read_cache(cache_file)
    if not cache:
        return
    keep = {}
    for k in ("turn_count", "last_checkpoint_turn", "_metrics", "frustration_history"):
        if k in cache:
            keep[k] = cache[k]
    write_cache(cache_file, keep)


def dedup_check(cache_file: str, key: str) -> bool:
    """Check if key exists in dedup cache. Returns True if hit."""
    cache = read_cache(cache_file)
    hit = key in cache
    _dbg("session", f"dedup_check: {'HIT' if hit else 'MISS'} key={key}")
    return hit


def dedup_add(cache_file: str, key: str) -> None:
    """Add key to dedup cache."""
    _dbg("session", f"dedup_add: key={key}")
    cache = read_cache(cache_file)
    cache[key] = 1
    write_cache(cache_file, cache)


def make_dedup_key(event: str, tool: str, query: str) -> str:
    """Create a dedup key from event+tool+query."""
    raw = f"{event}:{tool}:{query}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def content_hash(text: str) -> str:
    """Hash content for dedup purposes."""
    return hashlib.md5(text.encode()).hexdigest()[:16]


# ─── Context ID generation ────────────────────────────────────


def gen_context_id(cache_file: str) -> str:
    """Generate a unique 4-char hex context ID within this session."""
    cache = read_cache(cache_file)
    used_ids = cache.get("_used_context_ids", [])

    while True:
        cid = f"{random.randint(0, 0xFFFF):04x}"
        if cid not in used_ids:
            used_ids.append(cid)
            cache["_used_context_ids"] = used_ids
            write_cache(cache_file, cache)
            return cid


def store_injected_content(
    cache_file: str, context_id: str, content: str, metrics_enabled: bool = False
) -> None:
    """Store injected content in session cache for passive matching at Stop time."""
    if not metrics_enabled:
        return
    cache = read_cache(cache_file)
    ic = cache.get("_injected_content", {})
    ic[context_id] = content[:500]
    cache["_injected_content"] = ic
    write_cache(cache_file, cache)


# ─── Turn counter ─────────────────────────────────────────────


def increment_turn(cache_file: str) -> int:
    """Increment turn counter, return new count."""
    cache = read_cache(cache_file)
    tc = cache.get("turn_count", 0) + 1
    cache["turn_count"] = tc
    # Ensure last_checkpoint_turn exists
    cache.setdefault("last_checkpoint_turn", 0)
    write_cache(cache_file, cache)
    return tc


def get_turn_count(cache_file: str) -> int:
    """Get current turn count."""
    cache = read_cache(cache_file)
    return cache.get("turn_count", 0)


def get_last_checkpoint_turn(cache_file: str) -> int:
    """Get the turn number of the last checkpoint."""
    cache = read_cache(cache_file)
    return cache.get("last_checkpoint_turn", 0)


def set_last_checkpoint_turn(cache_file: str, turn: int) -> None:
    """Update the last checkpoint turn number."""
    cache = read_cache(cache_file)
    cache["last_checkpoint_turn"] = turn
    write_cache(cache_file, cache)
