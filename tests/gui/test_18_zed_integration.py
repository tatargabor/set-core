"""
Zed Integration Tests - Verify on_focus, on_double_click, and on_close_editor
use platform abstraction correctly with mocked responses.
"""

import subprocess
from unittest.mock import patch, MagicMock


def test_on_focus_uses_platform_abstraction(control_center, git_env, qtbot):
    """on_focus() should call platform.find_window_by_title and platform.focus_window."""
    project_path = str(git_env["project"])
    wt_path = str(git_env["base"] / "test-project-set-zed-focus")

    subprocess.run(
        ["git", "-C", project_path, "worktree", "add", "-b", "change/zed-focus", wt_path],
        capture_output=True, check=True,
    )

    try:
        status_data = {
            "worktrees": [{
                "project": "test-project",
                "change_id": "zed-focus",
                "path": wt_path,
                "branch": "change/zed-focus",
                "editor_open": True,
                "agents": [{"pid": 77001, "status": "running", "skill": None}],
                "git": {"last_commit": 0, "uncommitted_changes": False},
            }],
            "summary": {"total": 1, "running": 1, "compacting": 0, "waiting": 0, "idle": 0},
        }
        control_center.update_status(status_data)
        qtbot.wait(200)

        wt_row = None
        for row, wt in control_center.row_to_worktree.items():
            if wt.get("change_id") == "zed-focus":
                wt_row = row
                break
        assert wt_row is not None
        control_center.table.setCurrentCell(wt_row, 0)

        mock_platform = MagicMock()
        mock_platform.find_window_by_title.return_value = "mock-window-id"
        mock_platform.focus_window.return_value = True

        with patch("gui.control_center.mixins.handlers.get_platform", return_value=mock_platform):
            control_center.on_focus()

        mock_platform.find_window_by_title.assert_called_once()
        mock_platform.focus_window.assert_called_once()

    finally:
        subprocess.run(
            ["git", "-C", project_path, "worktree", "remove", "--force", wt_path],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", project_path, "branch", "-D", "change/zed-focus"],
            capture_output=True,
        )


def test_on_double_click_uses_platform(control_center, git_env, qtbot):
    """on_double_click() should use platform abstraction for window detection."""
    project_path = str(git_env["project"])
    wt_path = str(git_env["base"] / "test-project-set-zed-dblclk")

    subprocess.run(
        ["git", "-C", project_path, "worktree", "add", "-b", "change/zed-dblclk", wt_path],
        capture_output=True, check=True,
    )

    try:
        status_data = {
            "worktrees": [{
                "project": "test-project",
                "change_id": "zed-dblclk",
                "path": wt_path,
                "branch": "change/zed-dblclk",
                "editor_open": True,
                "agents": [],
                "git": {"last_commit": 0, "uncommitted_changes": False},
            }],
            "summary": {"total": 1, "running": 0, "compacting": 0, "waiting": 0, "idle": 1},
        }
        control_center.update_status(status_data)
        qtbot.wait(200)

        wt_row = None
        for row, wt in control_center.row_to_worktree.items():
            if wt.get("change_id") == "zed-dblclk":
                wt_row = row
                break
        assert wt_row is not None
        control_center.table.setCurrentCell(wt_row, 0)

        mock_platform = MagicMock()
        mock_platform.find_window_by_title.return_value = None  # No window

        with patch("gui.control_center.mixins.handlers.get_platform", return_value=mock_platform), \
             patch("gui.control_center.mixins.handlers.subprocess") as mock_sub:
            control_center.on_double_click()

        # Should try to find window via platform
        mock_platform.find_window_by_title.assert_called_once()
        # Should fall back to set-work
        mock_sub.Popen.assert_called_once()

    finally:
        subprocess.run(
            ["git", "-C", project_path, "worktree", "remove", "--force", wt_path],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", project_path, "branch", "-D", "change/zed-dblclk"],
            capture_output=True,
        )


def test_on_close_editor_uses_platform(control_center, git_env, qtbot):
    """on_close_editor() should call platform.close_window with correct window ID."""
    project_path = str(git_env["project"])
    wt_path = str(git_env["base"] / "test-project-set-zed-close")

    subprocess.run(
        ["git", "-C", project_path, "worktree", "add", "-b", "change/zed-close", wt_path],
        capture_output=True, check=True,
    )

    try:
        status_data = {
            "worktrees": [{
                "project": "test-project",
                "change_id": "zed-close",
                "path": wt_path,
                "branch": "change/zed-close",
                "editor_open": True,
                "agents": [],
                "git": {"last_commit": 0, "uncommitted_changes": False},
            }],
            "summary": {"total": 1, "running": 0, "compacting": 0, "waiting": 0, "idle": 1},
        }
        control_center.update_status(status_data)
        qtbot.wait(200)

        wt_row = None
        for row, wt in control_center.row_to_worktree.items():
            if wt.get("change_id") == "zed-close":
                wt_row = row
                break
        assert wt_row is not None
        control_center.table.setCurrentCell(wt_row, 0)

        mock_platform = MagicMock()
        mock_platform.find_window_by_title.return_value = "window-123"
        mock_platform.close_window.return_value = True

        with patch("gui.control_center.mixins.handlers.get_platform", return_value=mock_platform):
            control_center.on_close_editor()

        mock_platform.find_window_by_title.assert_called_once()
        mock_platform.close_window.assert_called_once()
        close_args = mock_platform.close_window.call_args
        assert close_args[0][0] == "window-123"

    finally:
        subprocess.run(
            ["git", "-C", project_path, "worktree", "remove", "--force", wt_path],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", project_path, "branch", "-D", "change/zed-close"],
            capture_output=True,
        )
