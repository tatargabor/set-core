"""Tests for `_read_session_iterations` — projects ralph-loop iterations
into a session-specific sub-row list for the Tokens / LLM Call Log.

The iteration → session attribution rule:
  - explicit `iter.session_id` matches the session file UUID → include
  - missing `iter.session_id` (legacy snapshots) → fall back to top-level
    `session_id` (covers single-session changes correctly)
  - mismatched UUID → exclude (iter belongs to a different session file)
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.api.orchestration import _read_session_iterations
from set_orch.state import Change, OrchestratorState, save_state


def _state_with_change(tmp_path: Path, change_name="c1"):
    wt = tmp_path / f"wt-{change_name}"
    (wt / ".set").mkdir(parents=True, exist_ok=True)
    return OrchestratorState(
        status="running",
        changes=[Change(name=change_name, worktree_path=str(wt))],
    ), wt


def _write_iters(wt: Path, iterations: list, top_sid: str = ""):
    p = wt / ".set" / "loop-state.json"
    p.write_text(json.dumps({
        "session_id": top_sid,
        "iterations": iterations,
    }))


class TestReadSessionIterations:
    def test_returns_iters_with_matching_per_iter_session_id(self, tmp_path):
        state, wt = _state_with_change(tmp_path)
        _write_iters(wt, [
            {"n": 1, "session_id": "uuid-A", "started": "t1", "ended": "t2",
             "resumed": False, "tokens_used": 100},
            {"n": 2, "session_id": "uuid-A", "started": "t3", "ended": "t4",
             "resumed": True, "tokens_used": 50},
            {"n": 3, "session_id": "uuid-B", "started": "t5", "ended": "t6",
             "resumed": False, "tokens_used": 80},
        ])
        result = _read_session_iterations(state, "c1", "uuid-A")
        assert [r["n"] for r in result] == [1, 2]
        assert result[0]["resumed"] is False
        assert result[1]["resumed"] is True

    def test_falls_back_to_top_level_session_id_when_iter_lacks_one(
        self, tmp_path,
    ):
        """Legacy snapshots (pre per-iter session_id): all iters belong
        to whichever session the top-level `session_id` currently names."""
        state, wt = _state_with_change(tmp_path)
        _write_iters(wt, [
            {"n": 1, "started": "t1", "ended": "t2", "resumed": False,
             "tokens_used": 100},
            {"n": 2, "started": "t3", "ended": "t4", "resumed": True,
             "tokens_used": 50},
        ], top_sid="legacy-sid")
        result = _read_session_iterations(state, "c1", "legacy-sid")
        assert [r["n"] for r in result] == [1, 2]

    def test_returns_empty_for_unknown_session(self, tmp_path):
        state, wt = _state_with_change(tmp_path)
        _write_iters(wt, [
            {"n": 1, "session_id": "uuid-A", "started": "t1", "resumed": False},
        ])
        assert _read_session_iterations(state, "c1", "uuid-other") == []

    def test_returns_empty_for_unknown_change(self, tmp_path):
        state, wt = _state_with_change(tmp_path)
        _write_iters(wt, [
            {"n": 1, "session_id": "uuid-A", "started": "t1"},
        ])
        assert _read_session_iterations(state, "no-such", "uuid-A") == []

    def test_returns_empty_when_loop_state_missing(self, tmp_path):
        state, wt = _state_with_change(tmp_path)
        # Don't write loop-state.json.
        assert _read_session_iterations(state, "c1", "uuid-A") == []

    def test_returns_empty_when_loop_state_corrupt(self, tmp_path):
        state, wt = _state_with_change(tmp_path)
        (wt / ".set" / "loop-state.json").write_text("{not json")
        assert _read_session_iterations(state, "c1", "uuid-A") == []

    def test_handles_missing_state(self):
        assert _read_session_iterations(None, "c1", "uuid-A") == []

    def test_iterations_sorted_by_n(self, tmp_path):
        state, wt = _state_with_change(tmp_path)
        _write_iters(wt, [
            {"n": 3, "session_id": "uuid-A"},
            {"n": 1, "session_id": "uuid-A"},
            {"n": 2, "session_id": "uuid-A"},
        ])
        result = _read_session_iterations(state, "c1", "uuid-A")
        assert [r["n"] for r in result] == [1, 2, 3]

    def test_token_fields_coerced_to_int(self, tmp_path):
        """Robust against bash writing string token counts."""
        state, wt = _state_with_change(tmp_path)
        _write_iters(wt, [
            {"n": 1, "session_id": "uuid-A",
             "tokens_used": "1234", "input_tokens": "500",
             "output_tokens": "200", "cache_read_tokens": None,
             "cache_create_tokens": ""},
        ])
        result = _read_session_iterations(state, "c1", "uuid-A")
        assert result[0]["tokens_used"] == 1234
        assert result[0]["input_tokens"] == 500
        assert result[0]["output_tokens"] == 200
        assert result[0]["cache_read_tokens"] == 0
        assert result[0]["cache_create_tokens"] == 0
