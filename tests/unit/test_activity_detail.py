"""Tests for set_orch.api.activity_detail — heuristic session jsonl analyzer.

Covers tasks 11.1-11.13 of the activity-implementing-drilldown change.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.api.activity_detail import (
    _build_llm_wait_spans,
    _build_sub_spans_for_session,
    _build_tool_spans,
    _is_cache_valid,
    _link_subagents,
    _load_cache,
    _normalize_tool_name,
    _parse_session_file,
    _slugify_purpose,
    _union_duration_ms,
    _write_cache,
    KNOWN_TOOLS,
    SUBAGENT_TOOL_NAMES,
)


# ─── Helpers ─────────────────────────────────────────────────────────


def _ts(seconds_from_epoch: int, ms: int = 0) -> str:
    """Build an ISO 8601 timestamp with millisecond precision (UTC)."""
    dt = datetime.fromtimestamp(seconds_from_epoch, tz=timezone.utc)
    return dt.replace(microsecond=ms * 1000).isoformat().replace("+00:00", "Z")


def _write_session(path: Path, entries: list[dict]) -> None:
    """Write a list of entry dicts as a JSONL file."""
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _user_entry(ts: str, text: str | None = None, tool_results: list[str] | None = None, uuid: str = "") -> dict:
    content: list = []
    if text is not None:
        content.append({"type": "text", "text": text})
    if tool_results:
        for tid in tool_results:
            content.append({"type": "tool_result", "tool_use_id": tid, "content": "result"})
    return {
        "type": "user",
        "uuid": uuid or f"user-{ts}",
        "timestamp": ts,
        "message": {"role": "user", "content": content},
    }


def _assistant_entry(
    ts: str,
    text: str | None = None,
    tool_uses: list[tuple[str, str, dict]] | None = None,
    uuid: str = "",
    model: str = "sonnet",
    usage: dict | None = None,
) -> dict:
    content: list = []
    if text is not None:
        content.append({"type": "text", "text": text})
    if tool_uses:
        for tid, tname, tinput in tool_uses:
            content.append({"type": "tool_use", "id": tid, "name": tname, "input": tinput})
    return {
        "type": "assistant",
        "uuid": uuid or f"asst-{ts}",
        "timestamp": ts,
        "message": {
            "role": "assistant",
            "model": model,
            "content": content,
            "usage": usage or {"input_tokens": 100, "output_tokens": 200},
        },
    }


# ─── Tool name normalization (task 11.4) ────────────────────────────


class TestNormalizeToolName:
    @pytest.mark.parametrize("raw,expected", [
        ("Bash", "bash"),
        ("Edit", "edit"),
        ("Write", "write"),
        ("Read", "read"),
        ("Glob", "glob"),
        ("Grep", "grep"),
        ("WebFetch", "webfetch"),
        ("WebSearch", "websearch"),
        ("Task", "task"),
        ("Agent", "agent"),
        ("Skill", "skill"),
        ("TodoWrite", "todowrite"),
        ("ToolSearch", "toolsearch"),
    ])
    def test_known_tools(self, raw, expected):
        assert _normalize_tool_name(raw) == expected
        assert expected in KNOWN_TOOLS

    def test_unknown_tool(self):
        assert _normalize_tool_name("MysteryTool") == "other"

    def test_empty_name(self):
        assert _normalize_tool_name("") == "other"


# ─── _build_llm_wait_spans (task 11.2) ──────────────────────────────


class TestBuildLlmWaitSpans:
    def test_user_to_assistant_produces_span(self):
        entries = _parse_session_file_from_list([
            _user_entry(_ts(1000), "Implement foundation"),
            _assistant_entry(_ts(1002), "OK", model="sonnet", usage={"input_tokens": 50, "output_tokens": 80}),
        ])
        spans = _build_llm_wait_spans(entries, "session-A")
        assert len(spans) == 1
        s = spans[0]
        assert s["category"] == "agent:llm-wait"
        assert s["duration_ms"] == 2000
        assert s["detail"]["session"] == "session-A"
        assert s["detail"]["model"] == "sonnet"
        assert s["detail"]["input_tokens"] == 50
        assert s["detail"]["output_tokens"] == 80
        assert s["detail"]["kind"] == "response"

    def test_assistant_to_assistant_produces_streaming_span(self):
        """Multi-message LLM output (assistant→assistant) is also LLM wait time."""
        entries = _parse_session_file_from_list([
            _assistant_entry(_ts(1000), "First chunk"),
            _assistant_entry(_ts(1003), "Second chunk"),
        ])
        spans = _build_llm_wait_spans(entries, "session-B")
        assert len(spans) == 1
        assert spans[0]["category"] == "agent:llm-wait"
        assert spans[0]["duration_ms"] == 3000
        assert spans[0]["detail"]["kind"] == "stream"


# ─── _build_tool_spans (task 11.3) ──────────────────────────────────


class TestBuildToolSpans:
    def test_bash_tool_use_to_result(self):
        entries = _parse_session_file_from_list([
            _assistant_entry(_ts(1000), tool_uses=[("tool-1", "Bash", {"command": "ls -la"})]),
            _user_entry(_ts(1005), tool_results=["tool-1"]),
        ])
        spans = _build_tool_spans(entries, "session-X")
        assert len(spans) == 1
        s = spans[0]
        assert s["category"] == "agent:tool:bash"
        assert s["duration_ms"] == 5000
        assert s["detail"]["tool"] == "Bash"
        assert s["detail"]["preview"] == "ls -la"

    def test_unknown_tool_becomes_other(self):
        entries = _parse_session_file_from_list([
            _assistant_entry(_ts(1000), tool_uses=[("t1", "MysteryTool", {"key": "value"})]),
            _user_entry(_ts(1001), tool_results=["t1"]),
        ])
        spans = _build_tool_spans(entries, "s")
        assert len(spans) == 1
        assert spans[0]["category"] == "agent:tool:other"
        assert spans[0]["detail"]["tool"] == "MysteryTool"

    def test_agent_tool_becomes_subagent_category(self):
        """Sub-agent dispatches (Agent/Task tool) get the agent:subagent: prefix."""
        entries = _parse_session_file_from_list([
            _assistant_entry(_ts(1000), tool_uses=[("t1", "Agent", {
                "description": "Verify foundation implementation",
                "prompt": "Run /opsx:verify foundation",
            })]),
            _user_entry(_ts(1100), tool_results=["t1"]),
        ])
        spans = _build_tool_spans(entries, "s")
        assert len(spans) == 1
        assert spans[0]["category"].startswith("agent:subagent:")
        assert spans[0]["detail"]["tool"] == "Agent"
        assert spans[0]["detail"]["purpose"] == "Verify foundation implementation"


# ─── _link_subagents (tasks 11.5-11.6) ──────────────────────────────


class TestLinkSubagents:
    def test_unmatched_task_stays_as_subagent_when_no_siblings(self, tmp_path):
        """When no sibling jsonls exist, the agent:subagent:* span is unchanged."""
        parent = tmp_path / "parent.jsonl"
        _write_session(parent, [
            _assistant_entry(_ts(1000), tool_uses=[("t1", "Agent", {"description": "Test"})]),
            _user_entry(_ts(1010), tool_results=["t1"]),
        ])
        entries = _parse_session_file(parent)
        tool_spans = _build_tool_spans(entries, "parent")
        # No siblings — _link_subagents should return spans unchanged
        result = _link_subagents(parent, entries, "parent", tool_spans)
        assert len(result) == 1
        assert result[0]["category"].startswith("agent:subagent:")

    def test_matched_subagent_replaces_with_subsession_window(self, tmp_path):
        """When a sibling matches by prompt + timestamp, the subagent span uses the sub-session's wall window."""
        parent = tmp_path / "parent.jsonl"
        sibling = tmp_path / "sibling.jsonl"
        _write_session(parent, [
            _assistant_entry(_ts(1000), tool_uses=[("t1", "Agent", {
                "description": "Verify foundation",
                "prompt": "Verify foundation implementation. Check all files.",
            })]),
            _user_entry(_ts(1020), tool_results=["t1"]),
        ])
        _write_session(sibling, [
            _user_entry(_ts(1001), text="Verify foundation implementation. Check all files."),
            _assistant_entry(_ts(1015), text="Done verifying"),
        ])
        entries = _parse_session_file(parent)
        tool_spans = _build_tool_spans(entries, "parent")
        result = _link_subagents(parent, entries, "parent", tool_spans)
        # Span should have been linked
        assert len(result) == 1
        s = result[0]
        assert s["category"].startswith("agent:subagent:")
        # subagent_session_id should point at the sibling
        assert "subagent_session_id" in s["detail"]
        assert s["detail"]["subagent_session_id"] == "sibling"


