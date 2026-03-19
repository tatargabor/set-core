"""Orchestrator memory helpers: remember, recall, gate stats.

Migrated from: lib/orchestration/orch-memory.sh (145 LOC)
Provides: orch_remember(), orch_recall(), orch_gate_stats(),
          plan_memory_hygiene(), orch_memory_stats(), orch_memory_audit()
"""

import logging
import shutil
import time
from typing import Any

from .subprocess_utils import run_command

logger = logging.getLogger(__name__)

# ─── Counters ────────────────────────────────────────────────────

_mem_ops_count = 0
_mem_ops_total_ms = 0
_mem_recall_count = 0
_mem_recall_total_ms = 0


def reset_counters() -> None:
    """Reset memory operation counters."""
    global _mem_ops_count, _mem_ops_total_ms, _mem_recall_count, _mem_recall_total_ms
    _mem_ops_count = 0
    _mem_ops_total_ms = 0
    _mem_recall_count = 0
    _mem_recall_total_ms = 0


# ─── Remember ────────────────────────────────────────────────────
# Migrated from: orch-memory.sh:orch_remember()


def orch_remember(
    content: str,
    mem_type: str = "Learning",
    tags: str = "",
) -> bool:
    """Save content to memory with source:orchestrator tag.

    Args:
        content: Memory content text.
        mem_type: Memory type (Decision, Learning, Context).
        tags: Additional comma-separated tags.

    Returns:
        True on success, False on failure.
    """
    global _mem_ops_count, _mem_ops_total_ms

    if not shutil.which("set-memory"):
        return False

    tag_str = f"source:orchestrator{f',{tags}' if tags else ''}"
    start_ms = _now_ms()

    result = run_command(
        ["set-memory", "remember", "--type", mem_type, "--tags", tag_str],
        stdin_data=content,
        timeout=30,
    )

    elapsed_ms = _now_ms() - start_ms
    _mem_ops_count += 1
    _mem_ops_total_ms += elapsed_ms

    logger.info(
        "Memory save: %dms (type=%s, tags=%s)",
        elapsed_ms,
        mem_type,
        tag_str,
    )
    return result.exit_code == 0


# ─── Recall ──────────────────────────────────────────────────────
# Migrated from: orch-memory.sh:orch_recall()


def orch_recall(
    query: str,
    limit: int = 3,
    tags: str = "source:orchestrator",
) -> str:
    """Recall memories with optional tag filtering.

    Args:
        query: Search query.
        limit: Max number of results.
        tags: Tag filter.

    Returns:
        Concatenated memory content (max 2000 chars).
    """
    global _mem_recall_count, _mem_recall_total_ms

    if not shutil.which("set-memory"):
        return ""

    start_ms = _now_ms()

    result = run_command(
        [
            "set-memory",
            "recall",
            query,
            "--limit",
            str(limit),
            "--tags",
            tags,
            "--mode",
            "hybrid",
        ],
        timeout=30,
    )

    elapsed_ms = _now_ms() - start_ms
    _mem_recall_count += 1
    _mem_recall_total_ms += elapsed_ms

    if result.exit_code != 0:
        logger.info(
            "Memory recall: %dms, failed (query='%s')",
            elapsed_ms,
            query[:60],
        )
        return ""

    # Parse JSON output and extract content
    import json

    try:
        memories = json.loads(result.stdout)
        parts = []
        for m in memories:
            content = m.get("content", "")
            # Skip stale memories
            mem_tags = m.get("tags", "")
            if "stale:true" in mem_tags:
                continue
            parts.append(content)
        text = "\n".join(parts)[:2000]
    except (json.JSONDecodeError, TypeError):
        text = result.stdout[:2000]

    logger.info(
        "Memory recall: %dms, %d chars (query='%s', limit=%d)",
        elapsed_ms,
        len(text),
        query[:60],
        limit,
    )
    return text


# ─── Gate Stats ──────────────────────────────────────────────────
# Migrated from: orch-memory.sh:orch_gate_stats()


