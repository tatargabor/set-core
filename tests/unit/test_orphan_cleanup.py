"""Unit tests for sentinel orphan cleanup."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.lib import test_paths as tp

from set_orch.engine import _cleanup_orphans, _has_process_in_dir


@pytest.fixture
def state_dir(tmp_path):
    """Create a minimal orchestration state for testing."""
    state_file = tp.state_file(tmp_path)
    # Initialize git repo
    import subprocess
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=tmp_path, capture_output=True)
    (tmp_path / "dummy.txt").write_text("init")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    return state_file


def _write_state(state_file, changes, merge_queue=None):
    """Write a test orchestration state."""
    state = {
        "status": "running",
        "plan_version": 1,
        "changes": changes,
        "merge_queue": list(merge_queue or []),
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


class TestRestoreOrphanedIntegrating:
    """Regression: supervisor restart while a change is status=integrating.

    status=integrating is set by _integrate_main_into_branch at the START of
    the verify pipeline (before gates run), NOT during merge. On restart we
    must distinguish:
      (a) gates passed, only merge_queue.append was lost → safe to re-queue
      (b) pipeline was mid-gate → must re-run gates, NOT bypass to merge
    """

    # Six pre-merge gate fields _verify_gates_already_passed inspects.
    _ALL_PASS_GATES = {
        "build_result": "pass",
        "test_result": "pass",
        "review_result": "pass",
        "scope_check": "pass",
        "e2e_result": "pass",
        "spec_coverage_result": "pass",
    }

    def test_integrating_with_gates_passed_gets_requeued(self, state_dir, tmp_path):
        """Case (a): all gates passed, just the merge_queue.append was lost."""
        wt = tmp_path / "wt-shopping-cart"
        wt.mkdir()
        _write_state(state_dir, [{
            "name": "shopping-cart",
            "status": "integrating",
            "current_step": "fixing",
            "worktree_path": str(wt),
            "scope": "", "complexity": "S",
            **self._ALL_PASS_GATES,
        }], merge_queue=[])

        _cleanup_orphans(str(state_dir))

        state = json.loads(state_dir.read_text())
        assert "shopping-cart" in state["merge_queue"]
        # Status stays integrating — execute_merge_queue will process it
        assert state["changes"][0]["status"] == "integrating"

    def test_integrating_with_gates_incomplete_resets_to_running(
        self, state_dir, tmp_path,
    ):
        """Case (b): restart mid-pipeline, some gates haven't run yet.

        Must re-enter verify pipeline via _poll_active_changes (status=running
        + ralph_pid=None triggers the dead-agent-with-loop-done path) instead
        of bypassing to merge.
        """
        wt = tmp_path / "wt-a"
        wt.mkdir()
        _write_state(state_dir, [{
            "name": "a",
            "status": "integrating",
            "current_step": "fixing",
            "worktree_path": str(wt),
            "ralph_pid": 99999999,
            "scope": "", "complexity": "S",
            # Only some gates ran before restart
            "build_result": "pass",
            "test_result": "pass",
            # review_result, scope_check, e2e_result, spec_coverage_result = None
        }], merge_queue=[])

        _cleanup_orphans(str(state_dir))

        state = json.loads(state_dir.read_text())
        ch = state["changes"][0]
        assert ch["status"] == "running"
        assert ch["ralph_pid"] is None
        assert "a" not in state["merge_queue"]

    def test_integrating_with_spec_verify_fail_resets_to_running(
        self, state_dir, tmp_path,
    ):
        """Regression: the exact craftbrew-run-20260414 scenario.

        spec_verify reported CRITICAL findings, supervisor restarted before
        retry dispatch happened. Must NOT bypass to merge.
        """
        wt = tmp_path / "wt-promotions"
        wt.mkdir()
        gates = dict(self._ALL_PASS_GATES)
        gates["spec_coverage_result"] = "fail"
        _write_state(state_dir, [{
            "name": "promotions-and-email",
            "status": "integrating",
            "current_step": "fixing",
            "worktree_path": str(wt),
            "scope": "", "complexity": "S",
            **gates,
        }], merge_queue=[])

        _cleanup_orphans(str(state_dir))

        state = json.loads(state_dir.read_text())
        ch = state["changes"][0]
        assert ch["status"] == "running"
        assert "promotions-and-email" not in state["merge_queue"]

    def test_integrating_with_review_fail_resets_to_running(
        self, state_dir, tmp_path,
    ):
        """review gate failure in the middle of the pipeline must not merge."""
        wt = tmp_path / "wt-b"
        wt.mkdir()
        gates = dict(self._ALL_PASS_GATES)
        gates["review_result"] = "fail"
        _write_state(state_dir, [{
            "name": "b",
            "status": "integrating",
            "current_step": "fixing",
            "worktree_path": str(wt),
            "scope": "", "complexity": "S",
            **gates,
        }], merge_queue=[])

        _cleanup_orphans(str(state_dir))

        state = json.loads(state_dir.read_text())
        assert state["changes"][0]["status"] == "running"
        assert "b" not in state["merge_queue"]

    def test_integrating_already_in_queue_untouched(self, state_dir, tmp_path):
        wt = tmp_path / "wt-a"
        wt.mkdir()
        _write_state(state_dir, [{
            "name": "a",
            "status": "integrating",
            "current_step": "fixing",
            "worktree_path": str(wt),
            "scope": "", "complexity": "S",
            **self._ALL_PASS_GATES,
        }], merge_queue=["a"])

        _cleanup_orphans(str(state_dir))

        state = json.loads(state_dir.read_text())
        # Still exactly one entry — we don't duplicate
        assert state["merge_queue"].count("a") == 1

    def test_integrating_without_worktree_not_requeued(self, state_dir):
        """No worktree on disk — _poll_active_changes handles this case by
        marking the change stalled. Cleanup MUST NOT requeue, otherwise
        execute_merge_queue will try to gate a non-existent worktree."""
        _write_state(state_dir, [{
            "name": "a",
            "status": "integrating",
            "current_step": "fixing",
            "worktree_path": "/tmp/this-does-not-exist-12345",
            "scope": "", "complexity": "S",
            **self._ALL_PASS_GATES,
        }], merge_queue=[])

        _cleanup_orphans(str(state_dir))

        state = json.loads(state_dir.read_text())
        assert state["merge_queue"] == []

    def test_non_integrating_not_requeued(self, state_dir, tmp_path):
        """Running / verifying / done changes are NOT requeued by this path.
        Orphaned 'done' is handled by the self-watchdog + suspended poll loops.
        """
        wt = tmp_path / "wt-a"
        wt.mkdir()
        _write_state(state_dir, [{
            "name": "a",
            "status": "verifying",
            "worktree_path": str(wt),
            "scope": "", "complexity": "S",
        }], merge_queue=[])

        _cleanup_orphans(str(state_dir))

        state = json.loads(state_dir.read_text())
        assert state["merge_queue"] == []


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
