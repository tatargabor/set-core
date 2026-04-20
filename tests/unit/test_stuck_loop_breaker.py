"""Unit tests for the engine's stuck-loop circuit breaker (section 3 of
fix-replan-stuck-gate-and-decomposer).

Covers `_apply_stuck_loop_counter`:
- Increment on identical fingerprint
- Reset on fingerprint change
- Threshold-first ordering — simultaneous threshold+fingerprint-changed
  lets the fingerprint change win, counter resets to 0
- Hard-fail + fix-iss escalation on threshold hit
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.engine import _apply_stuck_loop_counter  # noqa: E402
from set_orch.state import Change, OrchestratorState, load_state, save_state  # noqa: E402


class _FakeBus:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def emit(self, event_type, **kwargs):
        self.events.append((event_type, kwargs))


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    """State file with a single 'foo' change and a project root that has an
    openspec/ directory so escalation can write its proposal there.
    """
    # Fake project root with openspec/ so escalation succeeds.
    os.makedirs(tmp_path / "openspec" / "changes", exist_ok=True)
    sf = tmp_path / "state.json"
    st = OrchestratorState(status="running", changes=[
        Change(name="foo", worktree_path=str(tmp_path / "wt"), status="running"),
    ])
    save_state(st, str(sf))
    return str(sf)


def _set_fingerprint(state_file: str, change_name: str, fp: str):
    st = load_state(state_file)
    for c in st.changes:
        if c.name == change_name:
            c.last_gate_fingerprint = fp
    save_state(st, state_file)


def test_no_fingerprint_leaves_counter_untouched(state_file):
    bus = _FakeBus()
    fired = _apply_stuck_loop_counter(state_file, "foo", 3, bus)
    assert fired is False
    st = load_state(state_file)
    change = next(c for c in st.changes if c.name == "foo")
    assert change.stuck_loop_count == 0
    assert bus.events == []


def test_increment_on_same_fingerprint(state_file):
    bus = _FakeBus()
    _set_fingerprint(state_file, "foo", "sha256:aaa")
    fired = _apply_stuck_loop_counter(state_file, "foo", 3, bus)
    assert fired is False
    st = load_state(state_file)
    change = next(c for c in st.changes if c.name == "foo")
    assert change.stuck_loop_count == 1

    fired = _apply_stuck_loop_counter(state_file, "foo", 3, bus)
    assert fired is False
    st = load_state(state_file)
    change = next(c for c in st.changes if c.name == "foo")
    assert change.stuck_loop_count == 2


def test_reset_on_fingerprint_change(state_file):
    bus = _FakeBus()
    _set_fingerprint(state_file, "foo", "sha256:aaa")
    _apply_stuck_loop_counter(state_file, "foo", 3, bus)
    _apply_stuck_loop_counter(state_file, "foo", 3, bus)

    _set_fingerprint(state_file, "foo", "sha256:bbb")
    fired = _apply_stuck_loop_counter(state_file, "foo", 3, bus)
    assert fired is False
    st = load_state(state_file)
    change = next(c for c in st.changes if c.name == "foo")
    assert change.stuck_loop_count == 0


def test_threshold_fires_on_third_stuck_same_fingerprint(state_file):
    bus = _FakeBus()
    _set_fingerprint(state_file, "foo", "sha256:aaa")
    _apply_stuck_loop_counter(state_file, "foo", 3, bus)
    _apply_stuck_loop_counter(state_file, "foo", 3, bus)
    fired = _apply_stuck_loop_counter(state_file, "foo", 3, bus)
    assert fired is True
    st = load_state(state_file)
    change = next(c for c in st.changes if c.name == "foo")
    assert change.status == "failed:stuck_no_progress"
    assert change.stuck_loop_count == 3
    assert change.fix_iss_child is not None
    assert change.fix_iss_child.startswith("fix-iss-")
    # Event emitted
    event_types = [e[0] for e in bus.events]
    assert "STUCK_LOOP_ESCALATED" in event_types
    assert "FIX_ISS_ESCALATED" in event_types


def test_ordering_fingerprint_change_wins_over_threshold(state_file):
    """Simultaneous threshold-reached AND fingerprint-changed → threshold
    does NOT fire. Per tasks.md 3.7: 'check the threshold BEFORE evaluating
    reset'; if fingerprint is different, the 'would_trip' test fails and the
    reset branch runs, returning False.
    """
    bus = _FakeBus()
    _set_fingerprint(state_file, "foo", "sha256:aaa")
    _apply_stuck_loop_counter(state_file, "foo", 3, bus)
    _apply_stuck_loop_counter(state_file, "foo", 3, bus)
    # count is now 2. If fingerprint stays same, next call fires threshold.
    # We change fingerprint instead → counter resets to 0, no fire.
    _set_fingerprint(state_file, "foo", "sha256:different")
    fired = _apply_stuck_loop_counter(state_file, "foo", 3, bus)
    assert fired is False
    st = load_state(state_file)
    change = next(c for c in st.changes if c.name == "foo")
    assert change.stuck_loop_count == 0
    assert change.status == "running"  # not failed
