"""Unit tests for lib/set_orch/supervisor/ Phase 1 MVP.

Covers:
- state.py: SupervisorStatus persistence (atomic write, read, schema evolution)
- inbox.py: Python inbox reader, classify_message
- daemon.py: basic lifecycle with a mock subprocess (echo "alive" + sleep)

Phase 2 integration tests (anomaly detection + canary) live in a separate
test file once the anomaly module lands.
"""

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from tests.lib import test_paths as tp

from set_orch.supervisor.inbox import (
    InboxMessage,
    classify_message,
    read_new_messages,
)
from set_orch.supervisor.state import SupervisorStatus, read_status, write_status


@pytest.fixture
def project_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


# ─── state.py ────────────────────────────────────────────


class TestSupervisorStatusPersistence:
    def test_default_status_fields(self):
        s = SupervisorStatus()
        assert s.daemon_pid == 0
        assert s.orchestrator_pid == 0
        assert s.poll_cycle == 0
        assert s.rapid_crashes == 0
        assert s.events_cursor == 0
        assert s.status == "starting"
        assert s.trigger_counters == {}

    def test_write_read_round_trip(self, project_dir):
        s = SupervisorStatus(
            daemon_pid=12345,
            orchestrator_pid=67890,
            poll_cycle=5,
            rapid_crashes=1,
            events_cursor=2048,
            status="running",
            spec="docs/spec.md",
        )
        write_status(project_dir, s)
        read = read_status(project_dir)
        assert read.daemon_pid == 12345
        assert read.orchestrator_pid == 67890
        assert read.poll_cycle == 5
        assert read.rapid_crashes == 1
        assert read.events_cursor == 2048
        assert read.status == "running"
        assert read.spec == "docs/spec.md"

    def test_read_missing_returns_default(self, project_dir):
        # No status file written yet
        s = read_status(project_dir)
        assert s.daemon_pid == 0
        assert s.status == "starting"

    def test_atomic_write_does_not_leave_tmp_files(self, project_dir):
        s = SupervisorStatus(daemon_pid=1)
        write_status(project_dir, s)
        tmp_files = list((project_dir / ".set" / "supervisor").glob("*.tmp"))
        assert tmp_files == []

    def test_unknown_fields_in_json_are_dropped(self, project_dir):
        status_path = project_dir / ".set" / "supervisor" / "status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps({
            "daemon_pid": 999,
            "status": "running",
            "unknown_field_from_future": "whatever",
            "another_unknown": 42,
        }))
        # Reading should not raise; unknown fields silently dropped
        s = read_status(project_dir)
        assert s.daemon_pid == 999
        assert s.status == "running"

    def test_corrupt_json_returns_default(self, project_dir):
        status_path = project_dir / ".set" / "supervisor" / "status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text("{this is not json")
        s = read_status(project_dir)
        assert s.daemon_pid == 0


# ─── inbox.py ────────────────────────────────────────────


class TestInboxClassification:
    def test_classify_stop_english(self):
        msg = InboxMessage(sender="user", content="stop", timestamp="")
        assert classify_message(msg) == "stop"

    def test_classify_stop_hungarian(self):
        msg = InboxMessage(sender="user", content="állj le", timestamp="")
        assert classify_message(msg) == "stop"

    def test_classify_stop_phrase(self):
        msg = InboxMessage(sender="user", content="ne restartolj, csak állj", timestamp="")
        assert classify_message(msg) == "stop"

    def test_classify_status(self):
        msg = InboxMessage(sender="user", content="status", timestamp="")
        assert classify_message(msg) == "status"

    def test_classify_status_hungarian(self):
        msg = InboxMessage(sender="user", content="mi az állapot?", timestamp="")
        assert classify_message(msg) == "status"

    def test_classify_other(self):
        msg = InboxMessage(sender="user", content="érdekes dolog történt", timestamp="")
        assert classify_message(msg) == "other"

    def test_classify_empty(self):
        msg = InboxMessage(sender="user", content="   ", timestamp="")
        assert classify_message(msg) == "other"


class TestInboxReading:
    def test_empty_inbox_returns_empty_list(self, project_dir):
        assert read_new_messages(project_dir) == []

    def test_read_single_message(self, project_dir):
        inbox = project_dir / ".set" / "sentinel" / "inbox.jsonl"
        inbox.parent.mkdir(parents=True, exist_ok=True)
        inbox.write_text(json.dumps({
            "from": "tg",
            "content": "stop",
            "timestamp": "2026-04-11T18:00:00Z",
        }) + "\n")

        msgs = read_new_messages(project_dir)
        assert len(msgs) == 1
        assert msgs[0].sender == "tg"
        assert msgs[0].content == "stop"

    def test_cursor_prevents_rereading(self, project_dir):
        inbox = project_dir / ".set" / "sentinel" / "inbox.jsonl"
        inbox.parent.mkdir(parents=True, exist_ok=True)
        inbox.write_text(json.dumps({"from": "a", "content": "status"}) + "\n")

        first = read_new_messages(project_dir)
        assert len(first) == 1

        # Second read returns empty — cursor has advanced
        second = read_new_messages(project_dir)
        assert second == []

    def test_new_message_after_cursor_is_read(self, project_dir):
        inbox = project_dir / ".set" / "sentinel" / "inbox.jsonl"
        inbox.parent.mkdir(parents=True, exist_ok=True)
        inbox.write_text(json.dumps({"from": "a", "content": "status"}) + "\n")
        read_new_messages(project_dir)  # advance cursor

        # Append a new message
        with open(inbox, "a") as f:
            f.write(json.dumps({"from": "b", "content": "stop"}) + "\n")

        msgs = read_new_messages(project_dir)
        assert len(msgs) == 1
        assert msgs[0].sender == "b"
        assert msgs[0].content == "stop"

    def test_malformed_lines_are_skipped(self, project_dir):
        inbox = project_dir / ".set" / "sentinel" / "inbox.jsonl"
        inbox.parent.mkdir(parents=True, exist_ok=True)
        inbox.write_text(
            json.dumps({"from": "a", "content": "status"}) + "\n"
            + "not json at all\n"
            + json.dumps({"from": "b", "content": "stop"}) + "\n"
        )
        msgs = read_new_messages(project_dir)
        assert len(msgs) == 2
        assert msgs[0].sender == "a"
        assert msgs[1].sender == "b"


# ─── daemon.py — basic lifecycle ────────────────────────


class TestDaemonLifecycle:
    """Smoke tests for the daemon main loop using a short-lived subprocess.

    We use `sh -c "sleep 3"` as the mock orchestrator so the daemon's
    _monitor_loop detects the child exiting and shuts down cleanly. These
    tests verify:

    - daemon startup writes status.json
    - SUPERVISOR_START event is emitted
    - orchestrator subprocess is spawned
    - orchestrator clean exit → daemon shuts down with stop_reason
    - SUPERVISOR_STOP event is emitted
    """

    def test_daemon_starts_spawns_orch_and_shuts_down_on_clean_exit(self, project_dir):
        from set_orch.supervisor.daemon import SupervisorConfig, SupervisorDaemon

        # Create a minimal state file so "project_path" is valid
        (tp.state_file(project_dir)).write_text(
            json.dumps({"status": "running", "changes": []})
        )

        cfg = SupervisorConfig(
            project_path=str(project_dir),
            spec="docs/spec.md",
            orch_binary="/bin/sh",
            orch_extra_args=["-c", "sleep 1"],
            poll_interval=1,
        )
        # Avoid the "start --spec" arg-prefix that the real orchestrator expects
        # by patching _spawn_orchestrator inline
        daemon = SupervisorDaemon(cfg)

        import subprocess
        original_spawn = daemon._spawn_orchestrator

        def fake_spawn():
            log_dir = project_dir / ".set" / "supervisor" / "orch-logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            proc = subprocess.Popen(
                ["/bin/sh", "-c", "sleep 1"],
                cwd=str(project_dir),
                stdout=open(log_dir / "mock.log", "wb"),
                stderr=subprocess.STDOUT,
            )
            daemon._orch_proc = proc
            daemon.status.orchestrator_pid = proc.pid
            daemon.status.status = "running"
            from set_orch.supervisor.state import write_status
            write_status(daemon.project_path, daemon.status)

        daemon._spawn_orchestrator = fake_spawn

        exit_code = daemon.run()

        # Exit 0 expected on clean shutdown
        assert exit_code == 0

        # Status file shows stopped state
        final_status = read_status(project_dir)
        assert final_status.status == "stopped"
        assert "orchestrator" in (final_status.stop_reason or "")

        # Event log has SUPERVISOR_START + SUPERVISOR_STOP
        events_path = tp.events_file(project_dir)
        assert events_path.is_file()
        lines = events_path.read_text().strip().splitlines()
        event_types = []
        for line in lines:
            try:
                event_types.append(json.loads(line).get("type", ""))
            except json.JSONDecodeError:
                pass
        assert "SUPERVISOR_START" in event_types
        assert "SUPERVISOR_STOP" in event_types

    def test_inbox_stop_triggers_graceful_shutdown(self, project_dir, monkeypatch):
        from set_orch.supervisor import daemon as daemon_mod
        from set_orch.supervisor.daemon import SupervisorConfig, SupervisorDaemon

        # Shorten the SIGTERM grace so the test doesn't block 30s waiting for
        # the fake orchestrator to die
        monkeypatch.setattr(daemon_mod, "SIGTERM_GRACE_SECONDS", 2)

        (tp.state_file(project_dir)).write_text(
            json.dumps({"status": "running", "changes": []})
        )

        # Pre-seed the inbox with a "stop" message so the daemon picks it up on
        # the first poll cycle
        inbox = project_dir / ".set" / "sentinel" / "inbox.jsonl"
        inbox.parent.mkdir(parents=True, exist_ok=True)
        inbox.write_text(json.dumps({
            "from": "test",
            "content": "stop please",
            "timestamp": "2026-04-11T18:00:00Z",
        }) + "\n")

        cfg = SupervisorConfig(
            project_path=str(project_dir),
            spec="docs/spec.md",
            poll_interval=1,
        )
        daemon = SupervisorDaemon(cfg)

        import subprocess

        def fake_spawn():
            proc = subprocess.Popen(
                ["/bin/sh", "-c", "sleep 30"],
                cwd=str(project_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            daemon._orch_proc = proc
            daemon.status.orchestrator_pid = proc.pid

        daemon._spawn_orchestrator = fake_spawn

        t0 = time.time()
        exit_code = daemon.run()
        elapsed = time.time() - t0

        # Should exit within a few seconds (inbox stop → graceful shutdown).
        # With SIGTERM_GRACE_SECONDS=2 (monkeypatched), worst case is
        # poll + check + terminate + 2s grace + kill = ~5s
        assert elapsed < 10, f"daemon took {elapsed}s to honor inbox stop"
        assert exit_code == 0

        final_status = read_status(project_dir)
        assert final_status.status == "stopped"
        assert "inbox_stop" in (final_status.stop_reason or "")


class TestRapidCrashesResetOnPlanCompletion:
    """Task 6.9 — reset rapid_crashes when plan completes cleanly."""

    def _make_daemon(self, project_dir, rapid_crashes=2):
        from set_orch.supervisor.daemon import SupervisorConfig, SupervisorDaemon
        cfg = SupervisorConfig(
            project_path=str(project_dir),
            spec="docs/spec.md",
            orch_binary="/bin/sh",
        )
        daemon = SupervisorDaemon(cfg)
        daemon.status.rapid_crashes = rapid_crashes
        daemon.status.rapid_crashes_window_start = time.time()
        return daemon

    def test_reset_when_all_changes_terminal_no_replan(self, project_dir):
        daemon = self._make_daemon(project_dir, rapid_crashes=2)
        before = time.time()
        state = {
            "status": "done",
            "changes": [
                {"name": "a", "status": "merged"},
                {"name": "b", "status": "skipped"},
                {"name": "c", "status": "failed"},
            ],
        }
        daemon._maybe_reset_rapid_crashes(state)
        assert daemon.status.rapid_crashes == 0
        # Window anchor advances to "now" (not left at epoch 0.0), so the
        # next crash starts a fresh rapid-crash window.
        assert daemon.status.rapid_crashes_window_start >= before

    def test_no_reset_mid_plan_with_running_change(self, project_dir):
        daemon = self._make_daemon(project_dir, rapid_crashes=2)
        state = {
            "status": "running",
            "changes": [
                {"name": "a", "status": "merged"},
                {"name": "b", "status": "running"},
            ],
        }
        daemon._maybe_reset_rapid_crashes(state)
        assert daemon.status.rapid_crashes == 2

    def test_no_reset_during_replan_attempt(self, project_dir):
        daemon = self._make_daemon(project_dir, rapid_crashes=2)
        state = {
            "status": "running",
            "replan_attempt": 1,
            "changes": [
                {"name": "a", "status": "merged"},
                {"name": "b", "status": "failed"},
            ],
        }
        daemon._maybe_reset_rapid_crashes(state)
        assert daemon.status.rapid_crashes == 2

    def test_no_op_when_counter_already_zero(self, project_dir):
        daemon = self._make_daemon(project_dir, rapid_crashes=0)
        daemon.status.rapid_crashes_window_start = 123.4
        state = {"changes": [{"name": "a", "status": "done"}]}
        daemon._maybe_reset_rapid_crashes(state)
        # window_start should NOT be clobbered on no-op
        assert daemon.status.rapid_crashes == 0
        assert daemon.status.rapid_crashes_window_start == 123.4

    def test_no_reset_when_changes_list_empty(self, project_dir):
        daemon = self._make_daemon(project_dir, rapid_crashes=3)
        state = {"status": "running", "changes": []}
        daemon._maybe_reset_rapid_crashes(state)
        assert daemon.status.rapid_crashes == 3
