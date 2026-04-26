"""Tests for `_poll_iteration_events` — the engine-side poll that converts
ralph-loop iteration entries (written by bash to `loop-state.json`) into
ITERATION_END orchestration events.

The bash loop appends one entry per iteration but does NOT emit events
itself. The engine polls each running change's loop-state.json every tick,
compares the iteration count with the per-change baseline
`extras.last_emitted_iter`, and emits one ITERATION_END event per new entry.
This is the only path that surfaces ground-truth `resumed` values to the
activity timeline.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.engine import _poll_iteration_events
from set_orch.events import EventBus
from set_orch.state import Change, OrchestratorState, save_state, load_state


def _make_state(tmp_path, change_status="running", extras=None):
    """Build a minimal state with one change pointing at a worktree path."""
    wt = tmp_path / "wt-c1"
    (wt / ".set").mkdir(parents=True, exist_ok=True)
    state_file = str(tmp_path / "orchestration-state.json")
    state = OrchestratorState(
        status="running",
        changes=[
            Change(
                name="c1",
                status=change_status,
                worktree_path=str(wt),
                extras=extras or {},
            ),
        ],
    )
    save_state(state, state_file)
    return state_file, wt


def _write_loop_state(wt, iterations, session_id="sid-current"):
    """Write a loop-state.json with the given iterations list."""
    p = wt / ".set" / "loop-state.json"
    p.write_text(json.dumps({
        "change": "c1",
        "session_id": session_id,
        "iterations": iterations,
    }))
    return p


def _capture_events(tmp_path):
    """EventBus that writes to a per-test JSONL we can read back."""
    log = tmp_path / "events.jsonl"
    return EventBus(log_path=log), log


def _read_events(log):
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


class TestIterationEventPolling:
    def test_emits_one_event_per_new_iteration(self, tmp_path):
        state_file, wt = _make_state(tmp_path)
        _write_loop_state(wt, [
            {"n": 1, "started": "2026-01-01T10:00:00+00:00",
             "ended": "2026-01-01T10:05:00+00:00",
             "resumed": False, "tokens_used": 1000},
            {"n": 2, "started": "2026-01-01T10:06:00+00:00",
             "ended": "2026-01-01T10:11:00+00:00",
             "resumed": True, "tokens_used": 800},
        ])
        bus, log = _capture_events(tmp_path)

        _poll_iteration_events(state_file, bus)

        evts = [e for e in _read_events(log) if e.get("type") == "ITERATION_END"]
        assert len(evts) == 2
        assert evts[0]["data"]["iteration"] == 1
        assert evts[0]["data"]["resumed"] is False
        assert evts[0]["data"]["session_id"] == "sid-current"
        assert evts[0]["data"]["duration_ms"] == 5 * 60 * 1000
        assert evts[1]["data"]["iteration"] == 2
        assert evts[1]["data"]["resumed"] is True

    def test_baseline_persisted_so_no_double_emit_on_next_poll(self, tmp_path):
        state_file, wt = _make_state(tmp_path)
        _write_loop_state(wt, [
            {"n": 1, "started": "t1", "ended": "t2", "resumed": False},
        ])
        bus, log = _capture_events(tmp_path)

        _poll_iteration_events(state_file, bus)
        _poll_iteration_events(state_file, bus)

        evts = [e for e in _read_events(log) if e.get("type") == "ITERATION_END"]
        assert len(evts) == 1, "second poll should not re-emit existing iter"

        # And the baseline is now in extras.
        st = load_state(state_file)
        assert st.changes[0].extras.get("last_emitted_iter") == 1

    def test_only_new_iterations_emitted_after_baseline(self, tmp_path):
        # Pre-set the baseline as if iter 1 was already emitted in a prior tick.
        state_file, wt = _make_state(
            tmp_path, extras={"last_emitted_iter": 1},
        )
        _write_loop_state(wt, [
            {"n": 1, "started": "t1", "ended": "t2", "resumed": False},
            {"n": 2, "started": "t3", "ended": "t4", "resumed": True},
            {"n": 3, "started": "t5", "ended": "t6", "resumed": True},
        ])
        bus, log = _capture_events(tmp_path)

        _poll_iteration_events(state_file, bus)

        evts = [e for e in _read_events(log) if e.get("type") == "ITERATION_END"]
        assert [e["data"]["iteration"] for e in evts] == [2, 3]

    def test_skips_changes_with_pending_or_blocked_status(self, tmp_path):
        state_file, wt = _make_state(tmp_path, change_status="pending")
        _write_loop_state(wt, [
            {"n": 1, "started": "t1", "ended": "t2", "resumed": False},
        ])
        bus, log = _capture_events(tmp_path)

        _poll_iteration_events(state_file, bus)

        evts = [e for e in _read_events(log) if e.get("type") == "ITERATION_END"]
        assert evts == []

    def test_handles_corrupt_loop_state_gracefully(self, tmp_path):
        state_file, wt = _make_state(tmp_path)
        (wt / ".set" / "loop-state.json").write_text("{not valid json")
        bus, log = _capture_events(tmp_path)

        # Should not raise.
        _poll_iteration_events(state_file, bus)

        evts = [e for e in _read_events(log) if e.get("type") == "ITERATION_END"]
        assert evts == []

    def test_handles_missing_loop_state_silently(self, tmp_path):
        state_file, wt = _make_state(tmp_path)
        # Don't create loop-state.json
        bus, log = _capture_events(tmp_path)

        _poll_iteration_events(state_file, bus)

        evts = [e for e in _read_events(log) if e.get("type") == "ITERATION_END"]
        assert evts == []

    def test_no_event_bus_is_noop(self, tmp_path):
        """Passing event_bus=None must not crash and not write anything."""
        state_file, wt = _make_state(tmp_path)
        _write_loop_state(wt, [
            {"n": 1, "started": "t1", "ended": "t2", "resumed": False},
        ])
        # Should not raise and should not update baseline.
        _poll_iteration_events(state_file, None)
        st = load_state(state_file)
        assert st.changes[0].extras.get("last_emitted_iter", 0) == 0

    def test_falls_back_to_top_level_session_id_when_iter_lacks_one(
        self, tmp_path,
    ):
        """Older loop-state files don't have per-iter session_id. The poller
        backfills it from the top-level current session_id."""
        state_file, wt = _make_state(tmp_path)
        _write_loop_state(wt, [
            {"n": 1, "started": "t1", "ended": "t2", "resumed": False},
        ], session_id="top-level-sid")
        bus, log = _capture_events(tmp_path)

        _poll_iteration_events(state_file, bus)

        evts = [e for e in _read_events(log) if e.get("type") == "ITERATION_END"]
        assert evts[0]["data"]["session_id"] == "top-level-sid"

    def test_per_iter_session_id_takes_precedence_when_present(self, tmp_path):
        """If a loop-state entry has its own session_id, the event uses
        that — it represents the actual session that ran iter N, even when
        the top-level current session_id has since rolled over."""
        state_file, wt = _make_state(tmp_path)
        _write_loop_state(wt, [
            {"n": 1, "started": "t1", "ended": "t2",
             "resumed": False, "session_id": "iter-1-sid"},
        ], session_id="rolled-over-sid")
        bus, log = _capture_events(tmp_path)

        _poll_iteration_events(state_file, bus)

        evts = [e for e in _read_events(log) if e.get("type") == "ITERATION_END"]
        assert evts[0]["data"]["session_id"] == "iter-1-sid"
