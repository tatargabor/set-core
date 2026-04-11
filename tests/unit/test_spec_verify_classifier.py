"""Tests for spec-verify gate classifier fallback.

See OpenSpec change: llm-verdict-classifier

When the primary verify LLM fails to emit the VERIFY_RESULT/CRITICAL_COUNT
sentinel lines, the old behavior was to pass with an [ANOMALY] WARNING
(backward-compat escape hatch). With the classifier fallback enabled,
we instead run a second Sonnet pass on the verify output to extract a
structured verdict.

Four cases are tested:
1. Classifier confirms 0 critical → pass with WARNING
2. Classifier finds critical → fail with retry_context listing findings
3. Classifier errors out → fail closed (no trustworthy signal)
4. Classifier disabled → old backward-compat pass with [ANOMALY]
"""

import os
import shutil
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch import verifier
from set_orch.llm_verdict import ClassifierResult
from set_orch.state import Change
from set_orch.subprocess_utils import CommandResult


def _fake_classify(*, critical=0, error=None, findings=None, elapsed_ms=100):
    return ClassifierResult(
        verdict="fail" if critical > 0 or error else "pass",
        critical_count=critical,
        high_count=0,
        medium_count=0,
        low_count=0,
        findings=findings or [],
        raw_json={},
        error=error,
        elapsed_ms=elapsed_ms,
    )


def _patch_spec_verify(monkeypatch, verify_output: str, *, classifier_result=None,
                       classifier_enabled=True):
    """Set up _execute_spec_verify_gate for a unit test run.

    - Bypasses the shutil.which("claude") guard
    - Makes run_claude_logged return the given verify_output
    - Patches _classifier_enabled and classify_verdict
    """
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/claude")
    monkeypatch.setattr(
        verifier, "run_claude_logged",
        lambda *a, **kw: CommandResult(0, verify_output, "", 5000, False),
    )
    monkeypatch.setattr(verifier, "_classifier_enabled", lambda _: classifier_enabled)

    mock_classify = MagicMock(return_value=classifier_result or _fake_classify())
    import set_orch.llm_verdict as lv
    monkeypatch.setattr(lv, "classify_verdict", mock_classify)

    return mock_classify


def _make_change():
    return Change(name="test-change", scope="test scope", status="verifying")


class TestMissingSentinelClassifierPass:
    def test_classifier_confirms_no_critical_passes_with_warning(self, monkeypatch, caplog):
        import logging
        caplog.set_level(logging.WARNING, logger="set_orch.verifier")

        verify_output = "Looks good to me, everything seems fine but no VERIFY_RESULT line."
        mock_classify = _patch_spec_verify(
            monkeypatch, verify_output,
            classifier_result=_fake_classify(critical=0),
        )

        result = verifier._execute_spec_verify_gate(
            "test-change", _make_change(), "/tmp/fake-wt",
            state_file="/tmp/fake-state.json",
        )

        assert result.status == "pass"
        assert mock_classify.called
        anomaly_warnings = [r for r in caplog.records if "[ANOMALY]" in r.message]
        assert anomaly_warnings, "expected [ANOMALY] warning log for missing sentinel"


class TestMissingSentinelClassifierFail:
    def test_classifier_finds_critical_blocks(self, monkeypatch):
        verify_output = "I found that REQ-001 is not implemented but I forgot to write the sentinel."
        findings = [
            {"severity": "CRITICAL", "summary": "REQ-001 missing implementation", "file": "src/foo.ts", "line": "42"},
        ]
        mock_classify = _patch_spec_verify(
            monkeypatch, verify_output,
            classifier_result=_fake_classify(critical=1, findings=findings),
        )

        result = verifier._execute_spec_verify_gate(
            "test-change", _make_change(), "/tmp/fake-wt",
            state_file="/tmp/fake-state.json",
        )

        assert result.status == "fail"
        assert mock_classify.called
        assert "classifier" in (result.retry_context or "").lower()
        assert "REQ-001 missing implementation" in (result.retry_context or "")


class TestMissingSentinelClassifierError:
    def test_classifier_error_fails_closed(self, monkeypatch):
        verify_output = "Some output without sentinel"
        mock_classify = _patch_spec_verify(
            monkeypatch, verify_output,
            classifier_result=_fake_classify(error="timeout"),
        )

        result = verifier._execute_spec_verify_gate(
            "test-change", _make_change(), "/tmp/fake-wt",
            state_file="/tmp/fake-state.json",
        )

        assert result.status == "fail"
        assert mock_classify.called
        assert "sentinel" in (result.retry_context or "").lower()


class TestMissingSentinelClassifierDisabled:
    def test_backward_compat_pass_when_disabled(self, monkeypatch, caplog):
        import logging
        caplog.set_level(logging.WARNING, logger="set_orch.verifier")

        verify_output = "No sentinel, disabled classifier"
        mock_classify = _patch_spec_verify(
            monkeypatch, verify_output,
            classifier_enabled=False,
        )

        result = verifier._execute_spec_verify_gate(
            "test-change", _make_change(), "/tmp/fake-wt",
            state_file="/tmp/fake-state.json",
        )

        assert result.status == "pass"
        assert not mock_classify.called
        anomaly_warnings = [r for r in caplog.records if "[ANOMALY]" in r.message]
        assert anomaly_warnings


class TestExistingSentinelPaths:
    def test_verify_result_pass_not_affected(self, monkeypatch):
        verify_output = "All good.\nCRITICAL_COUNT: 0\nVERIFY_RESULT: PASS\n"
        mock_classify = _patch_spec_verify(
            monkeypatch, verify_output,
            classifier_result=_fake_classify(critical=99),  # would block if called
        )

        result = verifier._execute_spec_verify_gate(
            "test-change", _make_change(), "/tmp/fake-wt",
            state_file="/tmp/fake-state.json",
        )

        assert result.status == "pass"
        # Classifier not invoked when the sentinel is present
        assert not mock_classify.called

    def test_verify_result_fail_with_critical_not_affected(self, monkeypatch):
        verify_output = "Problems found.\nCRITICAL_COUNT: 2\nVERIFY_RESULT: FAIL\n"
        mock_classify = _patch_spec_verify(
            monkeypatch, verify_output,
            classifier_result=_fake_classify(critical=99),
        )

        result = verifier._execute_spec_verify_gate(
            "test-change", _make_change(), "/tmp/fake-wt",
            state_file="/tmp/fake-state.json",
        )

        assert result.status == "fail"
        assert not mock_classify.called  # sentinel-driven, classifier not invoked

    def test_verify_result_fail_with_zero_critical_downgrades(self, monkeypatch):
        verify_output = "Warnings only.\nCRITICAL_COUNT: 0\nVERIFY_RESULT: FAIL\n"
        mock_classify = _patch_spec_verify(
            monkeypatch, verify_output,
            classifier_result=_fake_classify(critical=99),
        )

        result = verifier._execute_spec_verify_gate(
            "test-change", _make_change(), "/tmp/fake-wt",
            state_file="/tmp/fake-state.json",
        )

        assert result.status == "pass"  # downgraded — no critical
        assert not mock_classify.called
