"""Tests for set_orch.auditor — prompt construction, result parsing, severity."""

import json
import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.auditor import (
    AuditGap,
    AuditResult,
    build_audit_prompt,
    parse_audit_result,
    _dict_to_audit_result,
)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ─── build_audit_prompt ──────────────────────────────────────────


class TestBuildAuditPrompt:
    def test_spec_mode_basic(self, tmp_dir):
        spec_file = os.path.join(tmp_dir, "spec.md")
        with open(spec_file, "w") as f:
            f.write("# My Spec\n\nSome requirements.")

        state = {
            "changes": [
                {"name": "c1", "status": "merged", "scope": "auth"},
                {"name": "c2", "status": "failed", "scope": "db"},
            ]
        }

        result = build_audit_prompt(state, input_mode="spec", input_path=spec_file)
        assert result["mode"] == "spec"
        assert "My Spec" in result["spec_text"]
        assert len(result["changes"]) == 2
        # Merged change is first
        assert result["changes"][0]["name"] == "c1"
        assert result["changes"][0]["status"] == "merged"
        # Failed change included for context
        assert result["changes"][1]["name"] == "c2"
        assert result["changes"][1]["status"] == "failed"

    def test_spec_mode_no_file(self):
        state = {"changes": []}
        result = build_audit_prompt(state, input_mode="spec", input_path="/nonexistent")
        assert result["spec_text"] == ""

    def test_digest_mode(self, tmp_dir):
        reqs = {
            "requirements": [
                {"id": "REQ-A-001", "title": "Auth", "brief": "Login"},
            ]
        }
        with open(os.path.join(tmp_dir, "requirements.json"), "w") as f:
            json.dump(reqs, f)

        cov = {
            "coverage": {
                "REQ-A-001": {"status": "merged", "change": "c1"},
            }
        }
        with open(os.path.join(tmp_dir, "coverage.json"), "w") as f:
            json.dump(cov, f)

        state = {
            "changes": [
                {"name": "c1", "status": "merged", "scope": "auth"},
            ]
        }

        result = build_audit_prompt(
            state, input_mode="digest", digest_dir=tmp_dir
        )
        assert result["mode"] == "digest"
        assert len(result["requirements"]) == 1
        assert result["requirements"][0]["id"] == "REQ-A-001"
        assert "REQ-A-001" in result["coverage"]

    def test_digest_mode_missing_files(self, tmp_dir):
        state = {"changes": []}
        result = build_audit_prompt(
            state, input_mode="digest", digest_dir=tmp_dir
        )
        assert result["mode"] == "digest"
        assert result["requirements"] == []
        assert result["coverage"] == ""

    def test_only_merged_and_failed_included(self):
        state = {
            "changes": [
                {"name": "c1", "status": "merged", "scope": "a"},
                {"name": "c2", "status": "running", "scope": "b"},
                {"name": "c3", "status": "skipped", "scope": "c"},
                {"name": "c4", "status": "dispatched", "scope": "d"},
            ]
        }
        result = build_audit_prompt(state)
        names = [c["name"] for c in result["changes"]]
        assert "c1" in names  # merged
        assert "c3" in names  # skipped
        assert "c2" not in names  # running — not included
        assert "c4" not in names  # dispatched — not included


# ─── parse_audit_result ──────────────────────────────────────────


class TestParseAuditResult:
    def test_direct_json(self):
        data = {
            "audit_result": "gaps_found",
            "gaps": [
                {
                    "requirement_id": "REQ-A-001",
                    "description": "Missing validation",
                    "severity": "critical",
                    "suggested_fix": "Add input validation",
                }
            ],
            "recommendations": ["Add more tests"],
            "coverage_score": 0.85,
            "summary": "Overall good",
        }
        result = parse_audit_result(json.dumps(data))
        assert result.audit_result == "gaps_found"
        assert len(result.gaps) == 1
        assert result.gaps[0].severity == "critical"
        assert result.gaps[0].requirement_id == "REQ-A-001"
        assert result.coverage_score == 0.85
        assert len(result.recommendations) == 1

    def test_markdown_fenced(self):
        raw = '```json\n{"audit_result": "clean", "gaps": [], "coverage_score": 1.0}\n```'
        result = parse_audit_result(raw)
        assert result.audit_result == "clean"
        assert len(result.gaps) == 0

    def test_with_preamble(self):
        raw = 'Here is my analysis:\n\n{"audit_result": "gaps_found", "gaps": [{"severity": "warning", "description": "Minor issue"}]}'
        result = parse_audit_result(raw)
        assert result.audit_result == "gaps_found"
        assert len(result.gaps) == 1

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Could not parse"):
            parse_audit_result("This is not JSON at all")

    def test_json_without_audit_result_key_raises(self):
        with pytest.raises(ValueError):
            parse_audit_result('{"unrelated": "data"}')


# ─── _dict_to_audit_result ──────────────────────────────────────


class TestDictToAuditResult:
    def test_full_gap_parsing(self):
        data = {
            "audit_result": "gaps_found",
            "gaps": [
                {
                    "requirement_id": "REQ-X-001",
                    "description": "Missing feature",
                    "severity": "critical",
                    "suggested_fix": "Implement it",
                    "spec_reference": "section 3.1",
                    "suggested_scope": "auth module",
                },
                {
                    "requirement_id": "REQ-X-002",
                    "description": "Minor thing",
                    "severity": "info",
                },
            ],
            "recommendations": ["rec1", "rec2"],
            "coverage_score": 0.75,
            "summary": "Needs work",
        }
        result = _dict_to_audit_result(data)
        assert isinstance(result, AuditResult)
        assert len(result.gaps) == 2
        assert result.gaps[0].spec_reference == "section 3.1"
        assert result.gaps[1].suggested_fix == ""  # default
        assert result.summary == "Needs work"

    def test_empty_gaps(self):
        data = {"audit_result": "clean", "coverage_score": 1.0}
        result = _dict_to_audit_result(data)
        assert result.gaps == []
        assert result.recommendations == []

    def test_severity_levels(self):
        """All three severity levels are handled."""
        data = {
            "audit_result": "gaps_found",
            "gaps": [
                {"severity": "critical", "description": "a"},
                {"severity": "warning", "description": "b"},
                {"severity": "info", "description": "c"},
            ],
        }
        result = _dict_to_audit_result(data)
        severities = [g.severity for g in result.gaps]
        assert severities == ["critical", "warning", "info"]
