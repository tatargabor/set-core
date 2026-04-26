"""Tests for the agent-session decision helper used by `resume_change` and
the activity timeline event payloads.

`_decide_session_mode` is a pure function over `(loop_state.json + flags)` →
`{mode, reason, prior_session_id, session_age_min}`. It encodes the
guardrails for `claude --resume` reuse:

  - merge-rebase retries → never resume (main branch moved)
  - poisoned-stall recovery → never resume (the prior session crashed
    BECAUSE of context that's still in the preserved session)
  - session age > 60 min → fresh (compaction risk)
  - ≥3 prior resume failures → fresh
  - missing/mismatched/missing-session-id state file → fresh
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.dispatcher import _decide_session_mode


def _write_loop_state(tmp_path, **fields) -> str:
    """Write a minimal loop-state.json with given fields."""
    base = {
        "session_id": "sid-abc",
        "change": "my-change",
        "resume_failures": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(fields)
    p = os.path.join(tmp_path, "loop-state.json")
    with open(p, "w") as f:
        json.dump(base, f)
    return p


@pytest.fixture
def tmp_dir(tmp_path):
    return str(tmp_path)


class TestDecideSessionMode:
    def test_resume_eligible_when_all_guardrails_pass(self, tmp_dir):
        path = _write_loop_state(tmp_dir)
        d = _decide_session_mode(path, "my-change")
        assert d["mode"] == "resume"
        assert d["reason"] == ""
        assert d["prior_session_id"] == "sid-abc"
        assert d["session_age_min"] >= 0

    def test_merge_retry_forces_fresh(self, tmp_dir):
        path = _write_loop_state(tmp_dir)
        d = _decide_session_mode(path, "my-change", is_merge_retry=True)
        assert d["mode"] == "fresh"
        assert "merge_rebase_pending" in d["reason"]
        # Merge-retry gates the prior session out; we don't surface its id.
        assert d["prior_session_id"] == ""

    def test_poisoned_stall_forces_fresh(self, tmp_dir):
        path = _write_loop_state(tmp_dir)
        for stall_reason in (
            "token_runaway:1234",
            "context_overflow",
            "dead_running_agent_no_commits",
            "verify_timeout",
        ):
            d = _decide_session_mode(path, "my-change", stall_reason=stall_reason)
            assert d["mode"] == "fresh", stall_reason
            assert "poisoned_stall_recovery" in d["reason"], stall_reason

    def test_unknown_stall_reason_does_not_force_fresh(self, tmp_dir):
        """Only the documented poisoned prefixes force fresh; other
        stall reasons (e.g., manual pause) leave resume-eligibility
        unchanged."""
        path = _write_loop_state(tmp_dir)
        d = _decide_session_mode(path, "my-change", stall_reason="some_other_reason")
        assert d["mode"] == "resume"

    def test_no_loop_state_file_returns_fresh(self):
        d = _decide_session_mode("/nonexistent/loop-state.json", "my-change")
        assert d["mode"] == "fresh"
        assert d["reason"] == "no loop-state.json"
        assert d["prior_session_id"] == ""

    def test_corrupt_json_returns_fresh_with_error_reason(self, tmp_dir):
        p = os.path.join(tmp_dir, "loop-state.json")
        with open(p, "w") as f:
            f.write("{not valid json")
        d = _decide_session_mode(p, "my-change")
        assert d["mode"] == "fresh"
        assert d["reason"].startswith("state read error:")

    def test_missing_session_id_returns_fresh(self, tmp_dir):
        path = _write_loop_state(tmp_dir, session_id="")
        d = _decide_session_mode(path, "my-change")
        assert d["mode"] == "fresh"
        assert d["reason"] == "no prior session_id"

    def test_change_name_mismatch_returns_fresh_but_keeps_prior_id(self, tmp_dir):
        path = _write_loop_state(tmp_dir, change="other-change")
        d = _decide_session_mode(path, "my-change")
        assert d["mode"] == "fresh"
        assert "change name mismatch" in d["reason"]
        # Diagnostic value: surface the orphaned session id.
        assert d["prior_session_id"] == "sid-abc"

    def test_too_many_resume_failures_returns_fresh(self, tmp_dir):
        path = _write_loop_state(tmp_dir, resume_failures=3)
        d = _decide_session_mode(path, "my-change")
        assert d["mode"] == "fresh"
        assert "too many prior resume failures" in d["reason"]

    def test_session_too_old_returns_fresh(self, tmp_dir):
        old = (datetime.now(timezone.utc) - timedelta(minutes=120)).isoformat()
        path = _write_loop_state(tmp_dir, started_at=old)
        d = _decide_session_mode(path, "my-change")
        assert d["mode"] == "fresh"
        assert "session too old" in d["reason"]
        assert d["session_age_min"] >= 60

    def test_session_age_at_threshold_is_resume(self, tmp_dir):
        # 30 min < 60 min cutoff
        recent = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        path = _write_loop_state(tmp_dir, started_at=recent)
        d = _decide_session_mode(path, "my-change")
        assert d["mode"] == "resume"
