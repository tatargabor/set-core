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
    _build_gap_spans,
    _build_llm_wait_spans,
    _build_sub_spans_for_session,
    _build_tool_spans,
    _categorize_gap,
    _is_cache_valid,
    _is_verifier_session,
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

    def test_short_residual_below_threshold_produces_no_gap_span(self, tmp_path):
        """Residual time below the 30s gap threshold doesn't produce any span.

        Previously this emitted an `agent:overhead` span for any >1s residual,
        but that single-span approach hid the semantic meaning of gaps.
        Now sub-30s residuals are considered normal inter-turn latency and
        are not classified — they contribute to neither llm-wait nor gap.
        """
        path = tmp_path / "session.jsonl"
        _write_session(path, [
            _user_entry(_ts(1000), text="task"),
            _assistant_entry(_ts(1003), tool_uses=[("t1", "Bash", {"command": "ls"})]),
            _user_entry(_ts(1005), tool_results=["t1"]),
            # 5-second trailing queue-operation — no span should be emitted
            {"type": "queue-operation", "timestamp": _ts(1010), "uuid": "qop"},
        ])
        spans = _build_sub_spans_for_session(path)
        # No legacy overhead span + no short gap span
        assert all(s["category"] != "agent:overhead" for s in spans)
        assert all(not s["category"].startswith("agent:review-wait") for s in spans)
        assert all(not s["category"].startswith("agent:verify-wait") for s in spans)
        assert all(not s["category"].startswith("agent:loop-restart") for s in spans)
        assert all(not s["category"].startswith("agent:gap") for s in spans)


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


# ─── Verifier session exclusion ─────────────────────────────────────


class TestVerifierSessionDetection:
    def test_spec_verify_marker_detected(self):
        entries = _parse_session_file_from_list([
            _user_entry(_ts(1000), "[PURPOSE:spec_verify:foundation-setup]\nIMPORTANT: ..."),
            _assistant_entry(_ts(1010), "ok"),
        ])
        assert _is_verifier_session(entries) is True

    def test_review_marker_detected(self):
        entries = _parse_session_file_from_list([
            _user_entry(_ts(1000), "[PURPOSE:review:auth-and-navigation]\nReview the change..."),
            _assistant_entry(_ts(1010), "ok"),
        ])
        assert _is_verifier_session(entries) is True

    def test_regular_agent_task_not_detected(self):
        entries = _parse_session_file_from_list([
            _user_entry(_ts(1000), "# Task\nImplement the 'foundation-setup' change"),
            _assistant_entry(_ts(1010), "ok"),
        ])
        assert _is_verifier_session(entries) is False

    def test_verifier_session_produces_no_spans(self, tmp_path):
        path = tmp_path / "verifier.jsonl"
        _write_session(path, [
            _user_entry(_ts(1000), "[PURPOSE:spec_verify:some-change]\nVerify..."),
            _assistant_entry(_ts(1030), "verified", tool_uses=[("t1", "Bash", {"command": "ls"})]),
            _user_entry(_ts(1040), tool_results=["t1"]),
        ])
        assert _build_sub_spans_for_session(path) == []


# ─── Gap categorization (_categorize_gap) ───────────────────────────


class TestCategorizeGap:
    def test_empty_prompt_is_gap(self):
        assert _categorize_gap("") == "agent:gap"

    def test_review_failure_becomes_review_wait(self):
        assert _categorize_gap("# Task\nCRITICAL CODE REVIEW FAILURE for foo") == "agent:review-wait"

    def test_review_findings_becomes_review_wait(self):
        assert _categorize_gap("Please fix the review findings in .claude/...") == "agent:review-wait"

    def test_failing_tests_becomes_verify_wait(self):
        assert _categorize_gap("# Task\nFix the failing tests in tests/e2e/") == "agent:verify-wait"

    def test_smoke_tests_failed_becomes_verify_wait(self):
        assert _categorize_gap("Note: some inherited smoke tests also failed (non-blocking)") == "agent:verify-wait"

    def test_generic_task_prompt_becomes_loop_restart(self):
        assert _categorize_gap("# Task\nImplement REQ-XYZ-001 in src/foo.ts") == "agent:loop-restart"

    def test_unrelated_prompt_becomes_gap(self):
        assert _categorize_gap("hello world") == "agent:gap"


# ─── _build_gap_spans ───────────────────────────────────────────────


