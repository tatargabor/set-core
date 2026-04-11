"""Unit tests for lib/set_orch/supervisor/canary.py."""

from __future__ import annotations

import datetime
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.supervisor.canary import (
    DEFAULT_CANARY_INTERVAL_SECONDS,
    WARN_RATE_LIMIT_SECONDS,
    CanaryDiff,
    CanaryRun,
    CanaryRunner,
    build_canary_diff,
    parse_canary_verdict,
)
from set_orch.supervisor.ephemeral import EphemeralResult
from set_orch.supervisor.state import SupervisorStatus


@pytest.fixture
def project_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


# ─── parse_canary_verdict ────────────────────────────────


class TestParseVerdict:
    def test_ok(self):
        assert parse_canary_verdict("blah blah\nCANARY_VERDICT: ok") == "ok"

    def test_note_lowercase(self):
        assert parse_canary_verdict("CANARY_VERDICT: note") == "note"

    def test_warn_uppercase_keyword(self):
        assert parse_canary_verdict("CANARY_VERDICT: WARN") == "warn"

    def test_stop(self):
        assert parse_canary_verdict("end\nCANARY_VERDICT: stop\n") == "stop"

    def test_missing_defaults_to_note(self):
        assert parse_canary_verdict("no verdict at all") == "note"

    def test_empty_defaults_to_note(self):
        assert parse_canary_verdict("") == "note"

    def test_unrecognised_value_defaults_to_note(self):
        assert parse_canary_verdict("CANARY_VERDICT: panic") == "note"


# ─── build_canary_diff ───────────────────────────────────


class TestBuildCanaryDiff:
    def test_classifies_changes(self):
        state = {
            "changes": [
                {"name": "a", "status": "merged"},
                {"name": "b", "status": "running", "tokens_used": 1000, "redispatch_count": 1},
                {"name": "c", "status": "pending"},
                {"name": "d", "status": "integration-failed"},
            ],
        }
        diff = build_canary_diff(
            state=state, new_events=[], poll_cycle=5,
            window_start_iso="2026-04-11T10:00:00Z",
            window_end_iso="2026-04-11T10:15:00Z",
        )
        assert diff.merged_changes == ["a"]
        assert len(diff.running_changes) == 1
        assert diff.running_changes[0]["name"] == "b"
        assert diff.running_changes[0]["tokens_used"] == 1000
        assert diff.pending_changes == ["c"]
        assert diff.failed_changes == ["d"]

    def test_event_summary_skips_heartbeat(self):
        events = [
            {"type": "WATCHDOG_HEARTBEAT"},
            {"type": "GATE_PASS"},
            {"type": "GATE_PASS"},
            {"type": "MERGE_SUCCESS"},
        ]
        diff = build_canary_diff(
            state=None, new_events=events, poll_cycle=1,
            window_start_iso="t1", window_end_iso="t2",
        )
        assert diff.event_summary == {"GATE_PASS": 2, "MERGE_SUCCESS": 1}
        assert "WATCHDOG_HEARTBEAT" not in diff.event_summary

    def test_gate_ms_averages(self):
        state = {
            "changes": [
                {"name": "a", "gate_build_ms": 100},
                {"name": "b", "gate_build_ms": 300},
                {"name": "c", "gate_test_ms": 50},
            ],
        }
        diff = build_canary_diff(
            state=state, new_events=[], poll_cycle=1,
            window_start_iso="t1", window_end_iso="t2",
        )
        assert diff.gate_ms["build"] == 200  # (100+300)/2
        assert diff.gate_ms["test"] == 50

    def test_render_contains_question_and_format(self):
        diff = build_canary_diff(
            state={"changes": [{"name": "x", "status": "merged"}]},
            new_events=[],
            poll_cycle=1,
            window_start_iso="t1",
            window_end_iso="t2",
        )
        rendered = diff.render()
        assert "Canary check" in rendered
        assert "CANARY_VERDICT: ok" in rendered
        assert "Merged: x" in rendered


# ─── CanaryRunner ────────────────────────────────────────


