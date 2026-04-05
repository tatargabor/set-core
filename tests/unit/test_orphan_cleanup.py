"""Unit tests for sentinel orphan cleanup."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from set_orch.engine import _cleanup_orphans, _has_process_in_dir


@pytest.fixture
def state_dir(tmp_path):
    """Create a minimal orchestration state for testing."""
    state_file = tmp_path / "orchestration-state.json"
    # Initialize git repo
    import subprocess
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=tmp_path, capture_output=True)
    (tmp_path / "dummy.txt").write_text("init")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    return state_file


def _write_state(state_file, changes):
    """Write a test orchestration state."""
    state = {
        "status": "running",
        "plan_version": 1,
        "changes": changes,
    }
    state_file.write_text(json.dumps(state, indent=2))


class TestStalePidCleanup:
    def test_dead_pid_merged_sets_done(self, state_dir):
        _write_state(state_dir, [{
            "name": "test-change",
            "status": "merged",
            "current_step": "integrating",
            "ralph_pid": 99999999,  # guaranteed dead PID
            "scope": "", "complexity": "S",
        }])

        _cleanup_orphans(str(state_dir))

        state = json.loads(state_dir.read_text())
        ch = state["changes"][0]
        assert ch["ralph_pid"] is None
        assert ch["current_step"] == "done"

    def test_dead_pid_running_sets_stalled(self, state_dir):
        _write_state(state_dir, [{
            "name": "test-change",
            "status": "running",
            "current_step": "planning",
            "ralph_pid": 99999999,
            "scope": "", "complexity": "S",
        }])

        _cleanup_orphans(str(state_dir))

        state = json.loads(state_dir.read_text())
        ch = state["changes"][0]
        assert ch["ralph_pid"] is None
        assert ch["status"] == "stalled"

    def test_live_pid_not_cleared(self, state_dir):
        my_pid = os.getpid()  # this process is alive
        _write_state(state_dir, [{
            "name": "test-change",
            "status": "running",
            "current_step": "planning",
            "ralph_pid": my_pid,
            "scope": "", "complexity": "S",
        }])

        _cleanup_orphans(str(state_dir))

        state = json.loads(state_dir.read_text())
        ch = state["changes"][0]
        assert ch["ralph_pid"] == my_pid  # not cleared
        assert ch["status"] == "running"  # not stalled


class TestStuckStepCleanup:
    def test_merged_integrating_fixed(self, state_dir):
        _write_state(state_dir, [{
            "name": "test-change",
            "status": "merged",
            "current_step": "integrating",
            "scope": "", "complexity": "S",
        }])

        _cleanup_orphans(str(state_dir))

        state = json.loads(state_dir.read_text())
        assert state["changes"][0]["current_step"] == "done"

    def test_merged_done_unchanged(self, state_dir):
        _write_state(state_dir, [{
            "name": "test-change",
            "status": "merged",
            "current_step": "done",
            "scope": "", "complexity": "S",
        }])

        _cleanup_orphans(str(state_dir))

        state = json.loads(state_dir.read_text())
        assert state["changes"][0]["current_step"] == "done"

    def test_running_step_not_touched(self, state_dir):
        _write_state(state_dir, [{
            "name": "test-change",
            "status": "running",
            "current_step": "fixing",
            "scope": "", "complexity": "S",
        }])

        _cleanup_orphans(str(state_dir))

        state = json.loads(state_dir.read_text())
        assert state["changes"][0]["current_step"] == "fixing"


class TestNoCleanupNeeded:
    def test_clean_state_no_modifications(self, state_dir):
        _write_state(state_dir, [{
            "name": "test-change",
            "status": "merged",
            "current_step": "done",
            "scope": "", "complexity": "S",
        }])

        # Should not raise, should not modify
        _cleanup_orphans(str(state_dir))

        state = json.loads(state_dir.read_text())
        assert state["changes"][0]["status"] == "merged"
        assert state["changes"][0]["current_step"] == "done"


class TestHasProcessInDir:
    def test_current_dir_has_process(self):
        # Our own process has CWD somewhere
        cwd = os.getcwd()
        assert _has_process_in_dir(cwd) is True

    def test_nonexistent_dir(self):
        assert _has_process_in_dir("/tmp/nonexistent-dir-12345") is False

    @pytest.mark.skipif(not os.path.isdir("/proc"), reason="Linux-only test")
    def test_empty_tmpdir(self, tmp_path):
        # Fresh tmp dir — no process should have CWD there
        assert _has_process_in_dir(str(tmp_path)) is False
