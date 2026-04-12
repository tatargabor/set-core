"""Tests for Part 8: Review severity calibration rubric."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.gate_verdict import GateVerdict
from set_orch.llm_verdict import REVIEW_SCHEMA, _build_classifier_prompt
from set_orch.templates import render_review_prompt
from set_orch.verifier import (
    _build_review_retry_prompt,
    _group_review_findings_by_severity,
    _render_grouped_findings_section,
)


class TestReviewPromptRubric:
    def test_prompt_contains_severity_rubric_section(self):
        prompt = render_review_prompt(
            scope="Add a button to the home page",
            diff_output="+ <button>click</button>",
        )
        assert "## Severity Rubric" in prompt
        assert "CRITICAL" in prompt
        assert "crash the app" in prompt
        assert "HIGH" in prompt
        assert "MEDIUM" in prompt
        assert "LOW" in prompt

    def test_prompt_has_when_in_doubt_guidance(self):
        prompt = render_review_prompt(scope="test", diff_output="+ x")
        assert "pick the LOWER one" in prompt

    def test_prompt_shadcn_button_example(self):
        prompt = render_review_prompt(scope="test", diff_output="+ x")
        assert "shadcn Button" in prompt


class TestClassifierPromptRubric:
    def test_classifier_prompt_has_severity_rubric(self):
        prompt = _build_classifier_prompt("review text", REVIEW_SCHEMA)
        assert "SEVERITY RUBRIC" in prompt
        assert "CRITICAL:" in prompt
        assert "MEDIUM:" in prompt

    def test_classifier_prompt_instructs_downgrades(self):
        prompt = _build_classifier_prompt("review text", REVIEW_SCHEMA)
        assert "DOWNGRADE" in prompt or "downgrade" in prompt
        assert "downgrades" in prompt


class TestReviewSchemaDowngrades:
    def test_schema_declares_downgrades_field(self):
        assert "downgrades" in REVIEW_SCHEMA


class TestGateVerdictDowngrades:
    def test_default_downgrades_empty_list(self):
        gv = GateVerdict(gate="review", verdict="pass")
        assert gv.downgrades == []

    def test_downgrades_preserved(self):
        entries = [{"from": "CRITICAL", "to": "MEDIUM", "summary": "shadcn button"}]
        gv = GateVerdict(gate="review", verdict="pass", downgrades=entries)
        assert gv.downgrades == entries


class TestSeverityGroupedRetryPrompt:
    def test_mixed_severities_render_all_sections(self):
        review_output = (
            "ISSUE: [CRITICAL] middleware imports bcryptjs\n"
            "FILE: middleware.ts\n"
            "LINE: 1\n"
            "ISSUE: [MEDIUM] raw button instead of shadcn Button\n"
            "FILE: page.tsx\n"
            "LINE: 42\n"
            "ISSUE: [MEDIUM] missing trailing newline\n"
            "FILE: util.ts\n"
            "LINE: 10\n"
            "ISSUE: [LOW] div instead of semantic element\n"
            "FILE: header.tsx\n"
            "LINE: 5\n"
            "ISSUE: [LOW] console.log left in code\n"
            "FILE: debug.ts\n"
            "LINE: 3\n"
        )
        grouped = _group_review_findings_by_severity(review_output)
        assert len(grouped["CRITICAL"]) == 1
        assert len(grouped["MEDIUM"]) == 2
        assert len(grouped["LOW"]) == 2

        section = _render_grouped_findings_section(grouped)
        assert "## Must Fix" in section
        assert "## Should Fix (if trivial)" in section
        assert "## Nice to Have" in section
        assert "Focus on Must Fix first" in section

    def test_only_critical_renders_only_must_fix(self):
        review_output = (
            "ISSUE: [CRITICAL] sql injection\nFILE: api.ts\nLINE: 10\n"
            "ISSUE: [CRITICAL] xss risk\nFILE: view.ts\nLINE: 20\n"
        )
        grouped = _group_review_findings_by_severity(review_output)
        section = _render_grouped_findings_section(grouped)
        assert "## Must Fix" in section
        assert "## Should Fix" not in section
        assert "## Nice to Have" not in section

    def test_no_findings_returns_empty(self):
        grouped = _group_review_findings_by_severity("REVIEW PASS — no issues")
        section = _render_grouped_findings_section(grouped)
        assert section == ""

    def test_retry_prompt_includes_grouped_section(self, tmp_path):
        import json as _json

        state_file = str(tmp_path / "state.json")
        _json.dump({"plan_version": 2, "status": "running", "changes": [{"name": "foo", "status": "running"}]}, open(state_file, "w"))
        review_output = (
            "ISSUE: [CRITICAL] sql injection in search\nFILE: search.ts\nLINE: 10\n"
            "ISSUE: [MEDIUM] raw button in variant selector\nFILE: variant.tsx\nLINE: 5\n"
        )
        prompt = _build_review_retry_prompt(
            state_file=state_file,
            change_name="foo",
            current_review_output=review_output,
            security_guide="",
            verify_retry_count=0,
            review_retry_limit=3,
        )
        assert "## Must Fix" in prompt
        assert "## Should Fix (if trivial)" in prompt
        assert "sql injection in search" in prompt
