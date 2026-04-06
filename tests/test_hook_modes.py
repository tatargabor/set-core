"""Tests for memory hook mode control (SET_MEMORY_HOOKS env var).

Tests hook mode guards (off/lite/full), relevance threshold,
content-based dedup, display truncation, and token budget.
"""

import hashlib
import json
import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def _clean_module_state():
    """Reset module-level state between tests."""
    import set_hooks.memory_ops as mo
    mo._content_seen.clear()
    mo._last_context_ids.clear()
    yield
    mo._content_seen.clear()
    mo._last_context_ids.clear()


@pytest.fixture
def cache_file(tmp_path):
    """Provide a temporary cache file."""
    return str(tmp_path / "cache.json")


def _make_memories(contents, score=0.7):
    """Build a list of fake memory dicts."""
    return [
        {"content": c, "relevance_score": score, "id": f"mem-{i}"}
        for i, c in enumerate(contents)
    ]


# ── Hook Mode Tests ──────────────────────────────────────────────


class TestHookModeOff:
    """SET_MEMORY_HOOKS=off → no injection hooks fire, Stop still works."""

    def test_session_start_returns_none(self, monkeypatch, cache_file):
        monkeypatch.setenv("SET_MEMORY_HOOKS", "off")
        # Must reimport to pick up new HOOK_MODE
        import importlib
        import set_hooks.util as util_mod
        importlib.reload(util_mod)
        import set_hooks.events as events_mod
        importlib.reload(events_mod)

        result = events_mod.handle_session_start({"source": "startup"}, cache_file)
        assert result is None

    def test_user_prompt_returns_none(self, monkeypatch, cache_file):
        monkeypatch.setenv("SET_MEMORY_HOOKS", "off")
        import importlib
        import set_hooks.util as util_mod
        importlib.reload(util_mod)
        import set_hooks.events as events_mod
        importlib.reload(events_mod)

        result = events_mod.handle_user_prompt({"prompt": "test prompt"}, cache_file)
        assert result is None

    def test_post_tool_returns_none(self, monkeypatch, cache_file):
        monkeypatch.setenv("SET_MEMORY_HOOKS", "off")
        import importlib
        import set_hooks.util as util_mod
        importlib.reload(util_mod)
        import set_hooks.events as events_mod
        importlib.reload(events_mod)

        result = events_mod.handle_post_tool(
            {"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}}, cache_file
        )
        assert result is None

    def test_stop_still_executes(self, monkeypatch, cache_file):
        """Stop hook must execute even in off mode (for transcript extraction)."""
        monkeypatch.setenv("SET_MEMORY_HOOKS", "off")
        import importlib
        import set_hooks.util as util_mod
        importlib.reload(util_mod)
        import set_hooks.events as events_mod
        importlib.reload(events_mod)

        # handle_stop returns None normally (it doesn't inject) but shouldn't early-return
        # We just verify it doesn't raise and processes normally
        result = events_mod.handle_stop(
            {"session_id": "test", "stop_hook_active": False}, cache_file
        )
        assert result is None  # Stop always returns None


class TestHookModeLite:
    """SET_MEMORY_HOOKS=lite → only SessionStart and UserPrompt fire."""

    def test_post_tool_returns_none(self, monkeypatch, cache_file):
        monkeypatch.setenv("SET_MEMORY_HOOKS", "lite")
        import importlib
        import set_hooks.util as util_mod
        importlib.reload(util_mod)
        import set_hooks.events as events_mod
        importlib.reload(events_mod)

        result = events_mod.handle_post_tool(
            {"tool_name": "Bash", "tool_input": {"command": "ls"}}, cache_file
        )
        assert result is None

    def test_post_tool_failure_returns_none(self, monkeypatch, cache_file):
        monkeypatch.setenv("SET_MEMORY_HOOKS", "lite")
        import importlib
        import set_hooks.util as util_mod
        importlib.reload(util_mod)
        import set_hooks.events as events_mod
        importlib.reload(events_mod)

        result = events_mod.handle_post_tool_failure(
            {"error": "some error message text here"}, cache_file
        )
        assert result is None

    def test_subagent_start_returns_none(self, monkeypatch, cache_file):
        monkeypatch.setenv("SET_MEMORY_HOOKS", "lite")
        import importlib
        import set_hooks.util as util_mod
        importlib.reload(util_mod)
        import set_hooks.events as events_mod
        importlib.reload(events_mod)

        result = events_mod.handle_subagent_start(
            {"tool_input": {"prompt": "do something"}}, cache_file
        )
        assert result is None

    def test_subagent_stop_returns_none(self, monkeypatch, cache_file):
        monkeypatch.setenv("SET_MEMORY_HOOKS", "lite")
        import importlib
        import set_hooks.util as util_mod
        importlib.reload(util_mod)
        import set_hooks.events as events_mod
        importlib.reload(events_mod)

        result = events_mod.handle_subagent_stop(
            {"agent_transcript_path": "/nonexistent"}, cache_file
        )
        assert result is None

    def test_commit_save_still_works_in_lite(self, monkeypatch, cache_file):
        """PostToolUse in lite mode still saves commit memories."""
        monkeypatch.setenv("SET_MEMORY_HOOKS", "lite")
        import importlib
        import set_hooks.util as util_mod
        importlib.reload(util_mod)
        import set_hooks.events as events_mod
        importlib.reload(events_mod)

        # Mock _commit_save to track if called
        called = []
        monkeypatch.setattr(events_mod, "_commit_save", lambda *a, **kw: called.append(1))

        result = events_mod.handle_post_tool(
            {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "test"'}},
            cache_file,
        )
        assert result is None  # No memory injection
        assert len(called) == 1  # But commit save was called


class TestHookModeFull:
    """SET_MEMORY_HOOKS=full → all hooks enabled (legacy behavior)."""

    def test_post_tool_processes_normally(self, monkeypatch, cache_file):
        monkeypatch.setenv("SET_MEMORY_HOOKS", "full")
        import importlib
        import set_hooks.util as util_mod
        importlib.reload(util_mod)
        import set_hooks.events as events_mod
        importlib.reload(events_mod)

        # With no daemon and no memories, it returns None (no results)
        # but it should NOT early-return due to mode guard
        monkeypatch.setattr(events_mod, "recall_memories", lambda *a, **kw: None)
        result = events_mod.handle_post_tool(
            {"tool_name": "Read", "tool_input": {"file_path": "/tmp/test.py"}},
            cache_file,
        )
        # Returns None because recall returned nothing, not because of mode guard
        assert result is None


# ── Content Dedup Tests ──────────────────────────────────────────


class TestContentDedup:
    """Content-based dedup prevents same memory from being injected twice."""

    def test_same_content_different_ids_deduped(self, cache_file):
        from set_hooks.memory_ops import _format_memories

        content = "This is a test memory content that should only appear once in output"
        memories = [
            {"content": content, "relevance_score": 0.8, "id": "mem-aaa"},
            {"content": content, "relevance_score": 0.8, "id": "mem-bbb"},
            {"content": content, "relevance_score": 0.8, "id": "mem-ccc"},
        ]

        result = _format_memories(memories, cache_file, "test")
        assert result is not None
        # Only one MEM# line should appear
        assert result.count("[MEM#") == 1

    def test_dedup_persists_across_calls(self, cache_file):
        from set_hooks.memory_ops import _format_memories

        content = "Persistent dedup test memory content for cross-call testing"
        memories1 = [{"content": content, "relevance_score": 0.8, "id": "mem-1"}]
        memories2 = [{"content": content, "relevance_score": 0.8, "id": "mem-2"}]

        result1 = _format_memories(memories1, cache_file, "test")
        result2 = _format_memories(memories2, cache_file, "test")

        assert result1 is not None  # First call succeeds
        assert result2 is None  # Second call deduped (no new content)

    def test_different_content_not_deduped(self, cache_file):
        from set_hooks.memory_ops import _format_memories

        memories = _make_memories([
            "First unique memory about feature A",
            "Second unique memory about feature B",
        ])

        result = _format_memories(memories, cache_file, "test")
        assert result is not None
        assert result.count("[MEM#") == 2


# ── Relevance Threshold Tests ────────────────────────────────────


class TestRelevanceThreshold:
    """MIN_RELEVANCE = 0.55 filters low-quality matches."""

    def test_low_score_filtered(self, cache_file):
        from set_hooks.memory_ops import _format_memories

        memories = _make_memories(["Low relevance memory content here"], score=0.4)
        result = _format_memories(memories, cache_file, "test")
        assert result is None

    def test_high_score_passes(self, cache_file):
        from set_hooks.memory_ops import _format_memories

        memories = _make_memories(["High relevance memory content here"], score=0.6)
        result = _format_memories(memories, cache_file, "test")
        assert result is not None
        assert "High relevance" in result

    def test_no_score_passes(self, cache_file):
        from set_hooks.memory_ops import _format_memories

        memories = [{"content": "Memory without a relevance score field", "id": "x"}]
        result = _format_memories(memories, cache_file, "test")
        assert result is not None

    def test_na_score_passes(self, cache_file):
        from set_hooks.memory_ops import _format_memories

        memories = [{"content": "Memory with N/A relevance score", "relevance_score": "N/A", "id": "x"}]
        result = _format_memories(memories, cache_file, "test")
        assert result is not None


# ── Display Truncation Tests ─────────────────────────────────────


class TestDisplayTruncation:
    """Memory content > 300 chars truncated with '...'."""

    def test_long_content_truncated(self, cache_file):
        from set_hooks.memory_ops import _format_memories

        long_content = "A" * 500
        memories = _make_memories([long_content])
        result = _format_memories(memories, cache_file, "test")
        assert result is not None
        # Should contain 300 A's followed by ...
        assert "A" * 300 + "..." in result
        # Should NOT contain 301+ A's
        assert "A" * 301 not in result.replace("...", "")

    def test_short_content_not_truncated(self, cache_file):
        from set_hooks.memory_ops import _format_memories

        short_content = "Short memory content"
        memories = _make_memories([short_content])
        result = _format_memories(memories, cache_file, "test")
        assert result is not None
        assert short_content in result
        # No trailing ... for short content
        lines = [l for l in result.split("\n") if "[MEM#" in l]
        assert not lines[0].endswith("...")


# ── Token Budget Tests ───────────────────────────────────────────


class TestTokenBudget:
    """Per-injection budget of 800 tokens caps total output."""

    def test_budget_limits_memories(self, cache_file):
        from set_hooks.memory_ops import _format_memories

        # Each truncated line ≈ 330 chars ≈ 82 tokens
        # 800 token budget → max ~9 memories
        # 15 unique memories should be capped
        big = "X" * 1200
        memories = [
            {"content": f"UniqueContent-{i:02d}: " + big, "relevance_score": 0.8, "id": f"mem-{i}"}
            for i in range(15)
        ]

        result = _format_memories(memories, cache_file, "test")
        assert result is not None
        mem_count = result.count("[MEM#")
        # Budget should cap well below 15
        assert mem_count < 15
        assert mem_count >= 1
        # Verify total output is within budget (~800 tokens = ~3200 chars)
        assert len(result) < 4000
