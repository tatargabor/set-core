"""Tests for the review gate classifier fallback.

See OpenSpec change: llm-verdict-classifier

Background
----------
Two silent-pass incidents merged CRITICAL findings because the review
gate body-regex parser didn't recognize the retry-review format. These
fossil tests preserve the exact review outputs from those incidents and
prove that the classifier fallback now catches them.

Fixtures
--------
- fixtures/review_output_micro_create_task_2026_04_11.txt — the full
  review text from /home/tg/demo/micro/set/orchestration/python.log
  line 5176. Contains `### Finding N:` + `**NOT_FIXED** [CRITICAL]` × 3.
- fixtures/review_output_minishop_0410_product_catalog_attempt4.txt —
  minishop_0410/product-catalog attempt 4 review output. Contains a
  markdown table row + `**REVIEW BLOCKED** — 1 unique critical issue
  remains` summary.
- fixtures/review_output_first_round_inline_format.txt — a clean
  first-round review with `ISSUE: [MEDIUM]` + `ISSUE: [LOW]` + a
  `REVIEW PASS` narrative line. Exercises the fast-path without
  requiring the classifier.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch import verifier
from set_orch.llm_verdict import ClassifierResult


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return f.read()


# ─── _parse_review_issues fast-path ──────────────────────────


class TestParseReviewIssuesFastPath:
    """The fast-path regex handles the first-round `ISSUE: [TAG]` format."""

    def test_first_round_inline_format_parses_correctly(self):
        text = _load_fixture("review_output_first_round_inline_format.txt")
        issues = verifier._parse_review_issues(text)

        # 2 MEDIUM + 1 LOW
        assert len(issues) == 3
        severities = [i["severity"] for i in issues]
        assert severities.count("MEDIUM") == 2
        assert severities.count("LOW") == 1
        assert not any(i["severity"] == "CRITICAL" for i in issues)

    def test_retry_review_header_format_returns_zero(self):
        """This is the bug — the fossil format returns 0 issues on the fast-path.
        The classifier fallback is what catches it."""
        text = _load_fixture("review_output_micro_create_task_2026_04_11.txt")
        issues = verifier._parse_review_issues(text)
        assert len(issues) == 0  # fast-path misses the header format

    def test_inline_critical_tag_single_source_severity(self):
        """Severity comes ONLY from the inline [TAG] — not from narrative body."""
        text = """
**ISSUE: [LOW] Minor naming nit**
FILE: src/foo.ts
LINE: 42
FIX: rename to camelCase

