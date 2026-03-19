"""Tests for set_orch.watchdog — timeout, hash loop, escalation, progress reset."""

import json
import os
import shutil
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.watchdog import (
    WatchdogResult,
    watchdog_check,
    watchdog_init_state,
    detect_hash_loop,
    check_progress,
    heartbeat_data,
    _escalation_action,
    _timeout_for_status,
    _compute_action_hash,
    _has_activity,
    WATCHDOG_TIMEOUT_RUNNING,
    WATCHDOG_TIMEOUT_VERIFYING,
    WATCHDOG_TIMEOUT_DISPATCHED,
    WATCHDOG_LOOP_THRESHOLD,
)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def worktree(tmp_dir):
    """Create a fake worktree with .claude/ dir."""
    wt = os.path.join(tmp_dir, "worktree")
    os.makedirs(os.path.join(wt, ".claude"))
    return wt


@pytest.fixture
def state_file(tmp_dir):
    path = os.path.join(tmp_dir, "state.json")
    with open(path, "w") as f:
        json.dump({}, f)
    return path


# ─── watchdog_init_state ─────────────────────────────────────────


class TestWatchdogInitState:
    def test_returns_baseline(self):
        ws = watchdog_init_state("test-change")
        assert ws["escalation_level"] == 0
        assert ws["consecutive_same_hash"] == 0
        assert ws["action_hash_ring"] == []
        assert ws["last_activity_epoch"] > 0

    def test_epoch_is_recent(self):
        ws = watchdog_init_state()
        assert abs(ws["last_activity_epoch"] - int(time.time())) < 2


# ─── detect_hash_loop ────────────────────────────────────────────


class TestDetectHashLoop:
    def test_no_loop_too_few(self):
        assert detect_hash_loop(["abc", "abc"], threshold=5) is False

    def test_no_loop_different_hashes(self):
        assert detect_hash_loop(["a", "b", "c", "d", "e"], threshold=5) is False

    def test_loop_detected(self):
        assert detect_hash_loop(["x", "x", "x", "x", "x"], threshold=5) is True

    def test_loop_ignores_empty_hash(self):
        assert detect_hash_loop(["", "", "", "", ""], threshold=5) is False

    def test_loop_longer_ring(self):
        ring = ["a", "b", "c", "c", "c", "c", "c"]
        assert detect_hash_loop(ring, threshold=5) is True

    def test_threshold_boundary(self):
        ring = ["x", "x", "x", "x"]
        assert detect_hash_loop(ring, threshold=4) is True
        assert detect_hash_loop(ring, threshold=5) is False


# ─── _escalation_action ─────────────────────────────────────────


class TestEscalationAction:
    def test_level_0(self):
        assert _escalation_action(0) == "warn"

    def test_level_1_warn(self):
        assert _escalation_action(1) == "warn"

    def test_level_2_restart(self):
        assert _escalation_action(2) == "restart"

    def test_level_3_redispatch(self):
        assert _escalation_action(3) == "redispatch"

    def test_level_4_fail(self):
        assert _escalation_action(4) == "fail"

    def test_level_high_fail(self):
        assert _escalation_action(99) == "fail"


# ─── _timeout_for_status ────────────────────────────────────────


class TestTimeoutForStatus:
    def test_running_default(self):
        assert _timeout_for_status("running") == WATCHDOG_TIMEOUT_RUNNING

    def test_verifying_default(self):
        assert _timeout_for_status("verifying") == WATCHDOG_TIMEOUT_VERIFYING

    def test_dispatched_default(self):
        assert _timeout_for_status("dispatched") == WATCHDOG_TIMEOUT_DISPATCHED

    def test_override(self):
        assert _timeout_for_status("running", override=999) == 999

    def test_unknown_status_defaults_to_running(self):
        assert _timeout_for_status("unknown") == WATCHDOG_TIMEOUT_RUNNING


# ─── watchdog_check ──────────────────────────────────────────────


class TestWatchdogCheck:
    def test_inactive_status_ok(self, state_file):
        state = {"changes": [{"name": "c1", "status": "merged"}]}
        result = watchdog_check("c1", state, state_file)
        assert result.action == "ok"

    def test_missing_change_ok(self, state_file):
        state = {"changes": []}
        result = watchdog_check("nonexistent", state, state_file)
        assert result.action == "ok"

    def test_activity_resets_escalation(self, worktree, state_file):
        """When loop-state mtime is newer than last_activity, reset escalation."""
        now = int(time.time())
        loop_state = os.path.join(worktree, ".claude", "loop-state.json")
        with open(loop_state, "w") as f:
            json.dump({"status": "running"}, f)

        state = {
            "changes": [
                {
                    "name": "c1",
                    "status": "running",
                    "worktree_path": worktree,
                    "watchdog": {
                        "last_activity_epoch": now - 100,  # old
                        "action_hash_ring": [],
                        "consecutive_same_hash": 3,
                        "escalation_level": 2,
                        "progress_baseline": 0,
                    },
                }
            ]
        }
        result = watchdog_check("c1", state, state_file)
        assert result.action == "ok"
        assert "reset" in result.reason

    def test_no_loop_state_artifact_grace(self, worktree, state_file):
        """If .claude/loop-state.json doesn't exist, artifact creation grace applies."""
        now = int(time.time())
        state = {
            "changes": [
                {
                    "name": "c1",
                    "status": "running",
                    "worktree_path": worktree,
                    "watchdog": {
                        "last_activity_epoch": now - 1000,
                        "action_hash_ring": [],
                        "consecutive_same_hash": 0,
                        "escalation_level": 0,
                        "progress_baseline": 0,
                    },
                }
            ]
        }
        result = watchdog_check("c1", state, state_file)
        assert result.action == "ok"
        assert "artifact creation" in result.reason

    def test_lazy_init_watchdog_state(self, state_file):
        """Watchdog state gets initialized lazily if missing."""
        state = {
            "changes": [{"name": "c1", "status": "running"}]
        }
        result = watchdog_check("c1", state, state_file)
        assert result.action == "ok"
        assert "watchdog" in state["changes"][0]