class TestBuildGapSpans:
    def test_short_gap_produces_no_span(self):
        """Gaps below the 30s threshold are ignored — normal inter-turn latency."""
        entries = _parse_session_file_from_list([
            _user_entry(_ts(1000), "task"),
            _assistant_entry(_ts(1020), "ok"),  # 20s gap, below threshold
        ])
        gaps = _build_gap_spans(entries, [], "s")
        assert gaps == []

    def test_long_gap_with_review_prompt_produces_review_wait(self):
        entries = _parse_session_file_from_list([
            _user_entry(_ts(1000), "initial task"),
            _assistant_entry(_ts(1010), "Done."),
            # 120s gap — no activity
            _user_entry(_ts(1130), "# Task\nCRITICAL CODE REVIEW FAILURE for 'x'"),
            _assistant_entry(_ts(1140), "fixing..."),
        ])
        # Build existing llm-wait spans first, then detect gaps not covered
        llm_spans = _build_llm_wait_spans(entries, "s")
        gaps = _build_gap_spans(entries, llm_spans, "s")
        assert len(gaps) == 1
        assert gaps[0]["category"] == "agent:review-wait"
        assert gaps[0]["duration_ms"] == 120_000
        assert "CRITICAL CODE REVIEW" in gaps[0]["detail"]["next_prompt"]

    def test_long_gap_with_verify_prompt_produces_verify_wait(self):
        entries = _parse_session_file_from_list([
            _user_entry(_ts(1000), "task"),
            _assistant_entry(_ts(1010), "Done fixing tests."),
            # 5 minute gap
            _user_entry(_ts(1310), "# Task\nSome inherited smoke tests also failed — fix them"),
        ])
        llm_spans = _build_llm_wait_spans(entries, "s")
        gaps = _build_gap_spans(entries, llm_spans, "s")
        assert len(gaps) == 1
        assert gaps[0]["category"] == "agent:verify-wait"

    def test_gap_fully_covered_by_existing_span_is_skipped(self):
        entries = _parse_session_file_from_list([
            _user_entry(_ts(1000), "task"),
            _assistant_entry(_ts(1500), "done"),  # 500s gap from user→assistant
        ])
        llm_spans = _build_llm_wait_spans(entries, "s")
        # The llm-wait span already covers 1000→1500; gap detection should
        # find the gap but determine it's covered → no gap span.
        gaps = _build_gap_spans(entries, llm_spans, "s")
        assert gaps == []

    def test_gap_queue_operation_enqueue_content_used_for_categorization(self, tmp_path):
        """queue-operation entries carry the enqueued prompt in `content`; gap
        detection should use that for categorization."""
        path = tmp_path / "q.jsonl"
        entries = [
            _user_entry(_ts(1000), "initial"),
            _assistant_entry(_ts(1010), "done."),
            # queue-operation marks a new enqueued task — the gap is from 1010 to 1200
            {
                "type": "queue-operation",
                "timestamp": _ts(1200),
                "operation": "enqueue",
                "content": "# Task\nCRITICAL CODE REVIEW FAILURE for 'x'. Fix it.",
                "sessionId": "s",
            },
            _user_entry(_ts(1201), "# Task\nCRITICAL CODE REVIEW FAILURE for 'x'. Fix it."),
            _assistant_entry(_ts(1210), "fixing"),
        ]
        _write_session(path, entries)
        parsed = _parse_session_file(path)
        llm_spans = _build_llm_wait_spans(parsed, "s")
        gaps = _build_gap_spans(parsed, llm_spans, "s")
        # Should find the gap between the first assistant (1010) and the
        # queue-operation (1200) = 190s, categorized as review-wait
        review_gaps = [g for g in gaps if g["category"] == "agent:review-wait"]
        assert len(review_gaps) >= 1, f"expected review-wait gap, got: {[g['category'] for g in gaps]}"


# ─── Integration: full session build with new gap logic ────────────


class TestSessionBuildWithGaps:
    def test_no_agent_overhead_category_emitted(self, tmp_path):
        """The old single `agent:overhead` span is gone — per-gap spans replace it."""
        path = tmp_path / "sess.jsonl"
        _write_session(path, [
            _user_entry(_ts(1000), "task"),
            _assistant_entry(_ts(1005), "Done."),
            # 3 minute gap
            _user_entry(_ts(1185), "# Task\nCRITICAL CODE REVIEW FAILURE"),
            _assistant_entry(_ts(1190), "fixing"),
        ])
        spans = _build_sub_spans_for_session(path)
        # No legacy overhead span
        assert all(s["category"] != "agent:overhead" for s in spans)
        # But we have a review-wait gap span
        review = [s for s in spans if s["category"] == "agent:review-wait"]
        assert len(review) == 1
        assert review[0]["duration_ms"] == 180_000


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
