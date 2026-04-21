"""Unit tests for lib/set_orch/supervisor/anomaly.py.

Each detector gets at least:
  - one positive case (triggers)
  - one negative case (does not trigger)
Plus a smoke test for `scan_for_anomalies` that the priority sort works.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.supervisor.anomaly import (
    AnomalyContext,
    AnomalyTrigger,
    DEFAULT_LOG_SILENCE_SECS,
    DEFAULT_STATE_STALL_SECS,
    DEFAULT_TOKEN_STALL_LIMIT,
    DEFAULT_TOKEN_STALL_SECS,
    KNOWN_EVENT_TYPES,
    PERMANENT_ERROR_SIGNALS,
    _classify_exit,
    detect_error_rate_spike,
    detect_integration_failed,
    detect_log_silence,
    detect_non_periodic_checkpoint,
    detect_process_crash,
    detect_state_stall,
    detect_terminal_state,
    detect_token_stall,
    detect_unknown_event_type,
    scan_for_anomalies,
)


@pytest.fixture
def tmp_project():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


def make_ctx(
    *,
    project_path: Path,
    state: dict | None = None,
    new_events: list[dict] | None = None,
    orchestrator_alive: bool = True,
    orchestrator_pid: int = 12345,
    state_mtime: float = 0.0,
    last_state_mtime: float = 0.0,
    last_state_change_at: float = 0.0,
    log_path: Path | None = None,
    log_size: int = 0,
    last_log_size: int = 0,
    last_log_growth_at: float = 0.0,
    error_baseline: dict | None = None,
    known_event_types: set[str] | None = None,
    now: float | None = None,
    last_change_statuses: dict[str, str] | None = None,
    last_orch_status: str = "",
    terminal_state_fired: bool = False,
    crossed_token_stall_thresholds: set[str] | None = None,
) -> AnomalyContext:
    return AnomalyContext(
        project_path=project_path,
        state_path=None,
        events_path=None,
        log_path=log_path,
        state=state,
        new_events=new_events or [],
        orchestrator_pid=orchestrator_pid,
        orchestrator_alive=orchestrator_alive,
        now=now or time.time(),
        state_mtime=state_mtime,
        last_state_mtime=last_state_mtime,
        last_state_change_at=last_state_change_at,
        log_size=log_size,
        last_log_size=last_log_size,
        last_log_growth_at=last_log_growth_at,
        error_baseline=error_baseline if error_baseline is not None else {},
        known_event_types=known_event_types if known_event_types is not None else set(),
        last_change_statuses=last_change_statuses if last_change_statuses is not None else {},
        last_orch_status=last_orch_status,
        terminal_state_fired=terminal_state_fired,
        crossed_token_stall_thresholds=(
            crossed_token_stall_thresholds
            if crossed_token_stall_thresholds is not None
            else set()
        ),
    )


# ─── terminal_state ──────────────────────────────────────


class TestTerminalState:
    def test_fires_when_status_done_and_pid_dead(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"status": "done", "changes": []},
            orchestrator_alive=False,
        )
        result = detect_terminal_state(ctx)
        assert len(result) == 1
        assert result[0].type == "terminal_state"
        assert result[0].priority == 1
        assert result[0].context["status"] == "done"

    def test_no_fire_when_pid_alive(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"status": "done", "changes": []},
            orchestrator_alive=True,
        )
        assert detect_terminal_state(ctx) == []

    def test_no_fire_when_running(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"status": "running"},
            orchestrator_alive=False,
        )
        assert detect_terminal_state(ctx) == []


# ─── process_crash ───────────────────────────────────────


class TestProcessCrash:
    def test_fires_when_dead_and_status_running(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"status": "running"},
            orchestrator_alive=False,
            orchestrator_pid=99,
        )
        result = detect_process_crash(ctx)
        assert len(result) == 1
        assert result[0].type == "process_crash"

    def test_no_fire_when_alive(self, tmp_project):
        ctx = make_ctx(project_path=tmp_project, state={"status": "running"}, orchestrator_alive=True)
        assert detect_process_crash(ctx) == []

    def test_no_fire_when_terminal(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"status": "done"},
            orchestrator_alive=False,
        )
        assert detect_process_crash(ctx) == []

    def test_no_fire_with_zero_pid(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"status": "running"},
            orchestrator_alive=False,
            orchestrator_pid=0,
        )
        assert detect_process_crash(ctx) == []


# ─── integration_failed ──────────────────────────────────


class TestIntegrationFailed:
    def test_fires_per_failing_change(self, tmp_project):
        state = {
            "changes": [
                {"name": "foo", "status": "integration-failed", "tokens_used": 50},
                {"name": "bar", "status": "running"},
                {"name": "baz", "status": "integration-e2e-failed", "tokens_used": 100},
            ]
        }
        ctx = make_ctx(project_path=tmp_project, state=state)
        result = detect_integration_failed(ctx)
        assert len(result) == 2
        names = {t.change for t in result}
        assert names == {"foo", "baz"}
        for t in result:
            assert t.type == "integration_failed"
            assert t.priority == 10

    def test_fires_on_plain_failed_status(self, tmp_project):
        # The orchestrator uses plain "failed" (not "integration-failed")
        # as the terminal status after max_verify_retries exhausts. The
        # detector must match this case too — it was the missing status
        # that left minishop-run-20260412-0103 uninstrumented for 1.5h.
        state = {
            "changes": [
                {"name": "foundation-setup", "status": "failed",
                 "tokens_used": 247_037, "verify_retry_count": 3},
            ]
        }
        ctx = make_ctx(project_path=tmp_project, state=state)
        result = detect_integration_failed(ctx)
        assert len(result) == 1
        assert result[0].change == "foundation-setup"
        assert result[0].context["verify_retry_count"] == 3

    def test_fires_on_any_status_with_failed_substring(self, tmp_project):
        state = {
            "changes": [
                {"name": "a", "status": "failed"},
                {"name": "b", "status": "integration-failed"},
                {"name": "c", "status": "integration-e2e-failed"},
                {"name": "d", "status": "integration-coverage-failed"},
            ]
        }
        ctx = make_ctx(project_path=tmp_project, state=state)
        result = detect_integration_failed(ctx)
        assert {t.change for t in result} == {"a", "b", "c", "d"}

    def test_does_not_fire_on_skipped(self, tmp_project):
        # "skipped" is intentional no-op, not a failure
        ctx = make_ctx(
            project_path=tmp_project,
            state={"changes": [{"name": "x", "status": "skipped"}]},
        )
        assert detect_integration_failed(ctx) == []

    def test_no_fire_when_all_clean(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"changes": [{"name": "foo", "status": "merged"}]},
        )
        assert detect_integration_failed(ctx) == []


class TestTransitionTriggers:
    """Transition-check coverage for detect_integration_failed, detect_terminal_state, detect_token_stall."""

    def test_integration_failed_first_observation_fires(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"changes": [{"name": "x", "status": "failed"}]},
            last_change_statuses={},
        )
        result = detect_integration_failed(ctx)
        assert len(result) == 1
        assert result[0].change == "x"

    def test_integration_failed_stable_state_no_refire(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"changes": [{"name": "x", "status": "failed"}]},
            last_change_statuses={"x": "failed"},
        )
        assert detect_integration_failed(ctx) == []

    def test_integration_failed_running_to_failed_transition_fires(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"changes": [{"name": "x", "status": "failed"}]},
            last_change_statuses={"x": "running"},
        )
        result = detect_integration_failed(ctx)
        assert len(result) == 1
        assert result[0].context["prev_status"] == "running"

    def test_integration_failed_failed_to_done_no_fire(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"changes": [{"name": "x", "status": "done"}]},
            last_change_statuses={"x": "failed"},
        )
        assert detect_integration_failed(ctx) == []

    def test_integration_failed_failed_to_running_no_fire(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"changes": [{"name": "x", "status": "running"}]},
            last_change_statuses={"x": "failed"},
        )
        assert detect_integration_failed(ctx) == []

    def test_integration_failed_running_to_running_no_fire(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"changes": [{"name": "x", "status": "running"}]},
            last_change_statuses={"x": "running"},
        )
        assert detect_integration_failed(ctx) == []

    def test_integration_failed_daemon_restart_persisted_status_no_refire(self, tmp_project):
        """AC-41: daemon restart against pre-existing failed change should not re-fire.

        The persisted `last_change_statuses` dict is loaded by
        `read_status` on daemon start, so the first poll after restart
        sees the same prev/current and the detector stays silent.
        """
        ctx = make_ctx(
            project_path=tmp_project,
            state={"changes": [{"name": "foundation", "status": "failed"}]},
            last_change_statuses={"foundation": "failed"},
        )
        assert detect_integration_failed(ctx) == []

    def test_terminal_state_first_observation_fires(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"status": "done", "changes": []},
            orchestrator_alive=False,
            terminal_state_fired=False,
        )
        result = detect_terminal_state(ctx)
        assert len(result) == 1

    def test_terminal_state_already_fired_no_refire(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"status": "done", "changes": []},
            orchestrator_alive=False,
            terminal_state_fired=True,
        )
        assert detect_terminal_state(ctx) == []

    def test_terminal_state_alive_no_fire(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            state={"status": "done", "changes": []},
            orchestrator_alive=True,
            terminal_state_fired=False,
        )
        assert detect_terminal_state(ctx) == []

    def test_token_stall_first_crossing_fires(self, tmp_project):
        now = time.time()
        ctx = make_ctx(
            project_path=tmp_project,
            state={"changes": [{"name": "x", "status": "running", "tokens_used": 600_000}]},
            now=now,
            last_state_change_at=now - DEFAULT_TOKEN_STALL_SECS - 10,
            crossed_token_stall_thresholds=set(),
        )
        result = detect_token_stall(ctx)
        assert len(result) == 1

    def test_token_stall_already_crossed_no_refire(self, tmp_project):
        now = time.time()
        ctx = make_ctx(
            project_path=tmp_project,
            state={"changes": [{"name": "x", "status": "running", "tokens_used": 600_000}]},
            now=now,
            last_state_change_at=now - DEFAULT_TOKEN_STALL_SECS - 10,
            crossed_token_stall_thresholds={f"x:{DEFAULT_TOKEN_STALL_LIMIT}"},
        )
        assert detect_token_stall(ctx) == []


# ─── non_periodic_checkpoint ─────────────────────────────


class TestNonPeriodicCheckpoint:
    def test_fires_for_non_periodic_reason(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            new_events=[
                {"type": "CHECKPOINT", "data": {"reason": "manual"}, "ts": "2026-04-11T10:00:00Z"},
                {"type": "CHECKPOINT", "data": {"reason": "periodic"}},
            ],
        )
        result = detect_non_periodic_checkpoint(ctx)
        assert len(result) == 1
        assert result[0].context["checkpoint_reason"] == "manual"

    def test_periodic_silent(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            new_events=[{"type": "CHECKPOINT", "data": {"reason": "periodic"}}],
        )
        assert detect_non_periodic_checkpoint(ctx) == []


# ─── state_stall ─────────────────────────────────────────


class TestStateStall:
    def test_fires_after_threshold(self, tmp_project):
        now = time.time()
        ctx = make_ctx(
            project_path=tmp_project,
            state={"status": "running"},
            state_mtime=now - DEFAULT_STATE_STALL_SECS - 30,
            last_state_change_at=now - DEFAULT_STATE_STALL_SECS - 30,
            now=now,
        )
        result = detect_state_stall(ctx)
        assert len(result) == 1
        assert result[0].type == "state_stall"
        assert result[0].context["stall_seconds"] >= DEFAULT_STATE_STALL_SECS

    def test_no_fire_under_threshold(self, tmp_project):
        now = time.time()
        ctx = make_ctx(
            project_path=tmp_project,
            state={"status": "running"},
            state_mtime=now - 30,
            last_state_change_at=now - 30,
            now=now,
        )
        assert detect_state_stall(ctx) == []

    def test_no_fire_when_dead(self, tmp_project):
        now = time.time()
        ctx = make_ctx(
            project_path=tmp_project,
            state={"status": "running"},
            orchestrator_alive=False,
            state_mtime=now - 2000,
            last_state_change_at=now - 2000,
            now=now,
        )
        assert detect_state_stall(ctx) == []

    def test_threshold_accommodates_slow_llm_gates(self, tmp_project):
        """Regression for craftbrew-run-20260421-0025: spec_verify took 412s.

        An LLM gate that legitimately runs ~400s must NOT trip state_stall.
        This test locks the threshold at ≥ 600s so any future tightening
        below that point requires deliberate revisit.
        """
        assert DEFAULT_STATE_STALL_SECS >= 600, (
            "state_stall threshold must not drop below 600s — that would "
            "false-alarm on legitimate LLM gates (spec_verify, review) which "
            "routinely take 5-7 minutes during synchronous Anthropic API calls."
        )

        # And the positive case: a 450s stall (typical slow LLM gate) must NOT fire.
        now = time.time()
        ctx = make_ctx(
            project_path=tmp_project,
            state={"status": "running"},
            state_mtime=now - 450,
            last_state_change_at=now - 450,
            now=now,
        )
        assert detect_state_stall(ctx) == [], \
            "450s stall (normal slow LLM gate) triggered state_stall false alarm"


# ─── token_stall ─────────────────────────────────────────


class TestTokenStall:
    def test_fires_above_limit_with_stall(self, tmp_project):
        now = time.time()
        state = {
            "changes": [
                {
                    "name": "hot",
                    "status": "running",
                    "tokens_used": DEFAULT_TOKEN_STALL_LIMIT + 100,
                },
            ],
        }
        ctx = make_ctx(
            project_path=tmp_project,
            state=state,
            last_state_change_at=now - DEFAULT_TOKEN_STALL_SECS - 60,
            now=now,
        )
        result = detect_token_stall(ctx)
        assert len(result) == 1
        assert result[0].change == "hot"

    def test_no_fire_under_token_limit(self, tmp_project):
        now = time.time()
        state = {"changes": [{"name": "x", "status": "running", "tokens_used": 100}]}
        ctx = make_ctx(
            project_path=tmp_project, state=state,
            last_state_change_at=now - 5000, now=now,
        )
        assert detect_token_stall(ctx) == []

    def test_no_fire_recent_progress(self, tmp_project):
        now = time.time()
        state = {
            "changes": [
                {"name": "x", "status": "running", "tokens_used": 999_999},
            ],
        }
        ctx = make_ctx(
            project_path=tmp_project, state=state,
            last_state_change_at=now - 60, now=now,
        )
        assert detect_token_stall(ctx) == []


# ─── unknown_event_type ──────────────────────────────────


class TestUnknownEventType:
    def test_fires_once_per_new_type(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            new_events=[
                {"type": "STATE_CHANGE"},   # known
                {"type": "MYSTERY_EVENT"},  # unknown
                {"type": "MYSTERY_EVENT"},  # second occurrence — silent
            ],
        )
        result = detect_unknown_event_type(ctx)
        assert len(result) == 1
        assert result[0].context["event_type"] == "MYSTERY_EVENT"
        # Side-effect: known set updated
        assert "MYSTERY_EVENT" in ctx.known_event_types

    def test_known_set_silences_future_calls(self, tmp_project):
        ctx = make_ctx(
            project_path=tmp_project,
            new_events=[{"type": "MYSTERY_EVENT"}],
            known_event_types={"MYSTERY_EVENT"},
        )
        assert detect_unknown_event_type(ctx) == []


# ─── error_rate_spike ────────────────────────────────────


class TestErrorRateSpike:
    def test_no_fire_until_baseline_built(self, tmp_project):
        log = tmp_project / "orch.log"
        log.write_text("INFO normal\n WARNING something\n WARNING again\n")
        ctx = make_ctx(
            project_path=tmp_project,
            log_path=log,
            log_size=log.stat().st_size,
            last_log_size=0,
            error_baseline={},
        )
        # Baseline starts at 0 — first sample seeds it but cannot trigger
        assert detect_error_rate_spike(ctx) == []
        assert ctx.error_baseline.get("avg_per_window", 0) > 0

    def test_fires_on_3x_spike_after_baseline(self, tmp_project):
        log = tmp_project / "orch.log"
        # Build a log with a baseline of ~2 warns and a fresh slice with 20
        body = " WARNING noise\n" * 2 + " ERROR boom\n" * 20
        log.write_text(body)
        ctx = make_ctx(
            project_path=tmp_project,
            log_path=log,
            log_size=log.stat().st_size,
            last_log_size=0,
            error_baseline={"avg_per_window": 5.0},
        )
        result = detect_error_rate_spike(ctx)
        assert len(result) == 1
        assert result[0].type == "error_rate_spike"
        assert result[0].context["error_count"] >= 1

    def test_no_fire_when_no_new_log(self, tmp_project):
        log = tmp_project / "orch.log"
        log.write_text("noise\n")
        ctx = make_ctx(
            project_path=tmp_project,
            log_path=log,
            log_size=log.stat().st_size,
            last_log_size=log.stat().st_size,  # no growth
            error_baseline={"avg_per_window": 100.0},
        )
        assert detect_error_rate_spike(ctx) == []


# ─── log_silence ─────────────────────────────────────────


class TestLogSilence:
    def test_fires_when_silent_past_threshold(self, tmp_project):
        log = tmp_project / "orch.log"
        log.write_text("just one line\n")
        now = time.time()
        size = log.stat().st_size
        ctx = make_ctx(
            project_path=tmp_project,
            log_path=log,
            log_size=size,
            last_log_size=size,    # no growth
            last_log_growth_at=now - DEFAULT_LOG_SILENCE_SECS - 60,
            now=now,
        )
        result = detect_log_silence(ctx)
        assert len(result) == 1
        assert result[0].type == "log_silence"

    def test_no_fire_when_log_grew(self, tmp_project):
        log = tmp_project / "orch.log"
        log.write_text("a\nb\nc\n")
        now = time.time()
        ctx = make_ctx(
            project_path=tmp_project,
            log_path=log,
            log_size=log.stat().st_size,
            last_log_size=log.stat().st_size - 2,
            last_log_growth_at=now - DEFAULT_LOG_SILENCE_SECS - 60,
            now=now,
        )
        assert detect_log_silence(ctx) == []

    def test_no_fire_when_dead(self, tmp_project):
        log = tmp_project / "orch.log"
        log.write_text("x\n")
        now = time.time()
        ctx = make_ctx(
            project_path=tmp_project,
            orchestrator_alive=False,
            log_path=log,
            log_size=log.stat().st_size,
            last_log_size=log.stat().st_size,
            last_log_growth_at=now - 9999,
            now=now,
        )
        assert detect_log_silence(ctx) == []


# ─── scan_for_anomalies (priority sort) ──────────────────


class TestScanForAnomalies:
    def test_priority_sort(self, tmp_project):
        # Build inputs that cause MULTIPLE detectors to fire and verify
        # the result is sorted by priority (terminal_state first).
        state = {
            "status": "done",
            "changes": [{"name": "foo", "status": "integration-failed"}],
        }
        ctx = make_ctx(
            project_path=tmp_project,
            state=state,
            orchestrator_alive=False,
            new_events=[{"type": "MYSTERY"}],
        )
        result = scan_for_anomalies(ctx)
        types = [t.type for t in result]
        assert types[0] == "terminal_state"  # priority 1
        assert "integration_failed" in types
        assert "unknown_event_type" in types
        # Priorities are non-decreasing
        priorities = [t.priority for t in result]
        assert priorities == sorted(priorities)


# ─── _classify_exit (permanent errors) ────────────────────


class TestClassifyExit:
    def test_spec_not_found(self):
        assert _classify_exit("Error: Spec file not found: docs/spec.md\n") == "spec_not_found"

    def test_spec_not_found_alt(self):
        assert _classify_exit("FileNotFoundError: [Errno 2] No such file or directory: 'docs/missing.md'") == "spec_not_found"

    def test_orchestrator_import_broken_module(self):
        assert _classify_exit("ModuleNotFoundError: No module named 'set_orch.engine'") == "orchestrator_import_broken"

    def test_orchestrator_import_broken_importerror(self):
        assert _classify_exit("ImportError: cannot import name 'foo' from 'bar'") == "orchestrator_import_broken"

    def test_orchestrator_binary_missing(self):
        assert _classify_exit("set-orchestrate: command not found\n") == "orchestrator_binary_missing"

    def test_directives_missing(self):
        assert _classify_exit("Error: No directives file at path") == "directives_missing"

    def test_state_file_missing(self):
        assert _classify_exit("Error: State file not found: foo.json") == "state_file_missing"

    def test_profile_resolution_failed(self):
        assert _classify_exit("ProfileResolutionError: plugin not loaded") == "profile_resolution_failed"

    def test_empty_stderr_returns_none(self):
        assert _classify_exit("") is None

    def test_python_traceback_is_transient(self):
        tb = (
            "Traceback (most recent call last):\n"
            "  File \"engine.py\", line 10, in <module>\n"
            "    run()\n"
            "RuntimeError: something went wrong\n"
        )
        assert _classify_exit(tb) is None

    def test_random_stderr_is_transient(self):
        assert _classify_exit("warning: something noisy but retryable\n") is None

    def test_every_cataloged_pattern_has_test_coverage(self):
        """Regression guard: every PERMANENT_ERROR_SIGNALS entry must match when fed literally."""
        for pattern, expected in PERMANENT_ERROR_SIGNALS:
            assert _classify_exit(pattern) == expected, (
                f"Pattern {pattern!r} did not classify as {expected!r}"
            )
