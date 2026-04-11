"""Tests for lib/set_orch/llm_verdict.py — the unified LLM verdict classifier.

See OpenSpec change: llm-verdict-classifier

Background
----------
Two production silent-pass incidents (micro/create-task 2026-04-11 and
minishop_0410/product-catalog attempt 4) merged CRITICAL findings because
the review gate body-regex parser did not recognise the retry-review
format. The fix is a format-agnostic classifier (second Sonnet pass) that
reads the primary output and returns a structured verdict.

This test file exercises the classifier helper itself. Tests for the
gates that USE the classifier live in test_verifier.py and
test_investigator.py.
"""

import json
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.llm_verdict import (
    ClassifierResult,
    INVESTIGATOR_SCHEMA,
    REVIEW_SCHEMA,
    SPEC_VERIFY_SCHEMA,
    _extract_json,
    _validate_required,
    classify_verdict,
)
from set_orch.subprocess_utils import CommandResult


# ─── _extract_json ────────────────────────────────────────────────


class TestExtractJson:
    def test_raw_json(self):
        text = '{"verdict": "pass", "critical_count": 0}'
        out = _extract_json(text)
        assert out == {"verdict": "pass", "critical_count": 0}

    def test_raw_json_with_whitespace(self):
        text = '  \n{"verdict": "pass", "critical_count": 0}\n  '
        assert _extract_json(text) == {"verdict": "pass", "critical_count": 0}

    def test_fenced_json(self):
        text = '```json\n{"verdict": "fail", "critical_count": 3}\n```'
        assert _extract_json(text) == {"verdict": "fail", "critical_count": 3}

    def test_fenced_json_no_language(self):
        text = '```\n{"verdict": "pass", "critical_count": 0}\n```'
        assert _extract_json(text) == {"verdict": "pass", "critical_count": 0}

    def test_preamble_before_json(self):
        text = 'Here is the verdict:\n\n{"verdict": "fail", "critical_count": 2}'
        assert _extract_json(text) == {"verdict": "fail", "critical_count": 2}

    def test_nested_braces_in_findings(self):
        text = '{"verdict": "fail", "critical_count": 1, "findings": [{"severity": "CRITICAL", "summary": "nested"}]}'
        out = _extract_json(text)
        assert out is not None
        assert out["findings"][0]["severity"] == "CRITICAL"

    def test_string_with_brace_char_does_not_break_balance(self):
        text = '{"verdict": "fail", "critical_count": 1, "summary": "contains } char"}'
        out = _extract_json(text)
        assert out is not None
        assert out["summary"] == "contains } char"

    def test_empty_string_returns_none(self):
        assert _extract_json("") is None
        assert _extract_json("   ") is None

    def test_non_json_returns_none(self):
        assert _extract_json("not json at all") is None

    def test_unbalanced_braces_returns_none(self):
        assert _extract_json("{verdict: pass") is None

    def test_json_array_top_level_extracts_first_inner_object(self):
        # Brace-match extracts the first balanced object from within an array.
        # This is permissive — classifier rarely returns arrays, but if it
        # wraps the result in a single-element list we still recover.
        assert _extract_json('[{"verdict": "pass"}]') == {"verdict": "pass"}


# ─── _validate_required ──────────────────────────────────────────


class TestValidateRequired:
    def test_valid(self):
        assert _validate_required({"verdict": "pass", "critical_count": 0}) is None

    def test_missing_verdict(self):
        assert _validate_required({"critical_count": 0}) == "verdict"

    def test_missing_critical_count(self):
        assert _validate_required({"verdict": "pass"}) == "critical_count"

    def test_non_integer_critical_count(self):
        assert _validate_required({"verdict": "pass", "critical_count": "not a number"}) == "critical_count"

    def test_string_integer_critical_count_ok(self):
        # "3" is int-coercible
        assert _validate_required({"verdict": "pass", "critical_count": "3"}) is None


# ─── classify_verdict ────────────────────────────────────────────


def _make_claude_result(stdout: str, *, exit_code: int = 0, timed_out: bool = False, duration_ms: int = 1500):
    """Build a fake ClaudeResult. ClaudeResult extends CommandResult."""
    result = CommandResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr="",
        duration_ms=duration_ms,
        timed_out=timed_out,
    )
    return result


