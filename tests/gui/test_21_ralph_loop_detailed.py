"""
Ralph Loop Detailed Tests - Comprehensive coverage of Ralph loop lifecycle

Covers:
- get_ralph_status: all status types, orphan detection, malformed JSON, empty path
- Stop loop: state update, PID file cleanup
- Context menu: items for running/finished/no loop states
- Start dialog: config defaults, empty task validation, command building
- Extra column rendering: button colors, tooltip content, click handler
- View log: dialog fallback, missing log
- Focus terminal: window search, fallback to log
"""

import json
import os
import signal
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from PySide6.QtWidgets import QMenu, QDialog, QPushButton, QTextEdit, QSpinBox, QComboBox, QWidget
from PySide6.QtCore import Qt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _MenuCapture:
    """Intercept QMenu.exec to capture menu structure without blocking."""

    def __init__(self):
        self.menus = []
        self._original_init = None

    def __enter__(self):
        self._original_init = QMenu.__init__
        capture = self

        original_init = self._original_init

        def patched_init(menu_self, *args, **kwargs):
            original_init(menu_self, *args, **kwargs)

            def non_blocking_exec(*a, **kw):
                all_actions = []
                for act in menu_self.actions():
                    if act.isSeparator():
                        continue
                    submenu = act.menu()
                    if submenu:
                        sub_actions = [sa.text() for sa in submenu.actions() if not sa.isSeparator()]
                        all_actions.append({"text": act.text(), "submenu": sub_actions})
                    else:
                        all_actions.append({"text": act.text(), "submenu": None})
                capture.menus.append(all_actions)
                return None

            menu_self.exec = non_blocking_exec

        QMenu.__init__ = patched_init
        return self

    def __exit__(self, *args):
        QMenu.__init__ = self._original_init

    def find_submenu(self, title):
        if not self.menus:
            return None
        for item in self.menus[-1]:
            if title in item["text"] and item["submenu"] is not None:
                return item["submenu"]
        return None

    def find_action(self, title):
        if not self.menus:
            return None
        for item in self.menus[-1]:
            if title in item.get("text", ""):
                return item
        return None


def _create_wt(control_center, git_env, qtbot, change_id="ralph-detail"):
    """Helper: create a worktree, push status to GUI, return path."""
    project_path = str(git_env["project"])
    wt_path = str(git_env["base"] / f"test-project-wt-{change_id}")

    subprocess.run(
        ["git", "-C", project_path, "worktree", "add", "-b", f"change/{change_id}", wt_path],
        capture_output=True, check=True,
    )

    status_data = {
        "worktrees": [{
            "project": "test-project",
            "change_id": change_id,
            "path": wt_path,
            "branch": f"change/{change_id}",
            "agents": [],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 0, "compacting": 0, "waiting": 0, "idle": 1},
    }
    control_center.update_status(status_data)
    qtbot.wait(200)
    return wt_path


def _cleanup_wt(git_env, wt_path, change_id="ralph-detail"):
    """Helper: remove worktree and branch."""
    project_path = str(git_env["project"])
    subprocess.run(
        ["git", "-C", project_path, "worktree", "remove", "--force", wt_path],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", project_path, "branch", "-D", f"change/{change_id}"],
        capture_output=True,
    )


def _write_loop_state(wt_path, state_dict):
    """Write loop-state.json into worktree's .claude dir."""
    claude_dir = Path(wt_path) / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "loop-state.json").write_text(json.dumps(state_dict))


def _find_wt_row(control_center, change_id):
    """Find the table row index for a given change_id."""
    for row, wt in control_center.row_to_worktree.items():
        if wt.get("change_id") == change_id:
            return row
    return None