# ─── Overhead calculation (task 11.7) ───────────────────────────────


class TestOverheadCalculation:
    def test_overhead_computed_from_wall_minus_accounted(self, tmp_path):
        path = tmp_path / "session.jsonl"
        _write_session(path, [
            _user_entry(_ts(1000), text="task"),
            _assistant_entry(_ts(1003), tool_uses=[("t1", "Bash", {"command": "echo hi"})]),  # llm-wait 3s
            _user_entry(_ts(1005), tool_results=["t1"]),                                       # tool 2s
            # Total wall: 1000→1005 = 5s. Accounted: 3+2 = 5s. Overhead: 0s.
        ])
        spans = _build_sub_spans_for_session(path)
        overhead = [s for s in spans if s["category"] == "agent:overhead"]
        assert overhead == []  # no residual

    def test_overhead_with_residual(self, tmp_path):
        """Synthetic 10s session with 3s llm-wait + 2s tool → 5s overhead."""
        path = tmp_path / "session.jsonl"
        _write_session(path, [
            # First entry at t=1000
            _user_entry(_ts(1000), text="task"),
            _assistant_entry(_ts(1003), tool_uses=[("t1", "Bash", {"command": "ls"})]),  # llm-wait 3s
            _user_entry(_ts(1005), tool_results=["t1"]),                                  # tool 2s
            # Add a 5s gap before the next entry (no spans cover it)
            {"type": "queue-operation", "timestamp": _ts(1010), "uuid": "qop"},
        ])
        spans = _build_sub_spans_for_session(path)
        overhead = [s for s in spans if s["category"] == "agent:overhead"]
        # Wall = 10s, accounted = 5s, overhead = 5s
        assert len(overhead) == 1
        assert overhead[0]["duration_ms"] == 5000


