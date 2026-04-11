"""End-to-end integration tests for the supervisor daemon (Phase 2 wiring).

These tests run the real `SupervisorDaemon._monitor_loop` against:
  - a real `set_orch.supervisor.anomaly.scan_for_anomalies` call
  - a real `TriggerExecutor` (not mocked)
  - a MOCKED `spawn_ephemeral_claude` (no LLM call)
  - a MOCKED orchestrator subprocess (`sleep N`)

This catches integration bugs the per-module unit tests can't:
  - daemon → context builder → anomaly scan wiring
  - status persistence between poll cycles
  - terminal_state trigger short-circuiting the loop
  - SUPERVISOR_TRIGGER events landing in orchestration-events.jsonl

Cost: ~5 seconds per test, no real Claude calls, no real orchestrator.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.supervisor import daemon as daemon_mod
from set_orch.supervisor.daemon import SupervisorConfig, SupervisorDaemon
from set_orch.supervisor.ephemeral import EphemeralResult
from set_orch.supervisor.state import read_status


@pytest.fixture
def project_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


def _build_daemon(
    project_dir: Path,
    *,
    state: dict,
    monkeypatch,
    spawn_results: list[EphemeralResult] | None = None,
    fake_orch_cmd: list[str] | None = None,
) -> tuple[SupervisorDaemon, list[dict]]:
    """Build a daemon with the runtime paths pinned to project_dir.

    Forces _resolve_runtime_paths to return project-relative paths so the
    test doesn't have to set up a git repo for SetRuntime.
    """
    state_path = project_dir / "orchestration-state.json"
    events_path = project_dir / "orchestration-events.jsonl"
    log_path = project_dir / "orchestration.log"
    state_path.write_text(json.dumps(state))
    events_path.write_text("")
    log_path.write_text("")

    monkeypatch.setattr(
        SupervisorDaemon,
        "_resolve_runtime_paths",
        lambda self: (state_path, events_path, log_path),
    )
    # Don't wait 30s on SIGTERM in tests
    monkeypatch.setattr(daemon_mod, "SIGTERM_GRACE_SECONDS", 1)

    spawn_calls: list[dict] = []

    def fake_spawn(**kwargs):
        spawn_calls.append(kwargs)
        if spawn_results:
            idx = min(len(spawn_calls) - 1, len(spawn_results) - 1)
            return spawn_results[idx]
        return EphemeralResult(
            trigger=kwargs.get("trigger", "?"),
            exit_code=0,
            timed_out=False,
            elapsed_ms=10,
            stdout_tail="VERDICT: noted",
        )

    # Mock spawn_ephemeral_claude in BOTH the triggers and canary modules.
    # Each module imported its own reference at import time.
    import set_orch.supervisor.triggers as trig_mod
    import set_orch.supervisor.canary as canary_mod
    monkeypatch.setattr(trig_mod, "spawn_ephemeral_claude", fake_spawn)
    monkeypatch.setattr(canary_mod, "spawn_ephemeral_claude", fake_spawn)

    cfg = SupervisorConfig(
        project_path=str(project_dir),
        spec="docs/spec.md",
        poll_interval=1,
    )
    daemon = SupervisorDaemon(cfg)

    # Replace executor + canary spawn_fn so the references inside the
    # executor instance also point at the mock (the executor captured the
    # symbol at __init__ time, before our monkeypatch).
    daemon._trigger_executor.spawn_fn = fake_spawn
    daemon._canary_runner.spawn_fn = fake_spawn

    # Mock the orchestrator subprocess. By default a short sleep — tests
    # that need a long-lived orch override fake_orch_cmd.
    cmd = fake_orch_cmd or ["/bin/sh", "-c", "sleep 4"]

    def fake_spawn_orchestrator():
        proc = subprocess.Popen(
            cmd,
            cwd=str(project_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        daemon._orch_proc = proc
        daemon.status.orchestrator_pid = proc.pid
        daemon.status.status = "running"
        from set_orch.supervisor.state import write_status
        write_status(daemon.project_path, daemon.status)

    daemon._spawn_orchestrator = fake_spawn_orchestrator
    return daemon, spawn_calls


def _read_event_types(project_dir: Path) -> list[str]:
    p = project_dir / "orchestration-events.jsonl"
    if not p.is_file():
        return []
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line).get("type", ""))
        except json.JSONDecodeError:
            continue
    return out


# ─── Trigger dispatch ────────────────────────────────────


class TestIntegrationFailedDispatch:
    def test_integration_failed_change_fires_ephemeral_spawn(
        self, project_dir, monkeypatch,
    ):
        state = {
            "status": "running",
            "changes": [
                {"name": "broken-change", "status": "integration-failed", "tokens_used": 100},
                {"name": "fine-change", "status": "running"},
            ],
        }
        daemon, spawn_calls = _build_daemon(
            project_dir, state=state, monkeypatch=monkeypatch,
        )

        # Pin canary so it does NOT fire (we want to assert ONLY the
        # integration_failed trigger spawned an ephemeral claude).
        from set_orch.supervisor.canary import CanaryRunner
        monkeypatch.setattr(CanaryRunner, "is_due", lambda self: False)

        exit_code = daemon.run()
        assert exit_code == 0

        # The mock orchestrator died on its own → daemon shut down cleanly.
        # During the poll cycles before death, integration_failed should
        # have fired at least once.
        triggers = [c["trigger"] for c in spawn_calls]
        assert "integration_failed" in triggers, (
            f"expected integration_failed in spawn calls, got: {triggers}"
        )

        # Status counter updated
        final = read_status(project_dir)
        assert final.trigger_counters.get("integration_failed", 0) >= 1
        # The (trigger, change) attempts dict tracks per-pair retries
        assert final.trigger_attempts.get("integration_failed:broken-change", 0) >= 1

        # SUPERVISOR_TRIGGER events landed in the events log
        types = _read_event_types(project_dir)
        assert "SUPERVISOR_TRIGGER" in types
        assert "SUPERVISOR_START" in types
        assert "SUPERVISOR_STOP" in types


class TestRetryBudgetEndToEnd:
    def test_integration_failed_stops_after_3_attempts(
        self, project_dir, monkeypatch,
    ):
        state = {
            "status": "running",
            "changes": [
                {"name": "stuck", "status": "integration-failed"},
            ],
        }
        # Long-lived orchestrator so the daemon polls many times
        daemon, spawn_calls = _build_daemon(
            project_dir,
            state=state,
            monkeypatch=monkeypatch,
            fake_orch_cmd=["/bin/sh", "-c", "sleep 10"],
        )
        from set_orch.supervisor.canary import CanaryRunner
        monkeypatch.setattr(CanaryRunner, "is_due", lambda self: False)

        # Run the daemon briefly in this thread, then signal it to stop.
        # We use a side channel: monkeypatch the executor's emit so that
        # after 3 dispatches we set _stop_requested.
        original_execute = daemon._trigger_executor.execute

        def execute_then_check(triggers):
            outcomes = original_execute(triggers)
            attempts = daemon.status.trigger_attempts.get(
                "integration_failed:stuck", 0,
            )
            if attempts >= 3:
                daemon._stop_requested = True
                daemon._stop_reason = "test_done"
            return outcomes

        daemon._trigger_executor.execute = execute_then_check  # type: ignore[assignment]

        exit_code = daemon.run()
        assert exit_code == 0

        # Exactly 3 dispatches (the budget for integration_failed)
        spawned_triggers = [c["trigger"] for c in spawn_calls if c["trigger"] == "integration_failed"]
        assert len(spawned_triggers) == 3

        # Subsequent attempts emit a "skipped" event (we triggered stop
        # right after 3, so likely none — but if any extra polls happened
        # they MUST be skipped, never spawned)
        assert daemon.status.trigger_attempts["integration_failed:stuck"] == 3


class TestTerminalStateShortCircuit:
    def test_terminal_state_fires_then_daemon_exits(
        self, project_dir, monkeypatch,
    ):
        # State already in terminal status — but we tell the daemon the
        # orchestrator is dead via a tiny `true` subprocess.
        state = {
            "status": "done",
            "changes": [{"name": "x", "status": "merged"}],
        }
        daemon, spawn_calls = _build_daemon(
            project_dir,
            state=state,
            monkeypatch=monkeypatch,
            fake_orch_cmd=["/bin/true"],
        )
        from set_orch.supervisor.canary import CanaryRunner
        monkeypatch.setattr(CanaryRunner, "is_due", lambda self: False)

        exit_code = daemon.run()
        assert exit_code == 0

        # terminal_state should have been the trigger that fired
        triggers = [c["trigger"] for c in spawn_calls]
        assert "terminal_state" in triggers, (
            f"expected terminal_state, got: {triggers}"
        )

        final = read_status(project_dir)
        # The daemon's stop_reason should reflect either terminal_state or
        # orchestrator_done — whichever path won the race
        assert final.status == "stopped"
