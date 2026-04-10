"""Tests for smart truncation utilities."""

import re
import pytest
from set_orch.truncate import smart_truncate, smart_truncate_structured, truncate_with_budget


class TestSmartTruncate:
    def test_short_text_unchanged(self):
        text = "hello world"
        assert smart_truncate(text, 100) == text

    def test_empty_string(self):
        assert smart_truncate("", 100) == ""

    def test_exact_limit(self):
        text = "a" * 100
        assert smart_truncate(text, 100) == text

    def test_truncation_preserves_head_and_tail(self):
        # 10 lines, each "line-NN\n"
        lines = [f"line-{i:02d}" for i in range(10)]
        text = "\n".join(lines)
        result = smart_truncate(text, 40, head_ratio=0.5)

        assert result.startswith("line-00")
        assert "line-09" in result
        assert "[truncated" in result

    def test_marker_shows_counts(self):
        text = "A" * 100 + "\n" * 5 + "B" * 100
        result = smart_truncate(text, 100)
        assert "truncated" in result
        assert "chars omitted" in result
        assert "lines" in result

    def test_head_ratio_affects_split(self):
        text = "HEAD_MARKER " + "x" * 500 + " TAIL_MARKER"
        # With head_ratio=0.5, head gets half
        result_50 = smart_truncate(text, 100, head_ratio=0.5)
        assert "HEAD_MARKER" in result_50
        assert "TAIL_MARKER" in result_50

        # With head_ratio=0.0, head gets nothing
        result_0 = smart_truncate(text, 100, head_ratio=0.0)
        assert "TAIL_MARKER" in result_0

    def test_output_approximately_within_budget(self):
        text = "x" * 10000
        result = smart_truncate(text, 1000)
        # Result should be around budget + marker overhead (~80 chars)
        assert len(result) < 1200


class TestSmartTruncateStructured:
    def test_short_text_unchanged(self):
        text = "hello world"
        assert smart_truncate_structured(text, 100) == text

    def test_empty_string(self):
        assert smart_truncate_structured("", 100) == ""

    def test_preserves_error_lines_from_middle(self):
        lines = []
        for i in range(200):
            if i == 80:
                lines.append("FATAL ERROR: Cannot find module 'prisma'")
            elif i == 100:
                lines.append("TypeError: undefined is not a function")
            else:
                lines.append(f"normal output line {i} with some padding text here")
        text = "\n".join(lines)

        # Budget large enough to have meaningful head+tail, error lines in middle
        result = smart_truncate_structured(text, 3000)
        assert "Cannot find module" in result
        assert "TypeError" in result
        assert "important line(s) preserved" in result
        assert "> line" in result  # Line number prefix

    def test_no_error_lines_falls_back_to_simple(self):
        text = "\n".join(f"normal line {i}" for i in range(100))
        result = smart_truncate_structured(text, 200)
        assert "[truncated" in result
        assert "important" not in result  # No preserved lines

    def test_preserved_lines_budget_capped(self):
        # All lines are "errors" — can't keep them all
        text = "\n".join(f"ERROR: failure number {i}" for i in range(200))
        result = smart_truncate_structured(text, 500, max_kept_ratio=0.1)

        # Should have some preserved lines but not all 200
        preserved_count = result.count("> line")
        assert 0 < preserved_count < 200

    def test_custom_keep_patterns(self):
        lines = [
            "normal line",
            "CUSTOM_MARKER: something important",
            "another normal line",
        ] * 50
        text = "\n".join(lines)

        custom = re.compile(r"CUSTOM_MARKER")
        result = smart_truncate_structured(text, 300, keep_patterns=custom)
        assert "CUSTOM_MARKER" in result

    def test_default_patterns_cover_common_errors(self):
        error_lines = [
            "Error: ENOENT: no such file",
            "FAIL src/test.ts",
            "CRITICAL: database connection failed",
            "WARNING: deprecated API",
            "panic: runtime error",
            "Traceback (most recent call last):",
            "Cannot find module '@prisma/client'",
            "Build failed with 3 errors",
        ]
        for err_line in error_lines:
            # 500 lines of padding + error in the middle → large enough text
            text = "normal line\n" * 100 + err_line + "\n" + "normal line\n" * 100
            result = smart_truncate_structured(text, 800)
            assert err_line.strip()[:20] in result, f"Pattern not matched: {err_line}"


class TestTruncateWithBudget:
    def test_all_fit(self):
        items = [("rule1", "content1"), ("rule2", "content2")]
        included, omitted = truncate_with_budget(items, 1000)
        assert len(included) == 2
        assert omitted == []

    def test_empty_items(self):
        included, omitted = truncate_with_budget([], 1000)
        assert included == []
        assert omitted == []

    def test_budget_exceeded(self):
        items = [
            ("small", "x" * 100),
            ("medium", "y" * 200),
            ("large", "z" * 5000),
            ("another", "w" * 100),
        ]
        included, omitted = truncate_with_budget(items, 400)
        included_names = [n for n, _ in included]
        assert "small" in included_names
        assert "medium" in included_names
        assert "large" in omitted
        assert "another" in omitted

    def test_first_item_always_included(self):
        """Even if the first item exceeds budget, include it."""
        items = [("big", "x" * 5000), ("small", "y" * 10)]
        included, omitted = truncate_with_budget(items, 100)
        assert len(included) == 1
        assert included[0][0] == "big"
        assert "small" in omitted

    def test_omitted_names_preserves_order(self):
        items = [(f"rule{i}", "x" * 100) for i in range(10)]
        included, omitted = truncate_with_budget(items, 350)
        # First 3 fit (~300 chars), rest omitted
        assert all(f"rule{i}" in omitted for i in range(len(included), 10))
