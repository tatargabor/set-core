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


def test_first_observation_never_fires_even_with_max_one(state_file):
    """With max_stuck_loops=1, a brand-new observation must NOT trip the
    breaker on the FIRST stuck exit — we have no evidence of repeated
    failure yet. The breaker fires on the SECOND exit with the same
    fingerprint.
    """
    bus = _FakeBus()
    _set_fingerprint(state_file, "foo", "sha256:aaa")
    fired = _apply_stuck_loop_counter(state_file, "foo", 1, bus)
    assert fired is False  # baseline capture only

    fired = _apply_stuck_loop_counter(state_file, "foo", 1, bus)
    assert fired is True  # second same-fp observation → trip


def test_head_moved_resets_counter_even_with_same_fingerprint(tmp_path, monkeypatch):
    """Regression for craftbrew-run-20260421-0025: the agent commits a fix
    between iterations but the gate isn't re-run, so the cached fingerprint
    still reflects the pre-fix verdict. Without this guard, stuck_loop would
    trip on the 3rd repeat of a fingerprint that's stale, discarding agent
    progress. With it, a moved HEAD SHA triggers a counter reset.
    """
    import subprocess
    # Create a real git worktree for HEAD reads
    wt = tmp_path / "wt"
    wt.mkdir()
    subprocess.run(["git", "init", "-q", str(wt)], check=True)
    subprocess.run(["git", "-C", str(wt), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(wt), "config", "user.name", "t"], check=True)
    (wt / "f.txt").write_text("v1")
    subprocess.run(["git", "-C", str(wt), "add", "."], check=True)
    subprocess.run(["git", "-C", str(wt), "commit", "-q", "-m", "c1"], check=True)

    os.makedirs(tmp_path / "openspec" / "changes", exist_ok=True)
    sf = tmp_path / "state.json"
    st = OrchestratorState(status="running", changes=[
        Change(name="foo", worktree_path=str(wt), status="running"),
    ])
    save_state(st, str(sf))

    bus = _FakeBus()

    # First stuck: captures fingerprint + HEAD baseline.
    _set_fingerprint(str(sf), "foo", "sha256:aaa")
    _apply_stuck_loop_counter(str(sf), "foo", 3, bus)

    # Second stuck: counter -> 2 (baseline HEAD matches).
    _apply_stuck_loop_counter(str(sf), "foo", 3, bus)
    loaded = load_state(str(sf))
    assert next(c for c in loaded.changes if c.name == "foo").stuck_loop_count == 2

    # Agent commits a fix. HEAD moves. Fingerprint still "aaa" because the
    # gate wasn't re-run — this is the catalog-listings scenario.
    (wt / "f.txt").write_text("v2")
    subprocess.run(["git", "-C", str(wt), "commit", "-aq", "-m", "agent fix"], check=True)

    # Third call: must RESET, not trip.
    fired = _apply_stuck_loop_counter(str(sf), "foo", 3, bus)
    assert fired is False, "stuck_loop tripped despite HEAD moving (new commit present)"

    loaded = load_state(str(sf))
    change = next(c for c in loaded.changes if c.name == "foo")
    assert change.stuck_loop_count == 0, "counter must reset when HEAD moves"
    assert change.status == "running", "change must not be marked failed"
    assert "STUCK_LOOP_ESCALATED" not in [e[0] for e in bus.events]


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