# ─── check_progress ──────────────────────────────────────────────


class TestCheckProgress:
    def test_no_worktree_path(self):
        result = check_progress("c1", {})
        assert result is None

    def test_no_loop_state_file(self, worktree):
        result = check_progress("c1", {"worktree_path": worktree})
        assert result is None

    def test_too_few_iterations(self, worktree):
        loop_state = os.path.join(worktree, ".claude", "loop-state.json")
        with open(loop_state, "w") as f:
            json.dump({"status": "running", "iterations": [{"n": 1}]}, f)

        result = check_progress("c1", {"worktree_path": worktree, "status": "running"})
        assert result is None

    def test_spinning_detected(self, worktree):
        loop_state = os.path.join(worktree, ".claude", "loop-state.json")
        iterations = [
            {"n": 1, "commits": [], "no_op": True},
            {"n": 2, "commits": [], "no_op": True},
            {"n": 3, "commits": [], "no_op": True},
        ]
        with open(loop_state, "w") as f:
            json.dump({"status": "running", "iterations": iterations}, f)

        result = check_progress("c1", {"worktree_path": worktree, "status": "running"})
        assert result == "spinning"

    def test_stuck_detected(self, worktree):
        loop_state = os.path.join(worktree, ".claude", "loop-state.json")
        iterations = [
            {"n": 1, "commits": [], "no_op": False},
            {"n": 2, "commits": [], "no_op": False},
            {"n": 3, "commits": [], "no_op": False},
        ]
        with open(loop_state, "w") as f:
            json.dump({"status": "running", "iterations": iterations}, f)

        result = check_progress("c1", {"worktree_path": worktree, "status": "running"})
        assert result == "stuck"

    def test_healthy_with_commits(self, worktree):
        loop_state = os.path.join(worktree, ".claude", "loop-state.json")
        iterations = [
            {"n": 1, "commits": ["abc"]},
            {"n": 2, "commits": []},
            {"n": 3, "commits": ["def"]},
        ]
        with open(loop_state, "w") as f:
            json.dump({"status": "running", "iterations": iterations}, f)

        result = check_progress("c1", {"worktree_path": worktree, "status": "running"})
        assert result is None

    def test_done_status_skipped(self, worktree):
        loop_state = os.path.join(worktree, ".claude", "loop-state.json")
        iterations = [
            {"n": 1, "commits": [], "no_op": True},
            {"n": 2, "commits": [], "no_op": True},
            {"n": 3, "commits": [], "no_op": True},
        ]
        with open(loop_state, "w") as f:
            json.dump({"status": "done", "iterations": iterations}, f)

        result = check_progress("c1", {"worktree_path": worktree, "status": "running"})
        assert result is None

    def test_failed_change_skipped(self, worktree):
        loop_state = os.path.join(worktree, ".claude", "loop-state.json")
        iterations = [
            {"n": 1, "commits": [], "no_op": True},
            {"n": 2, "commits": [], "no_op": True},
            {"n": 3, "commits": [], "no_op": True},
        ]
        with open(loop_state, "w") as f:
            json.dump({"status": "running", "iterations": iterations}, f)

        result = check_progress("c1", {"worktree_path": worktree, "status": "failed"})
        assert result is None

    def test_progress_baseline_filters(self, worktree):
        loop_state = os.path.join(worktree, ".claude", "loop-state.json")
        iterations = [
            {"n": 1, "commits": [], "no_op": True},
            {"n": 2, "commits": [], "no_op": True},
            {"n": 3, "commits": [], "no_op": True},
            {"n": 4, "commits": ["abc"]},
            {"n": 5, "commits": ["def"]},
            {"n": 6, "commits": ["ghi"]},
        ]
        with open(loop_state, "w") as f:
            json.dump({"status": "running", "iterations": iterations}, f)

        # With baseline=3, only iterations 4-6 are considered — they have commits
        result = check_progress(
            "c1",
            {"worktree_path": worktree, "status": "running"},
            progress_baseline=3,
        )
        assert result is None


# ─── heartbeat_data ──────────────────────────────────────────────


class TestHeartbeatData:
    def test_counts_active(self):
        state = {
            "changes": [
                {"name": "a", "status": "running"},
                {"name": "b", "status": "merged"},
                {"name": "c", "status": "verifying"},
                {"name": "d", "status": "dispatched"},
            ],
            "active_seconds": 120,
        }
        hb = heartbeat_data(state)
        assert hb["active_changes"] == 3  # running, verifying, dispatched
        assert hb["active_seconds"] == 120

    def test_empty_state(self):
        hb = heartbeat_data({})
        assert hb["active_changes"] == 0
        assert hb["active_seconds"] == 0