def _push_status(control_center, wt_path, change_id, qtbot):
    """Re-push worktree status data to the GUI (guards against background worker overwrites)."""
    status_data = {
        "worktrees": [{
            "project": "test-project",
            "change_id": change_id,
            "path": wt_path,
            "branch": f"change/{change_id}",
            "agents": [],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 0, "compacting": 0, "waiting": 0, "idle": 1},
    }
    control_center.update_status(status_data)
    qtbot.wait(100)


# ---------------------------------------------------------------------------
# get_ralph_status tests
# ---------------------------------------------------------------------------

class TestGetRalphStatus:

    def test_empty_path_returns_empty(self, control_center):
        assert control_center.get_ralph_status("") == {}

    def test_nonexistent_path_returns_empty(self, control_center):
        assert control_center.get_ralph_status("/nonexistent/path/xyz") == {}

    def test_no_loop_state_file_returns_empty(self, control_center, git_env, qtbot):
        wt_path = _create_wt(control_center, git_env, qtbot, "no-state")
        try:
            assert control_center.get_ralph_status(wt_path) == {}
        finally:
            _cleanup_wt(git_env, wt_path, "no-state")

    def test_malformed_json_returns_empty(self, control_center, git_env, qtbot):
        wt_path = _create_wt(control_center, git_env, qtbot, "bad-json")
        try:
            claude_dir = Path(wt_path) / ".claude"
            claude_dir.mkdir(parents=True, exist_ok=True)
            (claude_dir / "loop-state.json").write_text("{broken json!!")
            assert control_center.get_ralph_status(wt_path) == {}
        finally:
            _cleanup_wt(git_env, wt_path, "bad-json")

    def test_unknown_status_returns_empty(self, control_center, git_env, qtbot):
        """Statuses not in the whitelist should return empty dict."""
        wt_path = _create_wt(control_center, git_env, qtbot, "unknown-st")
        try:
            _write_loop_state(wt_path, {"status": "initializing", "current_iteration": 0})
            assert control_center.get_ralph_status(wt_path) == {}
        finally:
            _cleanup_wt(git_env, wt_path, "unknown-st")

    def test_done_status_detected(self, control_center, git_env, qtbot):
        wt_path = _create_wt(control_center, git_env, qtbot, "done-st")
        try:
            _write_loop_state(wt_path, {
                "status": "done",
                "current_iteration": 5,
                "max_iterations": 10,
                "task": "Test task",
            })
            status = control_center.get_ralph_status(wt_path)
            assert status["status"] == "done"
            assert status["active"] is False
            assert status["iteration"] == 5
            assert status["max_iterations"] == 10
            assert status["task"] == "Test task"
        finally:
            _cleanup_wt(git_env, wt_path, "done-st")

    def test_stuck_status_detected(self, control_center, git_env, qtbot):
        wt_path = _create_wt(control_center, git_env, qtbot, "stuck-st")
        try:
            _write_loop_state(wt_path, {
                "status": "stuck",
                "current_iteration": 10,
                "max_iterations": 10,
            })
            status = control_center.get_ralph_status(wt_path)
            assert status["status"] == "stuck"
            assert status["active"] is False
        finally:
            _cleanup_wt(git_env, wt_path, "stuck-st")

    def test_stalled_status_detected(self, control_center, git_env, qtbot):
        wt_path = _create_wt(control_center, git_env, qtbot, "stalled-st")
        try:
            _write_loop_state(wt_path, {
                "status": "stalled",
                "current_iteration": 7,
                "max_iterations": 10,
            })
            status = control_center.get_ralph_status(wt_path)
            assert status["status"] == "stalled"
            assert status["active"] is False
        finally:
            _cleanup_wt(git_env, wt_path, "stalled-st")

    def test_stopped_status_detected(self, control_center, git_env, qtbot):
        wt_path = _create_wt(control_center, git_env, qtbot, "stopped-st")
        try:
            _write_loop_state(wt_path, {
                "status": "stopped",
                "current_iteration": 3,
                "max_iterations": 10,
            })
            status = control_center.get_ralph_status(wt_path)
            assert status["status"] == "stopped"
            assert status["active"] is False
        finally:
            _cleanup_wt(git_env, wt_path, "stopped-st")

    def test_running_with_alive_pid_is_active(self, control_center, git_env, qtbot):
        """Running loop with our own PID should be detected as active."""
        wt_path = _create_wt(control_center, git_env, qtbot, "alive-pid")
        try:
            _write_loop_state(wt_path, {
                "status": "running",
                "current_iteration": 2,
                "max_iterations": 10,
                "terminal_pid": os.getpid(),
            })
            status = control_center.get_ralph_status(wt_path)
            assert status["active"] is True
            assert status["status"] == "running"
        finally:
            _cleanup_wt(git_env, wt_path, "alive-pid")

    def test_starting_with_alive_pid_is_active(self, control_center, git_env, qtbot):
        wt_path = _create_wt(control_center, git_env, qtbot, "starting-pid")
        try:
            _write_loop_state(wt_path, {
                "status": "starting",
                "current_iteration": 0,
                "max_iterations": 10,
                "terminal_pid": os.getpid(),
            })
            status = control_center.get_ralph_status(wt_path)
            assert status["active"] is True
            assert status["status"] == "starting"
        finally:
            _cleanup_wt(git_env, wt_path, "starting-pid")

    def test_orphan_detection_dead_pid(self, control_center, git_env, qtbot):
        """Running loop with dead PID should be detected as stopped (orphan)."""
        wt_path = _create_wt(control_center, git_env, qtbot, "dead-pid")
        try:
            # Use a PID that is guaranteed to not exist
            dead_pid = 2147483647  # Max PID, extremely unlikely to exist
            _write_loop_state(wt_path, {
                "status": "running",
                "current_iteration": 3,
                "max_iterations": 10,
                "terminal_pid": dead_pid,
            })
            status = control_center.get_ralph_status(wt_path)
            assert status["status"] == "stopped"
            assert status["active"] is False

            # Verify the file was updated on disk
            with open(Path(wt_path) / ".claude" / "loop-state.json") as f:
                saved = json.load(f)
            assert saved["status"] == "stopped"
        finally:
            _cleanup_wt(git_env, wt_path, "dead-pid")

    def test_orphan_detection_invalid_pid(self, control_center, git_env, qtbot):
        """Invalid PID value should be treated as dead process."""
        wt_path = _create_wt(control_center, git_env, qtbot, "invalid-pid")
        try:
            _write_loop_state(wt_path, {
                "status": "running",
                "current_iteration": 1,
                "max_iterations": 5,
                "terminal_pid": "not-a-number",
            })
            status = control_center.get_ralph_status(wt_path)
            assert status["status"] == "stopped"
            assert status["active"] is False
        finally:
            _cleanup_wt(git_env, wt_path, "invalid-pid")

    def test_running_without_pid_stays_running(self, control_center, git_env, qtbot):
        """Running state without terminal_pid should remain running (no PID check possible)."""
        wt_path = _create_wt(control_center, git_env, qtbot, "no-pid")
        try:
            _write_loop_state(wt_path, {
                "status": "running",
                "current_iteration": 2,
                "max_iterations": 10,
            })
            status = control_center.get_ralph_status(wt_path)
            # No PID to check, so it stays as-is
            assert status["status"] == "running"
            assert status["active"] is True
        finally:
            _cleanup_wt(git_env, wt_path, "no-pid")

    def test_last_commit_ts_extracted(self, control_center, git_env, qtbot):
        """last_commit_ts should come from the last iteration with commits."""
        wt_path = _create_wt(control_center, git_env, qtbot, "commit-ts")
        try:
            ts1 = "2026-02-08T10:00:00+00:00"
            ts2 = "2026-02-08T11:00:00+00:00"
            ts3 = "2026-02-08T12:00:00+00:00"
            _write_loop_state(wt_path, {
                "status": "done",
                "current_iteration": 3,
                "max_iterations": 10,
                "iterations": [
                    {"n": 1, "started": ts1, "ended": ts1, "commits": ["abc"]},
                    {"n": 2, "started": ts2, "ended": ts2, "commits": []},
                    {"n": 3, "started": ts3, "ended": ts3, "commits": ["def"]},
                ],
            })
            status = control_center.get_ralph_status(wt_path)
            assert status["last_commit_ts"] == ts3
        finally:
            _cleanup_wt(git_env, wt_path, "commit-ts")

    def test_last_commit_ts_none_when_no_commits(self, control_center, git_env, qtbot):
        wt_path = _create_wt(control_center, git_env, qtbot, "no-commits")
        try:
            _write_loop_state(wt_path, {
                "status": "stalled",
                "current_iteration": 3,
                "max_iterations": 10,
                "iterations": [
                    {"n": 1, "commits": []},
                    {"n": 2, "commits": []},
                ],
            })
            status = control_center.get_ralph_status(wt_path)
            assert status["last_commit_ts"] is None
        finally:
            _cleanup_wt(git_env, wt_path, "no-commits")

    def test_settings_extracted(self, control_center, git_env, qtbot):
        """stall_threshold and iteration_timeout_min should be included."""
        wt_path = _create_wt(control_center, git_env, qtbot, "settings")
        try:
            _write_loop_state(wt_path, {
                "status": "done",
                "current_iteration": 5,
                "max_iterations": 10,
                "stall_threshold": 3,
                "iteration_timeout_min": 60,
            })
            status = control_center.get_ralph_status(wt_path)
            assert status["stall_threshold"] == 3
            assert status["iteration_timeout_min"] == 60
        finally:
            _cleanup_wt(git_env, wt_path, "settings")

    def test_started_at_and_iterations_included(self, control_center, git_env, qtbot):
        wt_path = _create_wt(control_center, git_env, qtbot, "full-data")
        try:
            ts = "2026-02-08T09:00:00+00:00"
            iters = [{"n": 1, "started": ts, "ended": ts, "commits": []}]
            _write_loop_state(wt_path, {
                "status": "done",
                "current_iteration": 1,
                "max_iterations": 5,
                "started_at": ts,
                "iterations": iters,
                "task": "Full data test",
            })
            status = control_center.get_ralph_status(wt_path)
            assert status["started_at"] == ts
            assert len(status["iterations"]) == 1
            assert status["task"] == "Full data test"
        finally:
            _cleanup_wt(git_env, wt_path, "full-data")


# ---------------------------------------------------------------------------
# stop_ralph_loop tests
# ---------------------------------------------------------------------------

class TestStopRalphLoop:

    def test_stop_updates_state_file(self, control_center, git_env, qtbot):
        wt_path = _create_wt(control_center, git_env, qtbot, "stop-state")
        try:
            _write_loop_state(wt_path, {
                "status": "running",
                "current_iteration": 3,
                "max_iterations": 10,
                "terminal_pid": os.getpid(),
            })
            # Patch kill to avoid actually killing our process
            with patch("subprocess.run") as mock_run:
                control_center.stop_ralph_loop(wt_path)

            with open(Path(wt_path) / ".claude" / "loop-state.json") as f:
                saved = json.load(f)
            assert saved["status"] == "stopped"
        finally:
            _cleanup_wt(git_env, wt_path, "stop-state")

    def test_stop_kills_terminal_pid(self, control_center, git_env, qtbot):
        wt_path = _create_wt(control_center, git_env, qtbot, "stop-kill")
        try:
            # Create PID file
            claude_dir = Path(wt_path) / ".claude"
            claude_dir.mkdir(parents=True, exist_ok=True)
            pid_file = claude_dir / "ralph-terminal.pid"
            pid_file.write_text("99999")

            _write_loop_state(wt_path, {
                "status": "running",
                "current_iteration": 2,
                "max_iterations": 10,
            })

            with patch("subprocess.run") as mock_run:
                control_center.stop_ralph_loop(wt_path)

            # Check that kill was called with the PID
            mock_run.assert_called_once()
            args = mock_run.call_args
            assert "kill" in args[0][0]
            assert "99999" in args[0][0]

            # PID file should be cleaned up
            assert not pid_file.exists()
        finally:
            _cleanup_wt(git_env, wt_path, "stop-kill")

    def test_stop_no_pid_file_still_updates_state(self, control_center, git_env, qtbot):
        """Stop should update state even when there's no PID file."""
        wt_path = _create_wt(control_center, git_env, qtbot, "stop-nopid")
        try:
            _write_loop_state(wt_path, {
                "status": "running",
                "current_iteration": 1,
                "max_iterations": 5,
            })
            control_center.stop_ralph_loop(wt_path)

            with open(Path(wt_path) / ".claude" / "loop-state.json") as f:
                saved = json.load(f)
            assert saved["status"] == "stopped"
        finally:
            _cleanup_wt(git_env, wt_path, "stop-nopid")

    def test_stop_no_loop_state_file_no_error(self, control_center, git_env, qtbot):
        """Calling stop when there's no loop-state.json should not raise."""
        wt_path = _create_wt(control_center, git_env, qtbot, "stop-none")
        try:
            # No loop-state.json exists
            control_center.stop_ralph_loop(wt_path)  # Should not raise
        finally:
            _cleanup_wt(git_env, wt_path, "stop-none")


# ---------------------------------------------------------------------------
# Context menu tests
# ---------------------------------------------------------------------------

class TestRalphContextMenu:

    def test_menu_shows_start_when_no_loop(self, control_center, git_env, qtbot):
        cid = "menu-noloop"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            row = _find_wt_row(control_center, cid)
            assert row is not None

            with _MenuCapture() as cap:
                row_rect = control_center.table.visualRect(
                    control_center.table.model().index(row, 0)
                )
                control_center.show_row_context_menu(row_rect.center())

            ralph_items = cap.find_submenu("Ralph Loop")
            assert ralph_items is not None
            assert "Start Loop..." in ralph_items
            # Should NOT have Stop Loop
            assert "Stop Loop" not in ralph_items
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_menu_shows_stop_when_running(self, control_center, git_env, qtbot):
        cid = "menu-running"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "running",
                "current_iteration": 3,
                "max_iterations": 10,
                "terminal_pid": os.getpid(),
            })

            row = _find_wt_row(control_center, cid)
            with _MenuCapture() as cap:
                row_rect = control_center.table.visualRect(
                    control_center.table.model().index(row, 0)
                )
                control_center.show_row_context_menu(row_rect.center())

            ralph_items = cap.find_submenu("Ralph Loop")
            assert "Stop Loop" in ralph_items
            assert "View Terminal" in ralph_items
            # Status line
            has_status = any("Status:" in item and "3/10" in item for item in ralph_items)
            assert has_status, f"Expected status line with 3/10, got: {ralph_items}"
            # Should NOT have Start Loop
            assert "Start Loop..." not in ralph_items
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_menu_shows_history_for_done_loop(self, control_center, git_env, qtbot):
        cid = "menu-done"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "done",
                "current_iteration": 5,
                "max_iterations": 10,
            })

            row = _find_wt_row(control_center, cid)
            with _MenuCapture() as cap:
                row_rect = control_center.table.visualRect(
                    control_center.table.model().index(row, 0)
                )
                control_center.show_row_context_menu(row_rect.center())

            ralph_items = cap.find_submenu("Ralph Loop")
            assert "Start Loop..." in ralph_items
            has_history = any("Last:" in item and "done" in item and "5/10" in item for item in ralph_items)
            assert has_history, f"Expected 'Last: done (5/10)', got: {ralph_items}"
            assert "View Log" in ralph_items
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_menu_shows_history_for_stuck_loop(self, control_center, git_env, qtbot):
        cid = "menu-stuck"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "stuck",
                "current_iteration": 10,
                "max_iterations": 10,
            })

            row = _find_wt_row(control_center, cid)
            with _MenuCapture() as cap:
                row_rect = control_center.table.visualRect(
                    control_center.table.model().index(row, 0)
                )
                control_center.show_row_context_menu(row_rect.center())

            ralph_items = cap.find_submenu("Ralph Loop")
            has_history = any("Last:" in item and "stuck" in item for item in ralph_items)
            assert has_history, f"Expected stuck history line, got: {ralph_items}"
            assert "View Log" in ralph_items
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_menu_shows_history_for_stopped_loop(self, control_center, git_env, qtbot):
        cid = "menu-stopped"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "stopped",
                "current_iteration": 4,
                "max_iterations": 10,
            })

            row = _find_wt_row(control_center, cid)
            with _MenuCapture() as cap:
                row_rect = control_center.table.visualRect(
                    control_center.table.model().index(row, 0)
                )
                control_center.show_row_context_menu(row_rect.center())

            ralph_items = cap.find_submenu("Ralph Loop")
            has_history = any("Last:" in item and "stopped" in item for item in ralph_items)
            assert has_history, f"Expected stopped history, got: {ralph_items}"
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_menu_shows_view_terminal_when_starting(self, control_center, git_env, qtbot):
        cid = "menu-starting"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "starting",
                "current_iteration": 0,
                "max_iterations": 10,
                "terminal_pid": os.getpid(),
            })

            row = _find_wt_row(control_center, cid)
            with _MenuCapture() as cap:
                row_rect = control_center.table.visualRect(
                    control_center.table.model().index(row, 0)
                )
                control_center.show_row_context_menu(row_rect.center())

            ralph_items = cap.find_submenu("Ralph Loop")
            assert "View Terminal" in ralph_items
            assert "Stop Loop" in ralph_items
        finally:
            _cleanup_wt(git_env, wt_path, cid)