class FakeClock:
    def __init__(self, t: float = 1_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


def make_runner(
    project_dir: Path,
    *,
    spawn_result: EphemeralResult,
    clock: FakeClock | None = None,
):
    spawn_calls: list[dict] = []
    events: list[tuple[str, dict]] = []

    def fake_spawn(**kwargs):
        spawn_calls.append(kwargs)
        return spawn_result

    def emit(t, d):
        events.append((t, d))

    status = SupervisorStatus()
    runner = CanaryRunner(
        status=status,
        project_path=project_dir,
        spec="docs/spec.md",
        emit_event=emit,
        spawn_fn=fake_spawn,
        clock=clock or FakeClock(),
    )
    return runner, events, spawn_calls


def trivial_diff() -> CanaryDiff:
    return build_canary_diff(
        state=None, new_events=[], poll_cycle=1,
        window_start_iso="t1", window_end_iso="t2",
    )


class TestRunnerLifecycle:
    def test_is_due_initially(self, project_dir):
        runner, _, _ = make_runner(
            project_dir,
            spawn_result=EphemeralResult(
                trigger="canary", exit_code=0, timed_out=False,
                elapsed_ms=10, stdout_tail="CANARY_VERDICT: ok",
            ),
        )
        assert runner.is_due() is True

    def test_not_due_after_recent_run(self, project_dir):
        clock = FakeClock()
        runner, _events, _ = make_runner(
            project_dir,
            spawn_result=EphemeralResult(
                trigger="canary", exit_code=0, timed_out=False,
                elapsed_ms=10, stdout_tail="CANARY_VERDICT: ok",
            ),
            clock=clock,
        )
        runner.run(trivial_diff())
        # last_canary_at gets set to wall-clock UTC; is_due reads from
        # status.last_canary_at via fromisoformat. Re-check immediately.
        assert runner.is_due() is False

    def test_due_again_after_interval(self, project_dir):
        # Use real time.time() so the wall-clock last_canary_at and the
        # runner's clock agree (FakeClock decouples them).
        import time as _time
        runner, _events, _ = make_runner(
            project_dir,
            spawn_result=EphemeralResult(
                trigger="canary", exit_code=0, timed_out=False,
                elapsed_ms=10, stdout_tail="CANARY_VERDICT: ok",
            ),
            clock=_time.time,  # type: ignore[arg-type]
        )
        # Pretend a canary ran 20 minutes ago
        runner.status.last_canary_at = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=20)
        ).isoformat()
        assert runner.is_due() is True

    def test_not_due_after_recent_real_time(self, project_dir):
        import time as _time
        runner, _events, _ = make_runner(
            project_dir,
            spawn_result=EphemeralResult(
                trigger="canary", exit_code=0, timed_out=False,
                elapsed_ms=10, stdout_tail="CANARY_VERDICT: ok",
            ),
            clock=_time.time,  # type: ignore[arg-type]
        )
        runner.status.last_canary_at = (
            datetime.datetime.now(datetime.timezone.utc)
        ).isoformat()
        assert runner.is_due() is False

    def test_emits_canary_check_event(self, project_dir):
        runner, events, _ = make_runner(
            project_dir,
            spawn_result=EphemeralResult(
                trigger="canary", exit_code=0, timed_out=False,
                elapsed_ms=10, stdout_tail="CANARY_VERDICT: note\n",
            ),
        )
        runner.run(trivial_diff())
        assert any(t == "CANARY_CHECK" for t, _ in events)
        canary_evt = next(d for t, d in events if t == "CANARY_CHECK")
        assert canary_evt["verdict"] == "note"


class TestWarnRateLimit:
    def test_warn_recorded_on_first_fire(self, project_dir):
        runner, _events, _ = make_runner(
            project_dir,
            spawn_result=EphemeralResult(
                trigger="canary", exit_code=0, timed_out=False,
                elapsed_ms=10,
                stdout_tail=(
                    "the dispatcher seems stuck on change foo with 999 retries\n"
                    "CANARY_VERDICT: warn"
                ),
            ),
        )
        run = runner.run(trivial_diff())
        assert run.verdict == "warn"
        assert len(runner.status.canary_warn_log) == 1

    def test_repeat_warn_downgraded_to_note(self, project_dir):
        runner, _events, _ = make_runner(
            project_dir,
            spawn_result=EphemeralResult(
                trigger="canary", exit_code=0, timed_out=False,
                elapsed_ms=10,
                stdout_tail=(
                    "the dispatcher seems stuck on change foo with 999 retries\n"
                    "CANARY_VERDICT: warn"
                ),
            ),
        )
        first = runner.run(trivial_diff())
        assert first.verdict == "warn"
        second = runner.run(trivial_diff())
        # Same signature within rate-limit window → downgraded
        assert second.verdict == "note"

    def test_warn_with_different_signature_fires(self, project_dir):
        # First spawn produces signature A
        sa = EphemeralResult(
            trigger="canary", exit_code=0, timed_out=False, elapsed_ms=10,
            stdout_tail="dispatcher stuck on alpha\nCANARY_VERDICT: warn",
        )
        # Second spawn produces a totally different signature
        sb = EphemeralResult(
            trigger="canary", exit_code=0, timed_out=False, elapsed_ms=10,
            stdout_tail="merge conflicts piling up on beta\nCANARY_VERDICT: warn",
        )
        spawn_results = iter([sa, sb])
        spawn_calls: list[dict] = []
        events: list[tuple[str, dict]] = []

        def fake_spawn(**kwargs):
            spawn_calls.append(kwargs)
            return next(spawn_results)

        runner = CanaryRunner(
            status=SupervisorStatus(),
            project_path=project_dir,
            spec="docs/spec.md",
            emit_event=lambda t, d: events.append((t, d)),
            spawn_fn=fake_spawn,
        )
        run1 = runner.run(trivial_diff())
        run2 = runner.run(trivial_diff())
        assert run1.verdict == "warn"
        assert run2.verdict == "warn"
        assert len(runner.status.canary_warn_log) == 2
