"""Tests for set_hooks.memory_ops — recall, proactive, rules, formatting."""

import json
import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_hooks.memory_ops import (
    recall_memories,
    proactive_context,
    load_matching_rules,
    extract_query,
    output_hook_context,
    output_top_context,
    format_memory_output,
    _format_memories,
    get_last_context_ids,
    MIN_RELEVANCE,
    MIN_CONTENT_LEN,
)
from set_hooks.util import read_cache, write_cache


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def cache_file(tmp_dir):
    return os.path.join(tmp_dir, "session-cache.json")


@pytest.fixture
def rules_dir(tmp_dir):
    claude_dir = os.path.join(tmp_dir, ".claude")
    os.makedirs(claude_dir)
    return claude_dir


# ─── extract_query ────────────────────────────────────────────


class TestExtractQuery:
    def test_read_tool(self):
        data = {"tool_name": "Read", "tool_input": {"file_path": "/foo/bar/baz.py"}}
        assert extract_query(data) == "bar/baz.py"

    def test_read_short_path(self):
        data = {"tool_name": "Read", "tool_input": {"file_path": "file.py"}}
        assert extract_query(data) == "file.py"

    def test_bash_tool(self):
        data = {"tool_name": "Bash", "tool_input": {"command": "ls -la /tmp"}}
        assert extract_query(data) == "ls -la /tmp"

    def test_bash_truncation(self):
        long_cmd = "x" * 300
        data = {"tool_name": "Bash", "tool_input": {"command": long_cmd}}
        assert len(extract_query(data)) == 200

    def test_grep_tool(self):
        data = {"tool_name": "Grep", "tool_input": {"pattern": "def foo"}}
        assert extract_query(data) == "def foo"

    def test_edit_tool(self):
        data = {"tool_name": "Edit", "tool_input": {"file_path": "/a/b/c.py"}}
        assert extract_query(data) == "b/c.py"

    def test_unknown_tool_fallback(self):
        data = {"tool_name": "Unknown", "tool_input": {"prompt": "hello"}}
        assert extract_query(data) == "hello"

    def test_empty_input(self):
        data = {"tool_name": "Unknown", "tool_input": {}}
        assert extract_query(data) == ""


# ─── output formatting ───────────────────────────────────────


class TestOutputFormatting:
    def test_hook_context(self):
        result = output_hook_context("PostToolUse", "some context")
        parsed = json.loads(result)
        assert parsed["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert parsed["hookSpecificOutput"]["additionalContext"] == "some context"

    def test_top_context(self):
        result = output_top_context("top level")
        parsed = json.loads(result)
        assert parsed["additionalContext"] == "top level"

    def test_format_memory_output(self):
        result = format_memory_output("TEST HEADER", "formatted content")
        assert "=== TEST HEADER ===" in result
        assert "formatted content" in result


# ─── _format_memories ─────────────────────────────────────────


class TestFormatMemories:
    def test_basic_formatting(self, cache_file):
        memories = [
            {"content": "A" * 50, "relevance_score": 0.8},
            {"content": "B" * 50, "relevance_score": 0.6},
        ]
        result = _format_memories(memories, cache_file, "test")
        assert result is not None
        assert "MEM#" in result
        lines = [l for l in result.strip().splitlines() if l.strip()]
        assert len(lines) == 2

    def test_filters_low_relevance(self, cache_file):
        memories = [
            {"content": "A" * 50, "relevance_score": 0.1},  # Below MIN_RELEVANCE
        ]
        result = _format_memories(memories, cache_file, "test")
        assert result is None

    def test_filters_short_content(self, cache_file):
        memories = [
            {"content": "short", "relevance_score": 0.8},
        ]
        result = _format_memories(memories, cache_file, "test")
        assert result is None

    def test_dedup_by_prefix(self, cache_file):
        content = "X" * 100
        memories = [
            {"content": content, "relevance_score": 0.8},
            {"content": content, "relevance_score": 0.7},
        ]
        result = _format_memories(memories, cache_file, "test")
        lines = [l for l in result.strip().splitlines() if l.strip()]
        assert len(lines) == 1

    def test_heuristic_warning(self, cache_file):
        memories = [
            {"content": "This is a false positive detection " + "x" * 30, "relevance_score": 0.8},
        ]
        result = _format_memories(memories, cache_file, "test")
        assert "\u26a0\ufe0f HEURISTIC" in result

    def test_no_score_passes(self, cache_file):
        memories = [
            {"content": "No score memory content here " + "x" * 30},
        ]
        result = _format_memories(memories, cache_file, "test")
        assert result is not None

    def test_na_score_passes(self, cache_file):
        memories = [
            {"content": "NA score memory content here " + "x" * 30, "relevance_score": "N/A"},
        ]
        result = _format_memories(memories, cache_file, "test")
        assert result is not None

    def test_context_ids_stored(self, cache_file):
        memories = [
            {"content": "A" * 50, "relevance_score": 0.8},
            {"content": "B" * 50, "relevance_score": 0.7},
        ]
        _format_memories(memories, cache_file, "test")
        ids = get_last_context_ids()
        assert len(ids) == 2

    def test_empty_input(self, cache_file):
        result = _format_memories([], cache_file, "test")
        assert result is None


# ─── load_matching_rules ──────────────────────────────────────


class TestLoadMatchingRules:
    def _write_rules(self, rules_dir, rules):
        rules_file = os.path.join(rules_dir, "rules.yaml")
        try:
            import yaml
            with open(rules_file, "w") as f:
                yaml.dump({"rules": rules}, f)
            return True
        except ImportError:
            return False

    def test_matching_rule(self, rules_dir):
        if not self._write_rules(rules_dir, [
            {"id": "r1", "topics": ["testing"], "content": "Always run tests"}
        ]):
            pytest.skip("yaml not available")
        result = load_matching_rules("I need help with testing", os.path.dirname(rules_dir))
        assert "MANDATORY RULES" in result
        assert "Always run tests" in result

    def test_no_match(self, rules_dir):
        if not self._write_rules(rules_dir, [
            {"id": "r1", "topics": ["testing"], "content": "Always run tests"}
        ]):
            pytest.skip("yaml not available")
        result = load_matching_rules("deploy to production", os.path.dirname(rules_dir))
        assert result == ""

    def test_no_rules_file(self, tmp_dir):
        result = load_matching_rules("anything", tmp_dir)
        assert result == ""

    def test_multiple_matches(self, rules_dir):
        if not self._write_rules(rules_dir, [
            {"id": "r1", "topics": ["test"], "content": "Rule one"},
            {"id": "r2", "topics": ["test"], "content": "Rule two"},
        ]):
            pytest.skip("yaml not available")
        result = load_matching_rules("run the test suite", os.path.dirname(rules_dir))
        assert "Rule one" in result
        assert "Rule two" in result
