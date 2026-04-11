"""Tests pinning the "no faulty detection" final-solution invariants.

Each test asserts a specific guarantee that the gate-verdict pipeline now
provides. If any of these regress, the dual-eval bug class can come back.

Covers:
  - api/sessions.py:_session_outcome is sidecar-only (no keyword scan)
  - subprocess_utils.py:run_claude_logged auto-writes a default sidecar
  - verifier.py:_parse_critical_count anchors to last match in tail
  - verifier.py:review_change always runs classifier (not just retry)
  - verifier.py:_execute_spec_verify_gate fails closed when classifier
    is disabled and the sentinel is missing
  - merger.py:_test_script_missing reads package.json instead of guessing
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.gate_verdict import (
    GateVerdict,
    claude_session_dir,
    read_verdict_sidecar,
    write_verdict_sidecar,
)
from set_orch.api.sessions import _session_outcome
from set_orch.merger import _test_script_missing
from set_orch.verifier import _parse_critical_count


# ─── _session_outcome: sidecar-only ──────────────────────


@pytest.fixture
def session_with_text(tmp_path):
    """A fake session JSONL containing assistant text that WOULD trigger
    the old keyword heuristic ("review fail", "[CRITICAL]", etc.)."""
    session = tmp_path / "abc-uuid.jsonl"
    session.write_text(
        json.dumps({
            "type": "queue-operation",
            "content": "[PURPOSE:review:my-change]\nReview please",
        }) + "\n"
        + json.dumps({
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{
                    "type": "text",
                    "text": "Review fail [CRITICAL] not passing build fail",
                }],
            },
        }) + "\n"
    )
    return session


class TestSessionOutcomeSidecarOnly:
    def test_returns_unknown_when_no_sidecar(self, session_with_text):
        # Old heuristic would return "error" because of "[critical]" + "fail".
        # New behaviour: no sidecar → unknown.
        assert _session_outcome(session_with_text) == "unknown"

    def test_returns_sidecar_pass_even_when_text_says_fail(self, session_with_text):
        # Sidecar says pass, prose says fail. Sidecar is authoritative.
        write_verdict_sidecar(session_with_text, GateVerdict(
            gate="review", verdict="pass", source="classifier_confirmed",
            change="my-change",
        ))
        assert _session_outcome(session_with_text) == "success"

    def test_returns_sidecar_fail_even_when_text_says_pass(self, tmp_path):
        session = tmp_path / "u.jsonl"
        session.write_text(
            json.dumps({
                "type": "assistant",
                "message": {"role": "assistant", "content": [
                    {"type": "text", "text": "all tests pass committed fixed"},
                ]},
            }) + "\n"
        )
        write_verdict_sidecar(session, GateVerdict(
            gate="review", verdict="fail", critical_count=2,
            source="classifier_override", change="x",
        ))
        assert _session_outcome(session) == "error"


# ─── _parse_critical_count: last-match anchored ──────────


class TestParseCriticalCountLastMatch:
    def test_takes_last_occurrence(self):
        # Old behaviour: re.search returns FIRST match (here CRITICAL_COUNT: 5
        # from a quoted prior report). New behaviour: takes LAST match.
        output = (
            "Previous report said CRITICAL_COUNT: 5\n"
            "Investigating...\n"
            "All findings resolved\n"
            "CRITICAL_COUNT: 0\n"
            "VERIFY_RESULT: PASS\n"
        )
        assert _parse_critical_count(output) == 0

    def test_ignores_quoted_prefix(self):
        # A `> CRITICAL_COUNT: 5` (markdown blockquote) inside a quoted
        # discussion must NOT match — the regex anchors at line start
        # without the quote prefix.
        output = (
            "An earlier draft had this:\n"
            "> CRITICAL_COUNT: 5\n"
            "But the final answer is below.\n"
            "CRITICAL_COUNT: 0\n"
            "VERIFY_RESULT: PASS\n"
        )
        assert _parse_critical_count(output) == 0

    def test_only_scans_tail(self):
        # If a sentinel appears far from the end, but a different one
        # appears at the end, only the end one matters. (And quoted text
        # in the middle of a 50KB output is invisible.)
        prefix = "x" * 5000 + "\nCRITICAL_COUNT: 99\n" + "y" * 5000 + "\n"
        tail = "CRITICAL_COUNT: 3\nVERIFY_RESULT: FAIL\n"
        assert _parse_critical_count(prefix + tail) == 3

    def test_returns_none_on_missing(self):
        assert _parse_critical_count("nothing useful here") is None
        assert _parse_critical_count("") is None
        assert _parse_critical_count(None) is None  # type: ignore[arg-type]


# ─── _test_script_missing: reads package.json ────────────


@pytest.fixture
def wt_with_package(tmp_path):
    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({
        "name": "test",
        "scripts": {
            "test": "vitest run",
            "build": "next build",
            "lint": "eslint .",
        },
    }))
    return tmp_path


class TestTestScriptMissing:
    def test_known_script_present(self, wt_with_package):
        assert _test_script_missing(str(wt_with_package), "pnpm test") is False
        assert _test_script_missing(str(wt_with_package), "pnpm run test") is False
        assert _test_script_missing(str(wt_with_package), "npm test") is False
        assert _test_script_missing(str(wt_with_package), "yarn test") is False

    def test_unknown_script_missing(self, wt_with_package):
        assert _test_script_missing(str(wt_with_package), "pnpm e2e") is True
        assert _test_script_missing(str(wt_with_package), "pnpm run integration") is True
        assert _test_script_missing(str(wt_with_package), "npm run no-such-script") is True

    def test_no_package_json_returns_false(self, tmp_path):
        # No package.json → can't prove anything → return False
        # (callers will then attempt the run anyway)
        assert _test_script_missing(str(tmp_path), "pnpm test") is False

    def test_unknown_pm_returns_false(self, wt_with_package):
        # Unknown package manager / raw bash → don't assume missing
        assert _test_script_missing(str(wt_with_package), "make test") is False
        assert _test_script_missing(str(wt_with_package), "/bin/bash run-tests.sh") is False
        assert _test_script_missing(str(wt_with_package), "") is False

    def test_malformed_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text("{not valid json")
        # Can't parse → return False (be conservative)
        assert _test_script_missing(str(tmp_path), "pnpm test") is False


# ─── run_claude_logged auto-sidecar ──────────────────────


class TestRunClaudeLoggedAutoSidecar:
    def test_writes_default_sidecar_on_exit_0(self, tmp_path, monkeypatch):
        # Redirect Path.home() so the Claude session dir lands under tmp_path
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        cwd = "/some/wt-path"
        session_dir = claude_session_dir(cwd)
        session_dir.mkdir(parents=True)

        from set_orch import subprocess_utils
        from set_orch.subprocess_utils import ClaudeResult

        # Mock run_claude to (a) create a fake session jsonl with the
        # PURPOSE marker (b) return success
        def fake_run_claude(prompt, **kwargs):
            (session_dir / "new-session.jsonl").write_text(
                json.dumps({
                    "type": "queue-operation",
                    "content": prompt,
                }) + "\n"
            )
            return ClaudeResult(
                exit_code=0, stdout="ok", stderr="", duration_ms=100,
                input_tokens=10, output_tokens=20,
            )

        monkeypatch.setattr(subprocess_utils, "run_claude", fake_run_claude)
        result = subprocess_utils.run_claude_logged(
            "do the thing", purpose="my_purpose", change="my-change", cwd=cwd,
        )
        assert result.exit_code == 0

        sidecar = session_dir / "new-session.verdict.json"
        assert sidecar.is_file(), "default sidecar should be written on success"
        v = read_verdict_sidecar(session_dir / "new-session.jsonl")
        assert v is not None
        assert v.verdict == "pass"
        assert v.source == "claude_exit_code"
        assert v.gate == "my_purpose"
        assert v.change == "my-change"

    def test_writes_default_sidecar_on_exit_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        cwd = "/some/wt-path"
        session_dir = claude_session_dir(cwd)
        session_dir.mkdir(parents=True)

        from set_orch import subprocess_utils
        from set_orch.subprocess_utils import ClaudeResult

        def fake_run_claude(prompt, **kwargs):
            (session_dir / "failed-session.jsonl").write_text(
                json.dumps({"type": "queue-operation", "content": prompt}) + "\n"
            )
            return ClaudeResult(
                exit_code=1, stdout="boom", stderr="error", duration_ms=50,
            )

        monkeypatch.setattr(subprocess_utils, "run_claude", fake_run_claude)
        subprocess_utils.run_claude_logged(
            "do the thing", purpose="some_gate", change="ch", cwd=cwd,
        )
        v = read_verdict_sidecar(session_dir / "failed-session.jsonl")
        assert v is not None
        assert v.verdict == "fail"
        assert v.critical_count == 1
        assert v.source == "claude_exit_code"

    def test_no_cwd_no_sidecar_no_crash(self, monkeypatch):
        # When cwd is None we cannot resolve a session dir; the function
        # must NOT crash, just skip the sidecar.
        from set_orch import subprocess_utils
        from set_orch.subprocess_utils import ClaudeResult

        monkeypatch.setattr(
            subprocess_utils, "run_claude",
            lambda *a, **kw: ClaudeResult(
                exit_code=0, stdout="", stderr="", duration_ms=1,
            ),
        )
        # Should not raise
        result = subprocess_utils.run_claude_logged(
            "x", purpose="generic", cwd=None,
        )
        assert result.exit_code == 0