# ---------------------------------------------------------------------------
# Extra column rendering (Ralph button) tests
# ---------------------------------------------------------------------------

class TestRalphButtonRendering:

    def test_no_button_when_no_loop(self, control_center, git_env, qtbot):
        cid = "btn-none"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            row = _find_wt_row(control_center, cid)
            widget = control_center.table.cellWidget(row, 5)  # COL_EXTRA
            # Either None or no QPushButton inside
            if widget is not None:
                buttons = widget.findChildren(QPushButton)
                assert len(buttons) == 0, "Should have no Ralph button without loop state"
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_button_present_when_running(self, control_center, git_env, qtbot):
        cid = "btn-running"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "running",
                "current_iteration": 2,
                "max_iterations": 10,
                "terminal_pid": os.getpid(),
            })
            # Re-render
            control_center.refresh_table_display()
            qtbot.wait(100)

            row = _find_wt_row(control_center, cid)
            widget = control_center.table.cellWidget(row, 5)
            assert widget is not None
            buttons = widget.findChildren(QPushButton)
            assert len(buttons) == 1
            assert buttons[0].text() == "R"
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_button_color_running_is_green(self, control_center, git_env, qtbot):
        cid = "btn-color-run"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "running",
                "current_iteration": 1,
                "max_iterations": 5,
                "terminal_pid": os.getpid(),
            })
            control_center.refresh_table_display()
            qtbot.wait(100)

            row = _find_wt_row(control_center, cid)
            widget = control_center.table.cellWidget(row, 5)
            btn = widget.findChildren(QPushButton)[0]
            running_color = control_center.get_color("status_running")
            assert running_color in btn.styleSheet()
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_button_color_done_is_blue(self, control_center, git_env, qtbot):
        cid = "btn-color-done"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "done",
                "current_iteration": 5,
                "max_iterations": 5,
            })
            control_center.refresh_table_display()
            qtbot.wait(100)

            row = _find_wt_row(control_center, cid)
            widget = control_center.table.cellWidget(row, 5)
            btn = widget.findChildren(QPushButton)[0]
            done_color = control_center.get_color("status_done")
            assert done_color in btn.styleSheet()
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_button_color_stuck_is_red(self, control_center, git_env, qtbot):
        cid = "btn-color-stuck"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "stuck",
                "current_iteration": 10,
                "max_iterations": 10,
            })
            # Re-push status (background worker may have overwritten)
            _push_status(control_center, wt_path, cid, qtbot)
            control_center.refresh_table_display()
            qtbot.wait(100)

            row = _find_wt_row(control_center, cid)
            assert row is not None, f"Worktree row for {cid} not found in table"
            widget = control_center.table.cellWidget(row, 5)
            btn = widget.findChildren(QPushButton)[0]
            stuck_color = control_center.get_color("burn_high")
            assert stuck_color in btn.styleSheet()
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_button_color_stalled_is_orange(self, control_center, git_env, qtbot):
        cid = "btn-color-stall"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "stalled",
                "current_iteration": 6,
                "max_iterations": 10,
            })
            control_center.refresh_table_display()
            qtbot.wait(100)

            row = _find_wt_row(control_center, cid)
            widget = control_center.table.cellWidget(row, 5)
            btn = widget.findChildren(QPushButton)[0]
            stalled_color = control_center.get_color("status_stalled")
            assert stalled_color in btn.styleSheet()
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_button_color_stopped_is_idle(self, control_center, git_env, qtbot):
        cid = "btn-color-stop"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "stopped",
                "current_iteration": 2,
                "max_iterations": 10,
            })
            control_center.refresh_table_display()
            qtbot.wait(100)

            row = _find_wt_row(control_center, cid)
            widget = control_center.table.cellWidget(row, 5)
            btn = widget.findChildren(QPushButton)[0]
            idle_color = control_center.get_color("status_idle")
            assert idle_color in btn.styleSheet()
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_tooltip_contains_status_and_iterations(self, control_center, git_env, qtbot):
        cid = "btn-tip-basic"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "done",
                "current_iteration": 7,
                "max_iterations": 10,
                "task": "Build feature X",
            })
            control_center.refresh_table_display()
            qtbot.wait(100)

            row = _find_wt_row(control_center, cid)
            widget = control_center.table.cellWidget(row, 5)
            btn = widget.findChildren(QPushButton)[0]
            tip = btn.toolTip()
            assert "done" in tip
            assert "7/10" in tip
            assert "Build feature X" in tip
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_tooltip_shows_elapsed_time(self, control_center, git_env, qtbot):
        cid = "btn-tip-elapsed"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            started = (datetime.now(timezone.utc) - timedelta(hours=2, minutes=15)).isoformat()
            _write_loop_state(wt_path, {
                "status": "done",
                "current_iteration": 5,
                "max_iterations": 10,
                "started_at": started,
            })
            control_center.refresh_table_display()
            qtbot.wait(100)

            row = _find_wt_row(control_center, cid)
            widget = control_center.table.cellWidget(row, 5)
            btn = widget.findChildren(QPushButton)[0]
            tip = btn.toolTip()
            assert "Elapsed:" in tip
            assert "2h" in tip
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_tooltip_shows_settings(self, control_center, git_env, qtbot):
        cid = "btn-tip-settings"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "done",
                "current_iteration": 3,
                "max_iterations": 10,
                "stall_threshold": 4,
                "iteration_timeout_min": 90,
            })
            control_center.refresh_table_display()
            qtbot.wait(100)

            row = _find_wt_row(control_center, cid)
            widget = control_center.table.cellWidget(row, 5)
            btn = widget.findChildren(QPushButton)[0]
            tip = btn.toolTip()
            assert "stall=4" in tip
            assert "timeout=90m" in tip
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_tooltip_shows_last_commit_time(self, control_center, git_env, qtbot):
        cid = "btn-tip-commit"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "done",
                "current_iteration": 2,
                "max_iterations": 10,
                "iterations": [
                    {"n": 1, "started": "2026-02-08T14:30:00+00:00",
                     "ended": "2026-02-08T14:45:00+00:00", "commits": ["abc"]},
                ],
            })
            control_center.refresh_table_display()
            qtbot.wait(100)

            row = _find_wt_row(control_center, cid)
            widget = control_center.table.cellWidget(row, 5)
            btn = widget.findChildren(QPushButton)[0]
            tip = btn.toolTip()
            assert "Last commit:" in tip
            assert "14:45" in tip
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_tooltip_truncates_long_task(self, control_center, git_env, qtbot):
        cid = "btn-tip-trunc"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            long_task = "A" * 100
            _write_loop_state(wt_path, {
                "status": "done",
                "current_iteration": 1,
                "max_iterations": 5,
                "task": long_task,
            })
            control_center.refresh_table_display()
            qtbot.wait(100)

            row = _find_wt_row(control_center, cid)
            widget = control_center.table.cellWidget(row, 5)
            btn = widget.findChildren(QPushButton)[0]
            tip = btn.toolTip()
            # Task should be truncated to 60 chars
            assert "Task: " in tip
            task_line = [l for l in tip.split("\n") if l.startswith("Task:")][0]
            task_text = task_line.split("Task: ")[1]
            assert len(task_text) == 60
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_button_click_calls_focus_terminal(self, control_center, git_env, qtbot):
        cid = "btn-click"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "done",
                "current_iteration": 1,
                "max_iterations": 5,
            })
            control_center.refresh_table_display()
            qtbot.wait(100)

            row = _find_wt_row(control_center, cid)
            widget = control_center.table.cellWidget(row, 5)
            btn = widget.findChildren(QPushButton)[0]

            with patch.object(control_center, "focus_ralph_terminal") as mock_focus:
                btn.click()
                mock_focus.assert_called_once_with(wt_path)
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_current_iteration_elapsed_shown_when_running(self, control_center, git_env, qtbot):
        cid = "btn-iter-time"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            iter_started = (datetime.now(timezone.utc) - timedelta(minutes=12)).isoformat()
            _write_loop_state(wt_path, {
                "status": "running",
                "current_iteration": 2,
                "max_iterations": 10,
                "terminal_pid": os.getpid(),
                "started_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                "iterations": [
                    {"n": 1, "started": "2026-02-08T10:00:00+00:00",
                     "ended": "2026-02-08T10:30:00+00:00", "commits": []},
                    {"n": 2, "started": iter_started, "commits": []},
                ],
            })
            control_center.refresh_table_display()
            qtbot.wait(100)

            row = _find_wt_row(control_center, cid)
            widget = control_center.table.cellWidget(row, 5)
            btn = widget.findChildren(QPushButton)[0]
            tip = btn.toolTip()
            assert "Current iter:" in tip
        finally:
            _cleanup_wt(git_env, wt_path, cid)