class TestClassifyVerdictHappyPath:
    def test_pass_verdict(self, monkeypatch):
        from set_orch import llm_verdict, subprocess_utils

        fake_response = json.dumps({
            "verdict": "pass",
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 2,
            "low_count": 1,
            "findings": [
                {"severity": "MEDIUM", "summary": "warn A"},
                {"severity": "LOW", "summary": "warn B"},
            ],
        })

        monkeypatch.setattr(
            subprocess_utils, "run_claude_logged",
            lambda *a, **kw: _make_claude_result(fake_response),
        )

        result = classify_verdict(
            primary_output="REVIEW PASS — no critical issues found.\n",
            schema=REVIEW_SCHEMA,
            purpose="review",
        )
        assert result.verdict == "pass"
        assert result.critical_count == 0
        assert result.medium_count == 2
        assert result.error is None
        assert len(result.findings) == 2

    def test_fail_verdict_with_critical_findings(self, monkeypatch):
        from set_orch import llm_verdict, subprocess_utils

        fake_response = json.dumps({
            "verdict": "fail",
            "critical_count": 3,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "findings": [
                {"severity": "CRITICAL", "summary": "missing waitUntil"},
                {"severity": "CRITICAL", "summary": "missing blank-input test"},
                {"severity": "CRITICAL", "summary": "no title length limit"},
            ],
        })

        monkeypatch.setattr(
            subprocess_utils, "run_claude_logged",
            lambda *a, **kw: _make_claude_result(fake_response),
        )

        result = classify_verdict(
            primary_output="## Retry Review — Verifying 3 Previous Findings\n\n### Finding 1: ...\n**NOT_FIXED** [CRITICAL]",
            schema=REVIEW_SCHEMA,
            purpose="review",
        )
        assert result.verdict == "fail"
        assert result.critical_count == 3
        assert result.error is None
        assert [f["severity"] for f in result.findings] == ["CRITICAL", "CRITICAL", "CRITICAL"]


class TestClassifyVerdictJsonFormats:
    def test_json_in_markdown_fences(self, monkeypatch):
        from set_orch import subprocess_utils

        fake = '```json\n{"verdict": "pass", "critical_count": 0}\n```'
        monkeypatch.setattr(
            subprocess_utils, "run_claude_logged",
            lambda *a, **kw: _make_claude_result(fake),
        )
        result = classify_verdict("x", REVIEW_SCHEMA, purpose="review")
        assert result.verdict == "pass"
        assert result.error is None

    def test_preamble_before_json(self, monkeypatch):
        from set_orch import subprocess_utils

        fake = 'Here is the verdict:\n\n{"verdict": "fail", "critical_count": 2}'
        monkeypatch.setattr(
            subprocess_utils, "run_claude_logged",
            lambda *a, **kw: _make_claude_result(fake),
        )
        result = classify_verdict("x", REVIEW_SCHEMA, purpose="review")
        assert result.verdict == "fail"
        assert result.critical_count == 2
        assert result.error is None


