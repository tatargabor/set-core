"""
Create Worktree Handler Tests - Verify set-new uses SCRIPT_DIR path
"""

from unittest.mock import patch

from gui.constants import SCRIPT_DIR


def test_create_worktree_uses_script_dir_with_project(control_center):
    """create_worktree() should invoke set-new via SCRIPT_DIR, not bare PATH lookup."""
    captured = {}

    def fake_run_command_dialog(title, cmd, cwd=None):
        captured["title"] = title
        captured["cmd"] = cmd
        captured["cwd"] = cwd

    with patch.object(control_center, "run_command_dialog", fake_run_command_dialog):
        control_center.create_worktree({
            "project": "test-project",
            "change_id": "my-change",
        })

    expected_bin = str(SCRIPT_DIR / "set-new")
    assert captured["cmd"][0] == expected_bin, (
        f"Expected full path '{expected_bin}', got '{captured['cmd'][0]}'"
    )
    assert captured["cmd"] == [expected_bin, "-p", "test-project", "my-change"]


def test_create_worktree_uses_script_dir_with_local_path(control_center, tmp_path):
    """create_worktree() with local_path should also use SCRIPT_DIR for set-new."""
    captured = {}

    def fake_run_command_dialog(title, cmd, cwd=None):
        captured["title"] = title
        captured["cmd"] = cmd
        captured["cwd"] = cwd

    local = str(tmp_path / "local-repo")

    with patch.object(control_center, "run_command_dialog", fake_run_command_dialog):
        control_center.create_worktree({
            "project": "some-project",
            "change_id": "local-change",
            "local_path": local,
        })

    expected_bin = str(SCRIPT_DIR / "set-new")
    assert captured["cmd"][0] == expected_bin, (
        f"Expected full path '{expected_bin}', got '{captured['cmd'][0]}'"
    )
    assert captured["cmd"] == [expected_bin, "local-change"]
    assert captured["cwd"] == local