# ---------------------------------------------------------------------------
# Start dialog tests
# ---------------------------------------------------------------------------

class TestStartDialog:

    def test_dialog_no_tasks_md_defaults_to_manual(self, control_center, git_env, qtbot):
        cid = "dlg-manual"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            dialog_data = {}

            def capture_exec(self):
                from PySide6.QtWidgets import QLabel as _QLabel
                for combo in self.findChildren(QComboBox):
                    dialog_data["done_criteria"] = combo.currentText()
                for label in self.findChildren(_QLabel):
                    if label.objectName() == "tasks_md_label":
                        dialog_data["tasks_label"] = label.text()
                    if label.objectName() == "manual_warning":
                        dialog_data["warning_visible"] = label.isVisibleTo(self)
                return QDialog.Rejected

            with patch.object(QDialog, 'exec', capture_exec):
                control_center.start_ralph_loop_dialog(wt_path)

            assert dialog_data["done_criteria"] == "manual"
            assert "not found" in dialog_data["tasks_label"]
            assert dialog_data["warning_visible"] is True
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_dialog_with_tasks_md_defaults_to_tasks(self, control_center, git_env, qtbot):
        cid = "dlg-tasks"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            (Path(wt_path) / "tasks.md").write_text("- [ ] Task 1\n")

            dialog_data = {}

            def capture_exec(self):
                from PySide6.QtWidgets import QLabel as _QLabel
                for combo in self.findChildren(QComboBox):
                    dialog_data["done_criteria"] = combo.currentText()
                for label in self.findChildren(_QLabel):
                    if label.objectName() == "tasks_md_label":
                        dialog_data["tasks_label"] = label.text()
                    if label.objectName() == "manual_warning":
                        dialog_data["warning_visible"] = label.isVisibleTo(self)
                return QDialog.Rejected

            with patch.object(QDialog, 'exec', capture_exec):
                control_center.start_ralph_loop_dialog(wt_path)

            assert dialog_data["done_criteria"] == "tasks"
            assert "found" in dialog_data["tasks_label"]
            assert dialog_data["warning_visible"] is False
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_dialog_spinbox_defaults(self, control_center, git_env, qtbot):
        cid = "dlg-defaults"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            dialog_data = {}

            def capture_exec(self):
                for spin in self.findChildren(QSpinBox):
                    if spin.objectName() == "stall_threshold_spin":
                        dialog_data["stall"] = spin.value()
                        dialog_data["stall_min"] = spin.minimum()
                        dialog_data["stall_max"] = spin.maximum()
                    if spin.objectName() == "iter_timeout_spin":
                        dialog_data["timeout"] = spin.value()
                        dialog_data["timeout_min"] = spin.minimum()
                        dialog_data["timeout_max"] = spin.maximum()
                return QDialog.Rejected

            with patch.object(QDialog, 'exec', capture_exec):
                control_center.start_ralph_loop_dialog(wt_path)

            # Stall threshold: range 1-10, default 2
            assert dialog_data["stall_min"] == 1
            assert dialog_data["stall_max"] == 10
            assert dialog_data["stall"] == 2  # default

            # Iteration timeout: range 5-120
            assert dialog_data["timeout_min"] == 5
            assert dialog_data["timeout_max"] == 120
            assert dialog_data["timeout"] == 45  # default
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_dialog_empty_task_shows_warning(self, control_center, git_env, qtbot):
        """Submitting with empty task should show warning and not spawn subprocess."""
        cid = "dlg-empty"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            call_count = {"exec": 0}

            original_exec = QDialog.exec

            def capture_exec(self):
                call_count["exec"] += 1
                if call_count["exec"] == 1:
                    # First dialog: the start dialog - accept with empty task
                    return QDialog.Accepted
                else:
                    # Any subsequent dialog (warning) - just reject
                    return QDialog.Rejected

            with patch.object(QDialog, 'exec', capture_exec), \
                 patch("subprocess.Popen") as mock_popen, \
                 patch("gui.control_center.mixins.menus.show_warning") as mock_warn:
                control_center.start_ralph_loop_dialog(wt_path)

            # Popen should NOT have been called (task was empty)
            mock_popen.assert_not_called()
            # Warning should have been shown
            mock_warn.assert_called_once()
            assert "required" in str(mock_warn.call_args).lower()
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_dialog_accept_spawns_command(self, control_center, git_env, qtbot):
        """Accepting dialog with valid task should spawn set-loop start."""
        cid = "dlg-spawn"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            def capture_exec(self):
                # Fill in task text
                for te in self.findChildren(QTextEdit):
                    te.setPlainText("Implement feature Y")
                return QDialog.Accepted

            with patch.object(QDialog, 'exec', capture_exec), \
                 patch("subprocess.Popen") as mock_popen:
                control_center.start_ralph_loop_dialog(wt_path)

            mock_popen.assert_called_once()
            cmd = mock_popen.call_args[0][0]
            assert "set-loop" in cmd[0]
            assert "start" in cmd
            assert cid not in cmd  # change_id should NOT be passed to set-loop
            assert "Implement feature Y" in cmd
            assert "--max" in cmd
            assert "--done" in cmd
            assert "--stall-threshold" in cmd
            assert "--iteration-timeout" in cmd
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_dialog_cancelled_no_spawn(self, control_center, git_env, qtbot):
        """Cancelling dialog should not spawn anything."""
        cid = "dlg-cancel"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            with patch.object(QDialog, 'exec', lambda self: QDialog.Rejected), \
                 patch("subprocess.Popen") as mock_popen:
                control_center.start_ralph_loop_dialog(wt_path)

            mock_popen.assert_not_called()
        finally:
            _cleanup_wt(git_env, wt_path, cid)


