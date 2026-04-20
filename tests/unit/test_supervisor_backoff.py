"""Unit tests for the supervisor's exponential back-off on
retry_budget_exhausted (section 5 of fix-replan-stuck-gate-and-decomposer).

Uses a fake clock so the 60/120/240/480/600s steps are observable without
real sleeps. Validates that within a single back-off window no new
SUPERVISOR_TRIGGER event is emitted, steps escalate on repeated exhaustion,
and the back-off cache clears when the detector's condition disappears.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.supervisor.anomaly import AnomalyTrigger  # noqa: E402
from set_orch.supervisor.state import SupervisorStatus  # noqa: E402
from set_orch.supervisor.triggers import (  # noqa: E402
    BACKOFF_STEPS_SECONDS,
    TriggerExecutor,
    _backoff_tuple_key,
)


class _FakeClock:
    def __init__(self, start: float = 1_000_000.0):
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _dummy_spawn(*_, **kwargs):
    from set_orch.supervisor.ephemeral import EphemeralResult
    return EphemeralResult(
        trigger=kwargs.get("trigger", ""),
        exit_code=0, timed_out=False, elapsed_ms=1,
    )


@pytest.fixture
def executor(tmp_path):
    status = SupervisorStatus()
    events: list[tuple[str, dict]] = []

    def emit(event_type, data):
        events.append((event_type, data))

    ex = TriggerExecutor(
        status=status,
        project_path=tmp_path,
        events_path=tmp_path / "events.jsonl",
        spec="docs/spec.md",
        emit_event=emit,
        spawn_fn=_dummy_spawn,
        retry_budgets={"log_silence": 1},  # tiny budget → exhaust immediately
        rate_limit_per_hour=9999,
        clock=_FakeClock(),
    )
    ex._events = events
    ex._clock = ex.clock  # expose the fake
    return ex


def test_first_exhaustion_starts_60s_backoff(executor):
    trig = AnomalyTrigger(type="log_silence", change="", reason="no logs 5m", priority=5)

    # First fire: budget was 1 — the spawn succeeds, no back-off yet.
    outs = executor.execute([trig])
    assert outs[0].skipped_reason == ""
    assert executor.status.trigger_backoffs == {}

    # Second fire: budget exhausted → record skip + start step=1 (60s)
    outs = executor.execute([trig])
    assert outs[0].skipped_reason == "retry_budget_exhausted"
    key = _backoff_tuple_key(trig)
    assert key in executor.status.trigger_backoffs
    assert executor.status.trigger_backoffs[key]["step"] == 1


def test_within_window_no_event_emitted(executor):
    trig = AnomalyTrigger(type="log_silence", change="", reason="x", priority=5)
    executor.execute([trig])   # consume budget
    executor.execute([trig])   # first exhaustion → back-off 60s, 1 skip event

    events_before = len(executor._events)
    # Advance 30s — still inside 60s window
    executor.clock.advance(30)
    outs = executor.execute([trig])
    assert outs[0].skipped_reason == "back_off_active"
    # IMPORTANT: no new SUPERVISOR_TRIGGER event should have been written
    assert len(executor._events) == events_before


def test_backoff_grows_on_repeated_exhaustion(executor):
    trig = AnomalyTrigger(type="log_silence", change="", reason="x", priority=5)
    key = _backoff_tuple_key(trig)

    executor.execute([trig])  # consume budget
    executor.execute([trig])  # first exhaustion: step 1, 60s
    assert executor.status.trigger_backoffs[key]["step"] == 1

    # Advance past window and fire again → still exhausted → step 2, 120s
    executor.clock.advance(61)
    executor.execute([trig])
    assert executor.status.trigger_backoffs[key]["step"] == 2

    executor.clock.advance(121)
    executor.execute([trig])
    assert executor.status.trigger_backoffs[key]["step"] == 3

    executor.clock.advance(241)
    executor.execute([trig])
    assert executor.status.trigger_backoffs[key]["step"] == 4

    executor.clock.advance(481)
    executor.execute([trig])
    assert executor.status.trigger_backoffs[key]["step"] == 5

    # Cap: one more exhaustion cannot push step past len(steps).
    executor.clock.advance(601)
    executor.execute([trig])
    assert executor.status.trigger_backoffs[key]["step"] == 5


def test_backoff_clears_when_trigger_not_fired(executor):
    trig = AnomalyTrigger(type="log_silence", change="", reason="x", priority=5)
    key = _backoff_tuple_key(trig)
    executor.execute([trig])
    executor.execute([trig])
    assert key in executor.status.trigger_backoffs

    # Next poll fires nothing — the detector's condition no longer holds.
    # execute([]) should evict the stale back-off entry.
    executor.execute([])
    assert key not in executor.status.trigger_backoffs


def test_backoff_tuple_keyed_by_change(executor):
    """Same trigger type, different changes → separate back-off windows."""
    t1 = AnomalyTrigger(type="integration_failed", change="foo", reason="x", priority=5)
    t2 = AnomalyTrigger(type="integration_failed", change="bar", reason="x", priority=5)
    assert _backoff_tuple_key(t1) != _backoff_tuple_key(t2)


def test_emits_exactly_one_event_in_first_60s_window(executor):
    """Spec scenario: 15s polling produces exactly 1 event in first 60s."""
    trig = AnomalyTrigger(type="log_silence", change="", reason="x", priority=5)
    executor.execute([trig])  # consume budget (real spawn + event)
    count_events = lambda: sum(1 for t, _ in executor._events if t == "SUPERVISOR_TRIGGER")

    # Budget exhausts on second fire → 1 skip event for back-off start.
    executor.execute([trig])
    baseline = count_events()

    # Poll 3 more times at 15s intervals — T=15, 30, 45 all < 60s window.
    for _ in range(3):
        executor.clock.advance(15)
        executor.execute([trig])

    # Zero additional events — all suppressed by back-off.
    assert count_events() == baseline