class TestClassifyVerdictFailSafe:
    def test_empty_primary_output_returns_fail_safe(self):
        result = classify_verdict("", REVIEW_SCHEMA, purpose="review")
        assert result.verdict == "fail"
        assert result.critical_count == 1
        assert result.error == "empty_output"

    def test_whitespace_primary_output_returns_fail_safe(self):
        result = classify_verdict("   \n\t\n  ", REVIEW_SCHEMA, purpose="review")
        assert result.verdict == "fail"
        assert result.error == "empty_output"

    def test_classifier_exit_nonzero_returns_fail_safe(self, monkeypatch):
        from set_orch import subprocess_utils

        monkeypatch.setattr(
            subprocess_utils, "run_claude_logged",
            lambda *a, **kw: _make_claude_result("", exit_code=2),
        )
        result = classify_verdict("some primary output", REVIEW_SCHEMA, purpose="review")
        assert result.verdict == "fail"
        assert result.critical_count == 1
        assert result.error == "exit_2"

    def test_classifier_timeout_returns_fail_safe(self, monkeypatch):
        from set_orch import subprocess_utils

        monkeypatch.setattr(
            subprocess_utils, "run_claude_logged",
            lambda *a, **kw: _make_claude_result("", exit_code=-1, timed_out=True),
        )
        result = classify_verdict("some primary output", REVIEW_SCHEMA, purpose="review")
        assert result.verdict == "fail"
        assert result.error == "timeout"

    def test_classifier_exception_returns_fail_safe(self, monkeypatch):
        from set_orch import subprocess_utils

        def boom(*a, **kw):
            raise RuntimeError("network gone")

        monkeypatch.setattr(subprocess_utils, "run_claude_logged", boom)
        result = classify_verdict("some primary output", REVIEW_SCHEMA, purpose="review")
        assert result.verdict == "fail"
        assert "RuntimeError" in (result.error or "")

    def test_classifier_non_json_output_returns_fail_safe(self, monkeypatch):
        from set_orch import subprocess_utils

        monkeypatch.setattr(
            subprocess_utils, "run_claude_logged",
            lambda *a, **kw: _make_claude_result("Sorry, I cannot classify that."),
        )
        result = classify_verdict("some primary output", REVIEW_SCHEMA, purpose="review")
        assert result.verdict == "fail"
        assert result.error == "no_json_object"

    def test_classifier_missing_required_field_returns_fail_safe(self, monkeypatch):
        from set_orch import subprocess_utils

        fake = json.dumps({"verdict": "pass"})  # missing critical_count
        monkeypatch.setattr(
            subprocess_utils, "run_claude_logged",
            lambda *a, **kw: _make_claude_result(fake),
        )
        result = classify_verdict("some primary output", REVIEW_SCHEMA, purpose="review")
        assert result.verdict == "fail"
        assert result.error == "missing_field:critical_count"

    def test_classifier_invalid_critical_count_type_returns_fail_safe(self, monkeypatch):
        from set_orch import subprocess_utils

        fake = json.dumps({"verdict": "pass", "critical_count": "not a number"})
        monkeypatch.setattr(
            subprocess_utils, "run_claude_logged",
            lambda *a, **kw: _make_claude_result(fake),
        )
        result = classify_verdict("some primary output", REVIEW_SCHEMA, purpose="review")
        assert result.verdict == "fail"
        assert result.error == "missing_field:critical_count"


class TestClassifierEventBus:
    def test_event_emitted_on_success(self, monkeypatch):
        from set_orch import subprocess_utils

        fake = json.dumps({"verdict": "pass", "critical_count": 0})
        monkeypatch.setattr(
            subprocess_utils, "run_claude_logged",
            lambda *a, **kw: _make_claude_result(fake),
        )
        mock_bus = MagicMock()
        classify_verdict("input", REVIEW_SCHEMA, purpose="review", event_bus=mock_bus)
        assert mock_bus.emit.called
        args, kwargs = mock_bus.emit.call_args
        assert args[0] == "CLASSIFIER_CALL"
        data = kwargs.get("data") or (args[1] if len(args) > 1 else {})
        assert data.get("purpose") == "review"
        assert data.get("verdict") == "pass"
        assert data.get("error") is None

    def test_event_emitted_on_fail_safe(self, monkeypatch):
        from set_orch import subprocess_utils

        monkeypatch.setattr(
            subprocess_utils, "run_claude_logged",
            lambda *a, **kw: _make_claude_result("garbage"),
        )
        mock_bus = MagicMock()
        classify_verdict("input", REVIEW_SCHEMA, purpose="review", event_bus=mock_bus)
        args, kwargs = mock_bus.emit.call_args
        data = kwargs.get("data") or (args[1] if len(args) > 1 else {})
        assert data.get("error") == "no_json_object"
        assert data.get("verdict") == "fail"


# ─── Schema sanity ─────────────────────────────────────────────


class TestSchemas:
    def test_review_schema_has_required_fields(self):
        assert "verdict" in REVIEW_SCHEMA
        assert "critical_count" in REVIEW_SCHEMA
        assert "findings" in REVIEW_SCHEMA

    def test_investigator_schema_has_diagnosis_fields(self):
        assert "impact" in INVESTIGATOR_SCHEMA
        assert "fix_scope" in INVESTIGATOR_SCHEMA
        assert "fix_target" in INVESTIGATOR_SCHEMA
        assert "confidence" in INVESTIGATOR_SCHEMA

    def test_spec_verify_schema_has_findings(self):
        assert "findings" in SPEC_VERIFY_SCHEMA
        assert "critical_count" in SPEC_VERIFY_SCHEMA