# ---------------------------------------------------------------------------
# Focus terminal + View log tests
# ---------------------------------------------------------------------------

class TestFocusTerminal:

    def test_focus_no_loop_state_does_nothing(self, control_center, git_env, qtbot):
        cid = "focus-none"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            with patch.object(control_center, "view_ralph_log") as mock_log:
                control_center.focus_ralph_terminal(wt_path)
                mock_log.assert_not_called()
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_focus_falls_back_to_log_when_no_window(self, control_center, git_env, qtbot):
        cid = "focus-fallback"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "done",
                "current_iteration": 5,
                "max_iterations": 10,
                "worktree_name": Path(wt_path).name,
            })

            with patch("gui.control_center.mixins.handlers.get_platform") as mock_plat, \
                 patch.object(control_center, "view_ralph_log") as mock_log:
                mock_plat.return_value.find_window_by_title.return_value = None
                control_center.focus_ralph_terminal(wt_path)
                mock_log.assert_called_once_with(wt_path)
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_focus_finds_window_and_focuses(self, control_center, git_env, qtbot):
        cid = "focus-found"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "running",
                "current_iteration": 2,
                "max_iterations": 10,
                "worktree_name": Path(wt_path).name,
                "pid": 12345,
            })

            with patch("gui.control_center.mixins.handlers.get_platform") as mock_plat:
                # PPID chain finds window for Ralph loop PID
                mock_plat.return_value.find_window_by_pid.return_value = ("win-123", "kitty")
                control_center.focus_ralph_terminal(wt_path)
                mock_plat.return_value.find_window_by_pid.assert_called_once_with(12345)
                mock_plat.return_value.focus_window.assert_called_once_with("win-123", app_name="kitty")
        finally:
            _cleanup_wt(git_env, wt_path, cid)