def orch_gate_stats(state: dict[str, Any]) -> dict[str, Any]:
    """Aggregate quality gate cost summary across all changes.

    Args:
        state: Orchestration state dict.

    Returns:
        Dict with total_gate_ms, total_retry_tokens, etc.
    """
    total_gate_ms = 0
    total_retry_tokens = 0
    total_retry_count = 0
    changes_with_gate = 0

    for change in state.get("changes", []):
        gate_ms = change.get("gate_total_ms", 0)
        if not gate_ms:
            continue
        total_gate_ms += gate_ms
        total_retry_tokens += change.get("gate_retry_tokens", 0)
        total_retry_count += change.get("gate_retry_count", 0)
        changes_with_gate += 1

    if changes_with_gate == 0:
        return {}

    active_seconds = state.get("active_seconds", 1)
    active_ms = active_seconds * 1000
    gate_pct = (total_gate_ms * 100 // active_ms) if active_ms > 0 else 0

    return {
        "changes_with_gate": changes_with_gate,
        "total_gate_ms": total_gate_ms,
        "total_gate_secs": total_gate_ms // 1000,
        "gate_pct": gate_pct,
        "total_retry_count": total_retry_count,
        "total_retry_tokens_k": total_retry_tokens // 1000,
    }


# ─── Memory Hygiene ──────────────────────────────────────────────
# Migrated from: orch-memory.sh:plan_memory_hygiene()


def plan_memory_hygiene() -> dict[str, Any]:
    """Pre-decomposition memory health check.

    Returns:
        Dict with total_memories, duplicates, elapsed_ms.
    """
    if not shutil.which("set-memory"):
        return {}

    start_ms = _now_ms()

    # Dedup dry-run
    dedup_result = run_command(
        ["set-memory", "dedup", "--dry-run"],
        timeout=30,
    )
    dedup_count = 0
    if dedup_result.exit_code == 0:
        import re

        m = re.search(r"(\d+)\s+duplicates", dedup_result.stdout)
        if m:
            dedup_count = int(m.group(1))

    # Stats
    stats_result = run_command(
        ["set-memory", "stats", "--json"],
        timeout=30,
    )
    total_memories = 0
    if stats_result.exit_code == 0:
        import json

        try:
            stats = json.loads(stats_result.stdout)
            total_memories = stats.get("total_memories", 0)
        except (json.JSONDecodeError, TypeError):
            pass

    elapsed_ms = _now_ms() - start_ms

    logger.info(
        "Memory hygiene: %dms — %d memories, %d duplicates found (dry-run)",
        elapsed_ms,
        total_memories,
        dedup_count,
    )

    return {
        "total_memories": total_memories,
        "duplicates": dedup_count,
        "elapsed_ms": elapsed_ms,
    }


# ─── Memory Audit ────────────────────────────────────────────────
# Periodic memory health check (dedup dry-run + spot-check)


def orch_memory_audit() -> dict[str, Any]:
    """Periodic memory health check: dedup dry-run + spot-check.

    Returns:
        Dict with duplicates found, total memories, elapsed_ms.
    """
    if not shutil.which("set-memory"):
        return {}

    start_ms = _now_ms()

    # Dedup dry-run
    dedup_result = run_command(
        ["set-memory", "dedup", "--dry-run"],
        timeout=30,
    )
    dedup_count = 0
    if dedup_result.exit_code == 0:
        import re

        m = re.search(r"(\d+)\s+duplicates", dedup_result.stdout)
        if m:
            dedup_count = int(m.group(1))

    # Spot-check: verify index integrity
    verify_result = run_command(
        ["set-memory", "verify-index"],
        timeout=30,
    )
    index_ok = verify_result.exit_code == 0

    elapsed_ms = _now_ms() - start_ms

    logger.info(
        "Memory audit: %dms — %d duplicates, index %s",
        elapsed_ms,
        dedup_count,
        "ok" if index_ok else "BROKEN",
    )

    return {
        "duplicates": dedup_count,
        "index_ok": index_ok,
        "elapsed_ms": elapsed_ms,
    }


# ─── Memory Stats ────────────────────────────────────────────────
# Migrated from: orch-memory.sh:orch_memory_stats()


def orch_memory_stats() -> dict[str, Any]:
    """Log cumulative memory operation stats.

    Returns:
        Dict with ops/recall counts and timing.
    """
    total_ops = _mem_ops_count + _mem_recall_count
    if total_ops == 0:
        return {}

    total_ms = _mem_ops_total_ms + _mem_recall_total_ms
    avg_save_ms = (_mem_ops_total_ms // _mem_ops_count) if _mem_ops_count > 0 else 0
    avg_recall_ms = (
        (_mem_recall_total_ms // _mem_recall_count) if _mem_recall_count > 0 else 0
    )

    stats = {
        "total_ops": total_ops,
        "save_count": _mem_ops_count,
        "recall_count": _mem_recall_count,
        "total_ms": total_ms,
        "avg_save_ms": avg_save_ms,
        "avg_recall_ms": avg_recall_ms,
    }

    logger.info(
        "Memory stats: %d ops (%d saves, %d recalls), total %dms "
        "(save avg %dms, recall avg %dms)",
        total_ops,
        _mem_ops_count,
        _mem_recall_count,
        total_ms,
        avg_save_ms,
        avg_recall_ms,
    )

    return stats


# ─── Helpers ─────────────────────────────────────────────────────


def _now_ms() -> int:
    """Current time in milliseconds."""
    return int(time.time() * 1000)
