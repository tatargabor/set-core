"""Unit tests for lib/set_orch/supervisor/triggers.py.

Covers the trigger executor's:
  - retry budget exhaustion
  - global rate-limit window
  - sequential dispatch + priority order
  - terminal_state short-circuit
  - SUPERVISOR_TRIGGER event emission (success + skip)
  - prompt building uses prior_attempts_summary
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.supervisor.anomaly import AnomalyTrigger
from set_orch.supervisor.ephemeral import EphemeralResult
from set_orch.supervisor.state import SupervisorStatus
from set_orch.supervisor.triggers import (
    DEFAULT_GLOBAL_RATE_LIMIT_PER_HOUR,
    DEFAULT_RETRY_BUDGETS,
    TriggerExecutor,
)


@pytest.fixture
def project_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


class FakeClock:
    """Deterministic monotonic clock for retry-window tests."""

    def __init__(self, start: float = 1_000_000.0):
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def make_executor(
    project_dir: Path,
    *,
    spawn_results: list[EphemeralResult] | None = None,
    retry_budgets: dict[str, int] | None = None,
    rate_limit: int = DEFAULT_GLOBAL_RATE_LIMIT_PER_HOUR,
    clock: FakeClock | None = None,
) -> tuple[TriggerExecutor, list[tuple[str, dict]], list[dict]]:
    """Build an executor wired up with mock spawn + emit collectors."""
    spawn_calls: list[dict] = []
    spawn_results = spawn_results or [
        EphemeralResult(
            trigger="t",
            exit_code=0,
            timed_out=False,
            elapsed_ms=42,
            stdout_tail="VERDICT: noted",
        )
    ]

    def fake_spawn(**kwargs):
        spawn_calls.append(kwargs)
        # Round-robin through provided results, last one repeats
        idx = min(len(spawn_calls) - 1, len(spawn_results) - 1)
        return spawn_results[idx]

    events: list[tuple[str, dict]] = []

    def emit(event_type: str, data: dict) -> None:
        events.append((event_type, data))

    status = SupervisorStatus()
    executor = TriggerExecutor(
        status=status,
        project_path=project_dir,
        events_path=project_dir / "events.jsonl",
        spec="docs/spec.md",
        emit_event=emit,
        spawn_fn=fake_spawn,
        retry_budgets=retry_budgets or DEFAULT_RETRY_BUDGETS,
        rate_limit_per_hour=rate_limit,
        clock=clock or FakeClock(),
    )
    return executor, events, spawn_calls


# ─── basic dispatch ──────────────────────────────────────


class TestDispatch:
    def test_single_trigger_dispatched_and_event_emitted(self, project_dir):
        executor, events, spawn_calls = make_executor(project_dir)
        trig = AnomalyTrigger(
            type="state_stall", reason="x", priority=20,
        )
        outcomes = executor.execute([trig])
        assert len(outcomes) == 1
        assert outcomes[0].result is not None
        assert outcomes[0].result.exit_code == 0
        assert len(spawn_calls) == 1
        assert spawn_calls[0]["trigger"] == "state_stall"
        # SUPERVISOR_TRIGGER event emitted
        types = [t for t, _ in events]
        assert "SUPERVISOR_TRIGGER" in types
        # Status counters updated
        assert executor.status.trigger_attempts.get("state_stall") == 1
        assert executor.status.trigger_counters.get("state_stall") == 1

    def test_priority_order(self, project_dir):
        executor, _events, spawn_calls = make_executor(project_dir)
        triggers = [
            AnomalyTrigger(type="state_stall", priority=20),
            AnomalyTrigger(type="terminal_state", priority=1),
            AnomalyTrigger(type="integration_failed", change="x", priority=10),
        ]
        executor.execute(triggers)
        # terminal_state should short-circuit AFTER its own dispatch, so we
        # only see ONE call (terminal_state). Others were never executed.
        assert len(spawn_calls) == 1
        assert spawn_calls[0]["trigger"] == "terminal_state"

    def test_terminal_state_short_circuits_remaining(self, project_dir):
        executor, _events, spawn_calls = make_executor(project_dir)
        triggers = [
            AnomalyTrigger(type="terminal_state", priority=1),
            AnomalyTrigger(type="state_stall", priority=20),
            AnomalyTrigger(type="log_silence", priority=35),
        ]
        executor.execute(triggers)
        assert len(spawn_calls) == 1
        assert spawn_calls[0]["trigger"] == "terminal_state"


# ─── retry budgets ───────────────────────────────────────


class TestRetryBudget:
    def test_skipped_after_budget_exhausted(self, project_dir):
        executor, events, spawn_calls = make_executor(
            project_dir,
            retry_budgets={"state_stall": 2},
        )
        trig = AnomalyTrigger(type="state_stall")

        # First two attempts: dispatched
        executor.execute([trig])
        executor.execute([trig])
        assert len(spawn_calls) == 2

        # Third attempt: skipped
        executor.execute([trig])
        assert len(spawn_calls) == 2

        skipped_events = [
            d for t, d in events if t == "SUPERVISOR_TRIGGER" and d.get("skipped")
        ]
        assert len(skipped_events) == 1
        assert skipped_events[0]["skipped"] == "retry_budget_exhausted"

    def test_budget_per_change(self, project_dir):
        executor, _events, spawn_calls = make_executor(
            project_dir,
            retry_budgets={"integration_failed": 1},
        )
        # Two different changes — each gets its own budget
        executor.execute([AnomalyTrigger(type="integration_failed", change="alpha")])
        executor.execute([AnomalyTrigger(type="integration_failed", change="beta")])
        assert len(spawn_calls) == 2
        # Same change, second time → skipped
        executor.execute([AnomalyTrigger(type="integration_failed", change="alpha")])
        assert len(spawn_calls) == 2


# ─── rate limit ──────────────────────────────────────────


class TestRateLimit:
    def test_skipped_after_global_cap(self, project_dir):
        clock = FakeClock()
        executor, events, spawn_calls = make_executor(
            project_dir,
            rate_limit=2,
            clock=clock,
            retry_budgets={"non_periodic_checkpoint": 100},
        )
        trig = AnomalyTrigger(type="non_periodic_checkpoint")
        executor.execute([trig])
        executor.execute([trig])
        executor.execute([trig])  # 3rd → rate-limited
        assert len(spawn_calls) == 2
        skipped = [d for t, d in events if t == "SUPERVISOR_TRIGGER" and d.get("skipped")]
        assert any(d["skipped"] == "rate_limit_hit" for d in skipped)

    def test_window_resets_after_one_hour(self, project_dir):
        clock = FakeClock()
        executor, _events, spawn_calls = make_executor(
            project_dir,
            rate_limit=1,
            clock=clock,
            retry_budgets={"non_periodic_checkpoint": 100},
        )
        trig = AnomalyTrigger(type="non_periodic_checkpoint")
        executor.execute([trig])  # uses budget
        executor.execute([trig])  # rate-limited
        assert len(spawn_calls) == 1
        clock.advance(3700)  # past 1h
        executor.execute([trig])
        assert len(spawn_calls) == 2