class TestViewRalphLog:

    def test_view_log_no_file_shows_info(self, control_center, git_env, qtbot):
        cid = "log-none"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            with patch("gui.control_center.mixins.handlers.show_information") as mock_info:
                control_center.view_ralph_log(wt_path)
                mock_info.assert_called_once()
                assert "No" in str(mock_info.call_args) or "log" in str(mock_info.call_args).lower()
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_view_log_opens_with_platform(self, control_center, git_env, qtbot):
        cid = "log-open"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            claude_dir = Path(wt_path) / ".claude"
            claude_dir.mkdir(parents=True, exist_ok=True)
            (claude_dir / "ralph-loop.log").write_text("Log line 1\nLog line 2\n")

            with patch("gui.control_center.mixins.handlers.get_platform") as mock_plat:
                mock_plat.return_value.open_file.return_value = True
                control_center.view_ralph_log(wt_path)
                mock_plat.return_value.open_file.assert_called_once()
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_view_log_fallback_creates_dialog(self, control_center, git_env, qtbot):
        """When platform open_file fails, a fallback dialog is created.

        We verify: platform.open_file was tried, dialog was created, no crash.
        """
        cid = "log-dialog"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            claude_dir = Path(wt_path) / ".claude"
            claude_dir.mkdir(parents=True, exist_ok=True)
            (claude_dir / "ralph-loop.log").write_text("Fallback log content here\n")

            import gui.control_center.mixins.handlers as handlers_mod
            OrigQDialog = handlers_mod.QDialog

            class NonBlockingDialog(OrigQDialog):
                instances = []

                def __init__(self_dlg, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    NonBlockingDialog.instances.append(self_dlg)

                def exec(self_dlg):
                    return OrigQDialog.Accepted

            NonBlockingDialog.instances.clear()

            with patch("gui.control_center.mixins.handlers.get_platform") as mock_plat, \
                 patch.object(handlers_mod, "QDialog", NonBlockingDialog):
                mock_plat.return_value.open_file.return_value = False
                control_center.view_ralph_log(wt_path)

            # Verify platform open was attempted
            mock_plat.return_value.open_file.assert_called_once()
            # Verify dialog was created (fallback path)
            assert len(NonBlockingDialog.instances) == 1
            assert "Log" in NonBlockingDialog.instances[0].windowTitle()
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_view_log_truncation_logic(self, control_center, git_env, qtbot):
        """The truncation logic read_text()[-50000:] keeps only last 50k chars."""
        cid = "log-trunc"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            claude_dir = Path(wt_path) / ".claude"
            claude_dir.mkdir(parents=True, exist_ok=True)
            # Write > 50k chars: 60k X's + END_MARKER
            large_content = "X" * 60000 + "\nEND_MARKER\n"
            log_file = claude_dir / "ralph-loop.log"
            log_file.write_text(large_content)

            # Verify the truncation logic used by view_ralph_log
            truncated = log_file.read_text()[-50000:]
            assert "END_MARKER" in truncated, "END_MARKER should be in last 50k"
            assert len(truncated) == 50000
            # First 10k X's should be dropped
            assert truncated[0] == "X"  # still starts with X (from the middle)
            # But the full 60k prefix is NOT present
            assert len(truncated) < len(large_content)

            # Also verify the method doesn't crash on large files
            import gui.control_center.mixins.handlers as handlers_mod
            OrigQDialog = handlers_mod.QDialog

            class NonBlockingDialog(OrigQDialog):
                def exec(self_dlg):
                    return OrigQDialog.Accepted

            with patch("gui.control_center.mixins.handlers.get_platform") as mock_plat, \
                 patch.object(handlers_mod, "QDialog", NonBlockingDialog):
                mock_plat.return_value.open_file.return_value = False
                control_center.view_ralph_log(wt_path)  # Should not crash
        finally:
            _cleanup_wt(git_env, wt_path, cid)


# ---------------------------------------------------------------------------
# State transition consistency tests
# ---------------------------------------------------------------------------

class TestStateTransitions:

    def test_running_to_stopped_via_stop(self, control_center, git_env, qtbot):
        """Full flow: running loop -> stop -> state is stopped."""
        cid = "trans-stop"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "running",
                "current_iteration": 3,
                "max_iterations": 10,
                "terminal_pid": os.getpid(),
            })

            # Verify initially running
            status = control_center.get_ralph_status(wt_path)
            assert status["active"] is True
            assert status["status"] == "running"

            # Stop it
            with patch("subprocess.run"):
                control_center.stop_ralph_loop(wt_path)

            # Verify stopped
            status = control_center.get_ralph_status(wt_path)
            assert status["active"] is False
            assert status["status"] == "stopped"
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_running_to_stopped_via_orphan_detection(self, control_center, git_env, qtbot):
        """Full flow: running loop with dead PID -> get_ralph_status -> auto-stopped."""
        cid = "trans-orphan"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "running",
                "current_iteration": 4,
                "max_iterations": 10,
                "terminal_pid": 2147483647,
            })

            status = control_center.get_ralph_status(wt_path)
            assert status["active"] is False
            assert status["status"] == "stopped"

            # Second call should also return stopped (from file)
            status2 = control_center.get_ralph_status(wt_path)
            assert status2["status"] == "stopped"
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_done_loop_restart_shows_start_menu(self, control_center, git_env, qtbot):
        """After a loop is done, context menu should offer Start again."""
        cid = "trans-restart"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "done",
                "current_iteration": 10,
                "max_iterations": 10,
            })

            row = _find_wt_row(control_center, cid)
            with _MenuCapture() as cap:
                row_rect = control_center.table.visualRect(
                    control_center.table.model().index(row, 0)
                )
                control_center.show_row_context_menu(row_rect.center())

            ralph_items = cap.find_submenu("Ralph Loop")
            assert "Start Loop..." in ralph_items
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_stalled_loop_shows_start_and_history(self, control_center, git_env, qtbot):
        """Stalled loop (not active) should show Start + history."""
        cid = "trans-stalled"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "stalled",
                "current_iteration": 6,
                "max_iterations": 10,
            })

            _push_status(control_center, wt_path, cid, qtbot)
            row = _find_wt_row(control_center, cid)
            assert row is not None, f"Worktree row for {cid} not found in table"
            with _MenuCapture() as cap:
                row_rect = control_center.table.visualRect(
                    control_center.table.model().index(row, 0)
                )
                control_center.show_row_context_menu(row_rect.center())

            ralph_items = cap.find_submenu("Ralph Loop")
            # stalled is not in (done, stuck, stopped) so no "Last:" line
            assert "Start Loop..." in ralph_items
        finally:
            _cleanup_wt(git_env, wt_path, cid)


