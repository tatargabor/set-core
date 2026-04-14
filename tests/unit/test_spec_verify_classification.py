"""Regression tests for _execute_spec_verify_gate's three-category classification.

See OpenSpec change: fix-retry-context-signal-loss (Bug B).

Before the fix, any `exit_code != 0` from the claude CLI was unconditionally
mapped to a spec_verify gate FAIL, consuming a retry slot and re-dispatching
the impl agent with the LLM's own stream-json transcript as "retry_context".
This conflated:
  - LLM produced VERIFY_RESULT: FAIL (real spec violation)    — correct FAIL
  - LLM hit --max-turns 40 without verdict (infra failure)    — FALSE FAIL
  - Subprocess timeout (infra failure)                        — FALSE FAIL

The new three-category classification distinguishes these and abstains on
infrastructure failures (gate status=skipped, no retry slot consumed).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.verifier import _classify_spec_verify_outcome
from set_orch.subprocess_utils import ClaudeResult


def _mk(exit_code=0, stdout="", timed_out=False, duration_ms=100) -> ClaudeResult:
    return ClaudeResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr="",
        duration_ms=duration_ms,
        timed_out=timed_out,
    )


# ── _classify_spec_verify_outcome unit tests ─────────────────────────


def test_verify_result_pass_is_verdict():
    """AC-8: VERIFY_RESULT: PASS is authoritative — category=verdict regardless of exit_code."""
    r = _mk(exit_code=0, stdout="final report\n\nCRITICAL_COUNT: 0\nVERIFY_RESULT: PASS")
    assert _classify_spec_verify_outcome(r, r.stdout) == ("verdict", "")


def test_verify_result_pass_with_nonzero_exit_still_verdict():
    """Sentinel is authoritative over exit_code (e.g., post-processing glitches)."""
    r = _mk(exit_code=1, stdout="VERIFY_RESULT: PASS\nCRITICAL_COUNT: 0")
    # The classifier sees the sentinel and returns verdict even though exit_code != 0
    assert _classify_spec_verify_outcome(r, r.stdout)[0] == "verdict"


def test_verify_result_fail_is_verdict():
    """AC-10: VERIFY_RESULT: FAIL with exit_code != 0 is still verdict (not infra)."""
    r = _mk(
        exit_code=1,
        stdout="report body\n\nCRITICAL_COUNT: 2\nVERIFY_RESULT: FAIL",
    )
    assert _classify_spec_verify_outcome(r, r.stdout) == ("verdict", "")


def test_max_turns_without_sentinel_is_infra():
    """Raw stream-json with terminal_reason=max_turns and no sentinel = infra."""
    stream_json = (
        '[{"type":"system","subtype":"init"},'
        '{"type":"assistant","message":{"content":[]}},'
        '{"terminal_reason":"max_turns","errors":["Reached maximum number of turns (40)"]}]'
    )
    r = _mk(exit_code=1, stdout=stream_json)
    assert _classify_spec_verify_outcome(r, r.stdout) == ("infra", "max_turns")


def test_subprocess_timeout_is_infra():
    """timed_out=True with empty or partial stdout = infra (not code fault)."""
    r = _mk(exit_code=-1, stdout="", timed_out=True, duration_ms=900000)
    assert _classify_spec_verify_outcome(r, r.stdout) == ("infra", "timeout")


def test_timeout_outranks_max_turns():
    """If both timed_out and max_turns apply, timeout takes precedence."""
    r = _mk(
        exit_code=-1,
        stdout='{"terminal_reason":"max_turns"}',
        timed_out=True,
    )
    assert _classify_spec_verify_outcome(r, r.stdout) == ("infra", "timeout")


def test_no_sentinel_no_infra_cause_is_ambiguous():
    """No sentinel + no detectable infra reason falls through to classifier."""
    r = _mk(
        exit_code=0,
        stdout="some report text that forgot to emit the sentinel",
    )
    assert _classify_spec_verify_outcome(r, r.stdout) == ("ambiguous", "")


def test_quoted_max_turns_still_detected_as_infra():
    """Even if max_turns appears inside a quoted string, as long as the JSON
    field name pattern matches, treat as infra. This is robust against partial
    truncation of the stream-json output.
    """
    partial = '...truncated..."terminal_reason":"max_turns","errors"...'
    r = _mk(exit_code=1, stdout=partial)
    assert _classify_spec_verify_outcome(r, r.stdout) == ("infra", "max_turns")


# ── GateResult infra_fail plumbing ────────────────────────────────────


def test_gate_result_infra_fail_defaults_false():
    """GateResult.infra_fail defaults to False to preserve back-compat."""
    from set_orch.gate_runner import GateResult
    r = GateResult("spec_verify", "pass")
    assert r.infra_fail is False
    assert r.terminal_reason == ""


def test_gate_result_infra_fail_can_be_set():
    """The infra-failure path sets infra_fail=True + terminal_reason."""
    from set_orch.gate_runner import GateResult
    r = GateResult("spec_verify", "skipped")
    r.infra_fail = True
    r.terminal_reason = "max_turns"
    assert r.infra_fail is True
    assert r.terminal_reason == "max_turns"