# ─── Cache file (tasks 11.8-11.10) ──────────────────────────────────


class TestCacheFile:
    def test_cache_valid_when_no_session_newer(self, tmp_path):
        cache = tmp_path / "cache.jsonl"
        cache.write_text('{"category":"agent:llm-wait","duration_ms":1000}\n')
        # Make session file older
        sess = tmp_path / "session.jsonl"
        sess.write_text("")
        old_time = cache.stat().st_mtime - 100
        os.utime(sess, (old_time, old_time))
        assert _is_cache_valid(cache, [sess]) is True

    def test_cache_invalid_when_session_newer(self, tmp_path):
        cache = tmp_path / "cache.jsonl"
        cache.write_text("")
        sess = tmp_path / "session.jsonl"
        sess.write_text("")
        # Touch session to be newer than cache
        future = cache.stat().st_mtime + 100
        os.utime(sess, (future, future))
        assert _is_cache_valid(cache, [sess]) is False

    def test_cache_invalid_when_missing(self, tmp_path):
        cache = tmp_path / "no-such-file.jsonl"
        sess = tmp_path / "session.jsonl"
        sess.write_text("")
        assert _is_cache_valid(cache, [sess]) is False

    def test_corrupted_cache_returns_none_and_deletes(self, tmp_path):
        cache = tmp_path / "cache.jsonl"
        cache.write_text("not valid json at all\n")
        result = _load_cache(cache)
        assert result is None
        # File should have been deleted
        assert not cache.exists()

    def test_atomic_write_round_trip(self, tmp_path):
        cache = tmp_path / "cache.jsonl"
        spans = [
            {"category": "agent:llm-wait", "duration_ms": 1000, "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T00:00:01Z"},
            {"category": "agent:tool:bash", "duration_ms": 500, "start": "2026-01-01T00:00:01Z", "end": "2026-01-01T00:00:01.500Z"},
        ]
        _write_cache(cache, spans)
        loaded = _load_cache(cache)
        assert loaded == spans


# ─── Slug + union helpers ───────────────────────────────────────────


class TestSlugifyPurpose:
    def test_basic(self):
        assert _slugify_purpose("Verify foundation setup implementation") == "verify-foundation-setup"

    def test_punctuation_stripped(self):
        assert _slugify_purpose("Run /opsx:verify foo") == "run-opsxverify-foo"

    def test_empty(self):
        assert _slugify_purpose("") == "task"


class TestUnionDurationMs:
    def test_no_overlap_sums(self):
        spans = [
            {"start": "2026-01-01T00:00:00Z", "end": "2026-01-01T00:00:01Z"},
            {"start": "2026-01-01T00:00:02Z", "end": "2026-01-01T00:00:04Z"},
        ]
        # 1s + 2s = 3s, no overlap
        assert _union_duration_ms(spans) == 3000

    def test_full_overlap_counted_once(self):
        spans = [
            {"start": "2026-01-01T00:00:00Z", "end": "2026-01-01T00:00:05Z"},
            {"start": "2026-01-01T00:00:01Z", "end": "2026-01-01T00:00:03Z"},
        ]
        # Outer is 5s, inner is fully contained → union is 5s
        assert _union_duration_ms(spans) == 5000

    def test_partial_overlap(self):
        spans = [
            {"start": "2026-01-01T00:00:00Z", "end": "2026-01-01T00:00:05Z"},
            {"start": "2026-01-01T00:00:03Z", "end": "2026-01-01T00:00:08Z"},
        ]
        # Union: 0→8 = 8s
        assert _union_duration_ms(spans) == 8000


# ─── Helpers used in tests ──────────────────────────────────────────


def _parse_session_file_from_list(entries: list[dict]) -> list[dict]:
    """Pretend the entries came from a file: write to a temp path, parse, return."""
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
        path = Path(f.name)
    try:
        return _parse_session_file(path)
    finally:
        path.unlink()
