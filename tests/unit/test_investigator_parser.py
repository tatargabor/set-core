"""Tests for InvestigationRunner._parse_proposal.

See OpenSpec change: llm-verdict-classifier

The parser is exercised at three layers:
1. Explicit sentinels (`**Impact:**`, `**Fix-Scope:**`, etc.) — trusted verbatim
2. LLM verdict classifier fallback when sentinels are missing
3. Word-boundary keyword heuristic last-resort when classifier errors out

Historical note: the pre-fix keyword heuristic used substring matching
(`if "critical" in lines`), which false-positive'd on "criticality" and
"not critical" appearing anywhere in the proposal body.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.issues.audit import AuditLog
from set_orch.issues.investigator import InvestigationRunner
from set_orch.issues.policy import IssuesPolicyConfig
from set_orch.llm_verdict import ClassifierResult


def _make_runner(tmp_path: Path) -> InvestigationRunner:
    return InvestigationRunner(
        set_core_path=tmp_path,
        config=IssuesPolicyConfig(),
        audit=AuditLog(tmp_path / "audit.jsonl"),
        profile=None,
    )


# ─── Sentinel-first path ───────────────────────────────


class TestSentinelPreferred:
    def test_all_sentinels_present_skips_classifier(self, tmp_path, monkeypatch):
        runner = _make_runner(tmp_path)

        # Monkeypatch classifier so any invocation would hard-fail the test
        mock = MagicMock(side_effect=RuntimeError("classifier must not be called"))
        import set_orch.llm_verdict as lv
        monkeypatch.setattr(lv, "classify_verdict", mock)

        proposal = """# Fix Broken Login

## Problem
The login flow redirects to /dashboard before the session cookie is set.

**Impact:** high
**Fix-Scope:** single_file
**Target:** framework
**Confidence:** 0.9

## Solution
Await the cookie-set callback before redirecting.
"""
        diag = runner._parse_proposal(proposal, has_tasks=True)

        assert diag.impact == "high"
        assert diag.fix_scope == "single_file"
        assert diag.fix_target == "framework"
        assert 0.85 <= diag.confidence <= 0.95
        assert not mock.called


class TestConfidencePercentSentinel:
    def test_percent_value_normalised(self, tmp_path, monkeypatch):
        runner = _make_runner(tmp_path)
        mock = MagicMock(side_effect=RuntimeError("must not be called"))
        import set_orch.llm_verdict as lv
        monkeypatch.setattr(lv, "classify_verdict", mock)

        proposal = """**Impact:** medium
**Fix-Scope:** multi_file
**Target:** consumer
**Confidence:** 85
"""
        diag = runner._parse_proposal(proposal, has_tasks=True)
        assert 0.80 <= diag.confidence <= 0.90  # 85 → 0.85


# ─── Classifier fallback ─────────────────────────────


class TestClassifierFallback:
    def test_missing_sentinels_invoke_classifier(self, tmp_path, monkeypatch):
        runner = _make_runner(tmp_path)

        fake = ClassifierResult(
            verdict="fail",
            critical_count=1,
            raw_json={
                "verdict": "fail",
                "critical_count": 1,
                "impact": "high",
                "fix_scope": "multi_file",
                "fix_target": "framework",
                "confidence": 0.75,
            },
        )
        mock = MagicMock(return_value=fake)
        import set_orch.llm_verdict as lv
        monkeypatch.setattr(lv, "classify_verdict", mock)

        proposal = """# Fix it

## Problem
Something is broken.

## Solution
Fix it.
"""
        diag = runner._parse_proposal(proposal, has_tasks=True)
        assert mock.called
        assert diag.impact == "high"
        assert diag.fix_scope == "multi_file"
        assert diag.fix_target == "framework"

    def test_classifier_error_falls_back_to_heuristic(self, tmp_path, monkeypatch):
        runner = _make_runner(tmp_path)

        fake_error = ClassifierResult(
            verdict="fail",
            critical_count=1,
            error="timeout",
        )
        mock = MagicMock(return_value=fake_error)
        import set_orch.llm_verdict as lv
        monkeypatch.setattr(lv, "classify_verdict", mock)

        proposal = """# Fix

## Problem
This is a critical blocker — pipeline blocked.
"""
        diag = runner._parse_proposal(proposal, has_tasks=True)
        assert mock.called
        # Classifier errored → heuristic runs → "critical" word → high
        assert diag.impact == "high"
        # Confidence penalised by 0.1 for degraded extraction path
        assert diag.confidence <= 0.85

    def test_classifier_disabled_uses_heuristic(self, tmp_path, monkeypatch):
        runner = _make_runner(tmp_path)

        # Classifier import would fail with RuntimeError if called
        mock = MagicMock(side_effect=RuntimeError("must not be called"))
        import set_orch.llm_verdict as lv
        monkeypatch.setattr(lv, "classify_verdict", mock)

        proposal = """# Fix

## Problem
This is a minor warning.
"""
        diag = runner._parse_proposal(proposal, has_tasks=True, classifier_enabled=False)
        assert not mock.called
        assert diag.impact == "low"  # heuristic hit "minor"/"warning"


# ─── Word-boundary keyword heuristic ────────────────


class TestWordBoundaryHeuristic:
    def test_criticality_does_not_trigger_high(self, tmp_path, monkeypatch):
        runner = _make_runner(tmp_path)
        mock = MagicMock(side_effect=RuntimeError("must not be called"))
        import set_orch.llm_verdict as lv
        monkeypatch.setattr(lv, "classify_verdict", mock)

        proposal = """# Review

## Problem
We need to reassess the criticality of this area.
"""
        diag = runner._parse_proposal(proposal, has_tasks=True, classifier_enabled=False)
        # "criticality" must NOT trip the critical word match
        assert diag.impact != "high"

    def test_critical_word_boundary_triggers_high(self, tmp_path, monkeypatch):
        runner = _make_runner(tmp_path)
        mock = MagicMock(side_effect=RuntimeError("must not be called"))
        import set_orch.llm_verdict as lv
        monkeypatch.setattr(lv, "classify_verdict", mock)

        proposal = """# Review

## Problem
This is a critical bug in the merger that causes silent pass.
"""
        diag = runner._parse_proposal(proposal, has_tasks=True, classifier_enabled=False)
        assert diag.impact == "high"

    def test_framework_indicator_framework_target(self, tmp_path, monkeypatch):
        runner = _make_runner(tmp_path)
        mock = MagicMock(side_effect=RuntimeError("must not be called"))
        import set_orch.llm_verdict as lv
        monkeypatch.setattr(lv, "classify_verdict", mock)

        proposal = """# Problem

The dispatcher resets integration_e2e_retry_count on every redispatch,
so the retry limit never triggers.
"""
        diag = runner._parse_proposal(proposal, has_tasks=True, classifier_enabled=False)
        assert diag.fix_target == "framework"

    def test_consumer_only_default_target(self, tmp_path, monkeypatch):
        runner = _make_runner(tmp_path)
        mock = MagicMock(side_effect=RuntimeError("must not be called"))
        import set_orch.llm_verdict as lv
        monkeypatch.setattr(lv, "classify_verdict", mock)

        proposal = """# Problem

The user login redirects to the wrong page after password reset.
"""
        diag = runner._parse_proposal(proposal, has_tasks=True, classifier_enabled=False)
        assert diag.fix_target == "consumer"
