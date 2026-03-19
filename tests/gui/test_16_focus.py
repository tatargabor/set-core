"""
Focus Tests - Verify on_focus and on_double_click use platform layer for window detection
"""

import subprocess
from unittest.mock import patch, MagicMock

from PySide6.QtWidgets import QMessageBox


def test_on_focus_uses_platform_layer(control_center, git_env, qtbot):
    """on_focus() should use platform.find_window_by_title + focus_window, not subprocess."""
    project_path = str(git_env["project"])
    wt_path = str(git_env["base"] / "test-project-set-focus-test")

    subprocess.run(
        ["git", "-C", project_path, "worktree", "add", "-b", "change/focus-test", wt_path],
        capture_output=True, check=True,
    )

    try:
        status_data = {
            "worktrees": [{
                "project": "test-project",
                "change_id": "focus-test",
                "path": wt_path,
                "branch": "change/focus-test",
                "agents": [{"pid": 99999, "status": "running", "skill": None}],
                "git": {"last_commit": 0, "uncommitted_changes": False},
            }],
            "summary": {"total": 1, "running": 1, "compacting": 0, "waiting": 0, "idle": 0},
        }
        control_center.update_status(status_data)
        qtbot.wait(200)

        # Select the worktree row
        wt_row = None
        for row, wt in control_center.row_to_worktree.items():
            if wt.get("change_id") == "focus-test":
                wt_row = row
                break
        assert wt_row is not None, "Worktree row not found"
        control_center.table.setCurrentCell(wt_row, 0)

        # Mock the platform layer
        mock_platform = MagicMock()
        mock_platform.find_window_by_title.return_value = "test-project-set-focus-test"
        mock_platform.focus_window.return_value = True

        with patch("gui.control_center.mixins.handlers.get_platform", return_value=mock_platform):
            control_center.on_focus()

        # Verify platform methods were called with correct args
        mock_platform.find_window_by_title.assert_called_once()
        call_args = mock_platform.find_window_by_title.call_args
        assert "test-project-set-focus-test" in call_args[0][0]  # worktree basename

        mock_platform.focus_window.assert_called_once()
        focus_args = mock_platform.focus_window.call_args
        assert "test-project-set-focus-test" in focus_args[0][0]  # window_id from find

    finally:
        subprocess.run(
            ["git", "-C", project_path, "worktree", "remove", "--force", wt_path],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", project_path, "branch", "-D", "change/focus-test"],
            capture_output=True,
        )


def test_on_focus_opens_editor_when_no_window(control_center, git_env, qtbot):
    """on_focus() should call set-work when no editor window found (non-blocking)."""
    project_path = str(git_env["project"])
    wt_path = str(git_env["base"] / "test-project-set-focus-warn")

    subprocess.run(
        ["git", "-C", project_path, "worktree", "add", "-b", "change/focus-warn", wt_path],
        capture_output=True, check=True,
    )

    try:
        status_data = {
            "worktrees": [{
                "project": "test-project",
                "change_id": "focus-warn",
                "path": wt_path,
                "branch": "change/focus-warn",
                "agents": [{"pid": 99999, "status": "running", "skill": None}],
                "git": {"last_commit": 0, "uncommitted_changes": False},
            }],
            "summary": {"total": 1, "running": 1, "compacting": 0, "waiting": 0, "idle": 0},
        }
        control_center.update_status(status_data)
        qtbot.wait(200)

        wt_row = None
        for row, wt in control_center.row_to_worktree.items():
            if wt.get("change_id") == "focus-warn":
                wt_row = row
                break
        assert wt_row is not None
        control_center.table.setCurrentCell(wt_row, 0)

        mock_platform = MagicMock()
        mock_platform.find_window_by_title.return_value = None  # No window found

        with patch("gui.control_center.mixins.handlers.get_platform", return_value=mock_platform), \
             patch("gui.control_center.mixins.handlers.subprocess") as mock_sub:
            control_center.on_focus()

        # Should open editor via Popen (editor CLI command), NOT show a blocking dialog
        mock_sub.Popen.assert_called_once()
        popen_args = mock_sub.Popen.call_args[0][0]
        # The command should be a list containing the worktree path
        assert isinstance(popen_args, list)
        assert wt_path in str(popen_args)

    finally:
        subprocess.run(
            ["git", "-C", project_path, "worktree", "remove", "--force", wt_path],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", project_path, "branch", "-D", "change/focus-warn"],
            capture_output=True,
        )


def test_double_click_opens_editor_when_no_window(control_center, git_env, qtbot):
    """Double-click should call set-work when no IDE window exists, regardless of agent status."""
    project_path = str(git_env["project"])
    wt_path = str(git_env["base"] / "test-project-set-focus-dblclk")

    subprocess.run(
        ["git", "-C", project_path, "worktree", "add", "-b", "change/focus-dblclk", wt_path],
        capture_output=True, check=True,
    )

    try:
        # Active agent but no IDE window
        status_data = {
            "worktrees": [{
                "project": "test-project",
                "change_id": "focus-dblclk",
                "path": wt_path,
                "branch": "change/focus-dblclk",
                "agents": [{"pid": 99999, "status": "running", "skill": None}],
                "git": {"last_commit": 0, "uncommitted_changes": False},
            }],
            "summary": {"total": 1, "running": 1, "compacting": 0, "waiting": 0, "idle": 0},
        }
        control_center.update_status(status_data)
        qtbot.wait(200)

        wt_row = None
        for row, wt in control_center.row_to_worktree.items():
            if wt.get("change_id") == "focus-dblclk":
                wt_row = row
                break
        assert wt_row is not None
        control_center.table.setCurrentCell(wt_row, 0)

        mock_platform = MagicMock()
        mock_platform.find_window_by_title.return_value = None  # No window

        with patch("gui.control_center.mixins.handlers.get_platform", return_value=mock_platform), \
             patch("gui.control_center.mixins.handlers.subprocess") as mock_sub:
            control_center.on_double_click()

        # Should open editor even though agent is active (editor CLI command)
        mock_sub.Popen.assert_called_once()
        popen_args = mock_sub.Popen.call_args[0][0]
        assert isinstance(popen_args, list)
        assert wt_path in str(popen_args)

    finally:
        subprocess.run(
            ["git", "-C", project_path, "worktree", "remove", "--force", wt_path],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", project_path, "branch", "-D", "change/focus-dblclk"],
            capture_output=True,
        )