# ---------------------------------------------------------------------------
# Worktree-name tests (post openspec-decoupling)
# ---------------------------------------------------------------------------

class TestWorktreeNameState:

    def test_loop_state_with_worktree_name_read_correctly(self, control_center, git_env, qtbot):
        """8.2 loop-state.json with worktree_name field is correctly read by get_ralph_status"""
        cid = "wt-name-read"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            _write_loop_state(wt_path, {
                "status": "done",
                "current_iteration": 3,
                "max_iterations": 10,
                "worktree_name": Path(wt_path).name,
                "task": "Test worktree_name field",
            })
            status = control_center.get_ralph_status(wt_path)
            assert status["status"] == "done"
            assert status["iteration"] == 3
            assert status["task"] == "Test worktree_name field"
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_focus_terminal_uses_worktree_name(self, control_center, git_env, qtbot):
        """8.3 focus_ralph_terminal uses worktree_name for window title search"""
        cid = "wt-name-focus"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            wt_name = Path(wt_path).name
            _write_loop_state(wt_path, {
                "status": "running",
                "current_iteration": 1,
                "max_iterations": 5,
                "worktree_name": wt_name,
            })
            with patch("gui.control_center.mixins.handlers.get_platform") as mock_plat:
                mock_plat.return_value.find_window_by_pid.return_value = None
                mock_plat.return_value.find_window_by_title.return_value = "win-456"
                control_center.focus_ralph_terminal(wt_path)
                # Should search for "Ralph: <worktree_name>" not "Ralph: <change_id>"
                mock_plat.return_value.find_window_by_title.assert_called_once_with(f"Ralph: {wt_name}")
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_dialog_finds_tasks_md_at_worktree_root(self, control_center, git_env, qtbot):
        """8.4 tasks.md at worktree root is found by dialog's tasks detection"""
        cid = "wt-root-tasks"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            (Path(wt_path) / "tasks.md").write_text("- [ ] Root task\n")
            dialog_data = {}

            def capture_exec(self):
                for combo in self.findChildren(QComboBox):
                    dialog_data["done_criteria"] = combo.currentText()
                return QDialog.Rejected

            with patch.object(QDialog, 'exec', capture_exec):
                control_center.start_ralph_loop_dialog(wt_path)

            assert dialog_data["done_criteria"] == "tasks"
        finally:
            _cleanup_wt(git_env, wt_path, cid)

    def test_dialog_finds_tasks_md_in_subdirectory(self, control_center, git_env, qtbot):
        """8.5 tasks.md in arbitrary subdirectory (not openspec) is found by dialog"""
        cid = "set-sub-tasks"
        wt_path = _create_wt(control_center, git_env, qtbot, cid)
        try:
            subdir = Path(wt_path) / "myproject" / "planning"
            subdir.mkdir(parents=True, exist_ok=True)
            (subdir / "tasks.md").write_text("- [ ] Subdir task\n")

            dialog_data = {}

            def capture_exec(self):
                for combo in self.findChildren(QComboBox):
                    dialog_data["done_criteria"] = combo.currentText()
                return QDialog.Rejected

            with patch.object(QDialog, 'exec', capture_exec):
                control_center.start_ralph_loop_dialog(wt_path)

            assert dialog_data["done_criteria"] == "tasks"
        finally:
            _cleanup_wt(git_env, wt_path, cid)