The issue is not critical but it would improve readability considerably.
"""
        issues = verifier._parse_review_issues(text)
        assert len(issues) == 1
        assert issues[0]["severity"] == "LOW"  # the word "critical" in body is IGNORED


# ─── classifier fallback in review_change ───────────────────


def _fake_classify(verdict="fail", critical=0, findings=None, error=None, elapsed_ms=100):
    return ClassifierResult(
        verdict=verdict,
        critical_count=critical,
        high_count=0,
        medium_count=0,
        low_count=0,
        findings=findings or [],
        raw_json={},
        error=error,
        elapsed_ms=elapsed_ms,
    )


def _patch_review_pipeline(monkeypatch, review_output: str, classifier_result: ClassifierResult = None,
                            classifier_enabled: bool = True):
    """Monkeypatch review_change's dependencies so we can unit test the flow
    without a real Claude CLI or git diff.

    Returns the mock classifier so tests can assert it was / was not called.
    """
    from set_orch import verifier as vf
    from set_orch.subprocess_utils import CommandResult

    # Fake diff
    monkeypatch.setattr(vf, "_get_merge_base", lambda wt: "base")
    monkeypatch.setattr(vf, "run_git", lambda *a, **kw: CommandResult(0, "fake diff", "", 10, False))
    monkeypatch.setattr(vf, "_prioritize_diff_for_review", lambda x: x)
    monkeypatch.setattr(vf, "build_req_review_section", lambda *a, **kw: "")
    monkeypatch.setattr(vf, "_load_security_rules", lambda *a, **kw: "")

    # Fake template render
    monkeypatch.setattr(
        vf, "run_command",
        lambda *a, **kw: CommandResult(0, "rendered prompt", "", 10, False),
    )

    # Fake primary review LLM call
    monkeypatch.setattr(
        vf, "run_claude_logged",
        lambda *a, **kw: CommandResult(0, review_output, "", 5000, False),
    )

    # Fake classifier_enabled lookup
    monkeypatch.setattr(vf, "_classifier_enabled", lambda state_file: classifier_enabled)

    # Fake classifier itself
    mock_classify = MagicMock(return_value=classifier_result or _fake_classify(verdict="pass"))
    import set_orch.llm_verdict as lv
    monkeypatch.setattr(lv, "classify_verdict", mock_classify)

    return mock_classify


class TestReviewGateSilentPassFossil:
    """Regression tests capturing the two production silent-pass incidents."""

    def test_micro_create_task_fossil_blocked_by_classifier(self, monkeypatch):
        """The micro/create-task 2026-04-11 review merged 3 CRITICAL findings.
        With the classifier fallback, the same input should now block."""
        review_output = _load_fixture("review_output_micro_create_task_2026_04_11.txt")

        classifier_result = _fake_classify(
            verdict="fail",
            critical=3,
            findings=[
                {"severity": "CRITICAL", "summary": "Missing waitUntil: networkidle"},
                {"severity": "CRITICAL", "summary": "Missing blank-input validation test"},
                {"severity": "CRITICAL", "summary": "No title length limit"},
            ],
        )
        mock_classify = _patch_review_pipeline(monkeypatch, review_output, classifier_result)

        result = verifier.review_change(
            change_name="create-task",
            wt_path="/tmp/fake-wt",
            scope="add a create-task form + server action",
            review_model="sonnet",
            state_file="/tmp/fake-state.json",
            design_snapshot_dir="",
        )

        # Classifier MUST have been invoked (fast-path returned 0)
        assert mock_classify.called, "classifier must run when fast-path finds 0 issues on a long retry review"
        # Review gate result: classifier critical count > 0 → has_critical True
        assert result.has_critical is True, (
            "the micro/create-task 2026-04-11 fossil must trigger the classifier fallback "
            "and block the merge — otherwise silent pass recurs"
        )

    def test_minishop_0410_product_catalog_fossil_blocked_by_classifier(self, monkeypatch):
        review_output = _load_fixture(
            "review_output_minishop_0410_product_catalog_attempt4.txt"
        )
        classifier_result = _fake_classify(
            verdict="fail",
            critical=1,
            findings=[
                {"severity": "CRITICAL", "summary": "E2E test file still does not exist"},
            ],
        )
        mock_classify = _patch_review_pipeline(monkeypatch, review_output, classifier_result)

        result = verifier.review_change(
            change_name="product-catalog",
            wt_path="/tmp/fake-wt",
            scope="storefront product catalog",
            review_model="sonnet",
            state_file="/tmp/fake-state.json",
            design_snapshot_dir="",
        )

        assert mock_classify.called
        assert result.has_critical is True


class TestReviewGateFirstRoundFastPath:
    """When the fast-path handles the format cleanly, classifier is skipped."""

    def test_first_round_inline_format_skips_classifier(self, monkeypatch):
        review_output = _load_fixture("review_output_first_round_inline_format.txt")
        # Classifier would hard-fail if called — this proves it is NOT called
        mock_classify = _patch_review_pipeline(
            monkeypatch, review_output,
            classifier_result=_fake_classify(critical=99),  # would block if called
        )

        result = verifier.review_change(
            change_name="clean-change",
            wt_path="/tmp/fake-wt",
            scope="clean scope",
            review_model="sonnet",
            state_file="/tmp/fake-state.json",
            design_snapshot_dir="",
        )

        # Fast-path finds 2 MEDIUM + 1 LOW — no CRITICAL → has_critical False
        assert result.has_critical is False
        # Classifier was NOT invoked (fast-path already found some issues,
        # and none were CRITICAL, so the classifier never runs)
        assert not mock_classify.called, (
            "classifier should be skipped when fast-path finds non-zero findings "
            "(even if they are all below CRITICAL)"
        )


class TestReviewGateClassifierDisabled:
    def test_classifier_disabled_keeps_old_behavior(self, monkeypatch):
        """When the directive is False, the classifier is skipped entirely
        and the fast-path is the only verdict source. The micro fossil would
        silently pass here — that is the pre-fix behavior operators can opt
        back into if Sonnet cost is a concern."""
        review_output = _load_fixture("review_output_micro_create_task_2026_04_11.txt")
        mock_classify = _patch_review_pipeline(
            monkeypatch, review_output,
            classifier_result=_fake_classify(critical=3),
            classifier_enabled=False,
        )

        result = verifier.review_change(
            change_name="create-task",
            wt_path="/tmp/fake-wt",
            scope="scope",
            review_model="sonnet",
            state_file="/tmp/fake-state.json",
            design_snapshot_dir="",
        )

        # With classifier disabled, the fossil slips through (known-bad, opt-in)
        assert result.has_critical is False
        assert not mock_classify.called


class TestReviewGateClassifierErrorFallThrough:
    def test_classifier_error_falls_through_with_fast_path_verdict(self, monkeypatch):
        """If the classifier fails (timeout, JSON error) the fast-path result
        is used — backward compatible with the pre-fix state."""
        review_output = _load_fixture("review_output_micro_create_task_2026_04_11.txt")
        classifier_error = _fake_classify(verdict="fail", critical=1, error="timeout")
        mock_classify = _patch_review_pipeline(monkeypatch, review_output, classifier_error)

        result = verifier.review_change(
            change_name="create-task",
            wt_path="/tmp/fake-wt",
            scope="scope",
            review_model="sonnet",
            state_file="/tmp/fake-state.json",
            design_snapshot_dir="",
        )

        # Classifier was called but errored — fast-path verdict stands
        assert mock_classify.called
        assert result.has_critical is False  # fast-path said clean


class TestReviewPassRegexRemoved:
    def test_quoted_review_pass_does_not_short_circuit(self, monkeypatch):
        """A review output that QUOTES the phrase "REVIEW PASS" but then
        finds new CRITICAL issues must fail — the old regex short-circuit
        would have passed on the quoted phrase."""
        review_output = (
            'The previous review said "REVIEW PASS — no critical issues found" '
            "but I now find new problems on this retry:\n\n"
            "**ISSUE: [CRITICAL] New security hole introduced by the latest patch**\n"
            "FILE: src/app/actions.ts\n"
            "LINE: 42\n"
            "FIX: Add input validation before calling db\n"
        )
        # Classifier should not even need to run — fast-path finds the CRITICAL
        mock_classify = _patch_review_pipeline(
            monkeypatch, review_output,
            classifier_result=_fake_classify(verdict="pass"),
        )

        result = verifier.review_change(
            change_name="quoted",
            wt_path="/tmp/fake-wt",
            scope="scope",
            review_model="sonnet",
            state_file="/tmp/fake-state.json",
            design_snapshot_dir="",
        )

        assert result.has_critical is True  # new CRITICAL detected
        # Classifier not needed — fast-path already found it
        assert not mock_classify.called
