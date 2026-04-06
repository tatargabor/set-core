"""Replay test: simulate hook pipeline with realistic memory data.

Verifies that the optimized pipeline produces significantly less token
overhead than the old pipeline would have.
"""

import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def _clean_state():
    import set_hooks.memory_ops as mo
    mo._content_seen.clear()
    mo._last_context_ids.clear()
    yield
    mo._content_seen.clear()
    mo._last_context_ids.clear()


@pytest.fixture
def cache_file(tmp_path):
    return str(tmp_path / "cache.json")


# Simulate realistic memory returns from a production run
REALISTIC_MEMORIES = [
    # Same content returned repeatedly (gate retry context — real pattern)
    {"content": "Change frissítve. A lényeg: Két path (merger.py + engine.py) → egy közös _build_gate_retry_context() helper. Framework-agnosztikus — a summary parser generikus regex (N failed, N passed, [.*] › lines), nem Playwright-specifikus. Core-ban marad (lib/set_orch/engine.py). 7 task, kész az apply-ra. Várjuk meg a craftbrew-run20 eredményét.", "relevance_score": 0.45, "id": "mem-dup1"},
    {"content": "Change frissítve. A lényeg: Két path (merger.py + engine.py) → egy közös _build_gate_retry_context() helper. Framework-agnosztikus — a summary parser generikus regex (N failed, N passed, [.*] › lines), nem Playwright-specifikus. Core-ban marad (lib/set_orch/engine.py). 7 task, kész az apply-ra. Várjuk meg a craftbrew-run20 eredményét.", "relevance_score": 0.42, "id": "mem-dup2"},
    {"content": "Change frissítve. A lényeg: Két path (merger.py + engine.py) → egy közös _build_gate_retry_context() helper. Framework-agnosztikus — a summary parser generikus regex (N failed, N passed, [.*] › lines), nem Playwright-specifikus. Core-ban marad (lib/set_orch/engine.py). 7 task, kész az apply-ra. Várjuk meg a craftbrew-run20 eredményét.", "relevance_score": 0.38, "id": "mem-dup3"},

    # Low relevance garbage
    {"content": "Van már egy 380K dev.db, amit az E2E tesztek használtak.", "relevance_score": 0.35, "id": "mem-low1"},
    {"content": "static-context-ages stalled és nem latszodnak még mindig a Files oszlopban a gomb.", "relevance_score": 0.32, "id": "mem-low2"},

    # Actually relevant memory
    {"content": "PostToolUse hook fires on every Read/Bash tool call. This is the single largest source of token waste in orchestration runs.", "relevance_score": 0.78, "id": "mem-good1"},

    # Long irrelevant content
    {"content": "A " * 400 + "very long memory that goes on and on with no useful information whatsoever, just padding to test truncation behavior in the formatting pipeline.", "relevance_score": 0.60, "id": "mem-long1"},
]


def test_replay_token_reduction(cache_file):
    """Simulate 20 hook calls with realistic data, verify token savings."""
    from set_hooks.memory_ops import _format_memories

    old_total_tokens = 0
    new_total_tokens = 0

    # Simulate 20 hook calls returning the same set of memories
    for i in range(20):
        # Old pipeline: no content dedup, no relevance filtering at 0.55, no truncation
        # Estimate: all 7 memories × full content = ~2800 chars per call
        old_chars = sum(len(m["content"]) for m in REALISTIC_MEMORIES)
        old_total_tokens += old_chars // 4

        # New pipeline: content dedup, relevance filtering, truncation, budget
        result = _format_memories(REALISTIC_MEMORIES, cache_file, "test")
        if result:
            new_total_tokens += len(result) // 4

    # New pipeline should use < 50% of old pipeline tokens
    assert new_total_tokens < old_total_tokens * 0.50, (
        f"New pipeline ({new_total_tokens} tokens) should be < 50% of old ({old_total_tokens} tokens), "
        f"ratio: {new_total_tokens / old_total_tokens:.1%}"
    )


def test_replay_only_relevant_survives(cache_file):
    """Only high-relevance, unique memories should survive the pipeline."""
    from set_hooks.memory_ops import _format_memories

    result = _format_memories(REALISTIC_MEMORIES, cache_file, "test")
    assert result is not None

    # The duplicates (score 0.42-0.45) should be filtered by relevance (< 0.55)
    # The low-relevance ones (0.32, 0.35) should be filtered
    # Only mem-good1 (0.78) and mem-long1 (0.60) should survive
    mem_count = result.count("[MEM#")
    assert mem_count == 2, f"Expected 2 surviving memories, got {mem_count}"

    # The good memory should be present
    assert "PostToolUse hook fires" in result

    # The long memory should be truncated
    assert "..." in result
