"""Unit tests for the engine's per-change token-runaway circuit breaker
(section 4 of fix-replan-stuck-gate-and-decomposer).

Covers `_apply_token_runaway_check`:
- Baseline captured on first call with a fingerprint
- No fire when fingerprint changes (baseline resets)
- Fires when delta exceeds threshold with a stable fingerprint
- No-op when fingerprint is unset
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.engine import _apply_token_runaway_check  # noqa: E402
from set_orch.state import Change, OrchestratorState, load_state, save_state  # noqa: E402


class _FakeBus:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def emit(self, event_type, **kwargs):
        self.events.append((event_type, kwargs))


@pytest.fixture
def state_file(tmp_path):
    os.makedirs(tmp_path / "openspec" / "changes", exist_ok=True)
    sf = tmp_path / "state.json"
    st = OrchestratorState(status="running", changes=[
        Change(name="foo", status="running", input_tokens=1_000_000),
    ])
    save_state(st, str(sf))
    return str(sf)


def _set(state_file, name, **kwargs):
    st = load_state(state_file)
    for c in st.changes:
        if c.name == name:
            for k, v in kwargs.items():
                setattr(c, k, v)
    save_state(st, state_file)


def test_no_fingerprint_is_noop(state_file):
    bus = _FakeBus()
    fired = _apply_token_runaway_check(state_file, "foo", 10_000_000, bus)
    assert fired is False
    assert bus.events == []


def test_baseline_captured_on_first_gate(state_file):
    bus = _FakeBus()
    _set(state_file, "foo", last_gate_fingerprint="sha256:aaa", input_tokens=1_000_000)
    fired = _apply_token_runaway_check(state_file, "foo", 10_000_000, bus)
    assert fired is False
    st = load_state(state_file)
    change = next(c for c in st.changes if c.name == "foo")
    assert change.token_runaway_baseline == 1_000_000


def test_fingerprint_change_resets_baseline(state_file):
    bus = _FakeBus()
    _set(state_file, "foo", last_gate_fingerprint="sha256:aaa", input_tokens=1_000_000)
    _apply_token_runaway_check(state_file, "foo", 10_000_000, bus)

    # Same fingerprint, tokens grow but under threshold → no fire.
    _set(state_file, "foo", input_tokens=5_000_000)
    fired = _apply_token_runaway_check(state_file, "foo", 10_000_000, bus)
    assert fired is False

    # Fingerprint changes → baseline resets to current (5M).
    _set(state_file, "foo", last_gate_fingerprint="sha256:bbb")
    _apply_token_runaway_check(state_file, "foo", 10_000_000, bus)
    st = load_state(state_file)
    change = next(c for c in st.changes if c.name == "foo")
    assert change.token_runaway_baseline == 5_000_000


def test_breaker_fires_when_delta_exceeds_threshold(state_file):
    bus = _FakeBus()
    _set(state_file, "foo", last_gate_fingerprint="sha256:aaa", input_tokens=1_000_000)
    _apply_token_runaway_check(state_file, "foo", 10_000_000, bus)

    # Grow by 15M (above 10M threshold) with SAME fingerprint.
    _set(state_file, "foo", input_tokens=16_000_000)
    fired = _apply_token_runaway_check(state_file, "foo", 10_000_000, bus)
    assert fired is True

    st = load_state(state_file)
    change = next(c for c in st.changes if c.name == "foo")
    assert change.status == "failed:token_runaway"
    assert change.fix_iss_child is not None

    event_types = [e[0] for e in bus.events]
    assert "TOKEN_RUNAWAY" in event_types
    assert "FIX_ISS_ESCALATED" in event_types


def test_breaker_does_not_fire_when_under_threshold(state_file):
    bus = _FakeBus()
    _set(state_file, "foo", last_gate_fingerprint="sha256:aaa", input_tokens=1_000_000)
    _apply_token_runaway_check(state_file, "foo", 10_000_000, bus)

    _set(state_file, "foo", input_tokens=5_000_000)  # +4M under threshold
    fired = _apply_token_runaway_check(state_file, "foo", 10_000_000, bus)
    assert fired is False
    st = load_state(state_file)
    change = next(c for c in st.changes if c.name == "foo")
    assert change.status == "running"
