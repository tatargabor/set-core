"""
Worktree Operation Tests - Real git worktree create/list/close
"""

import os
import subprocess

from PySide6.QtWidgets import QApplication


def test_create_worktree(git_env):
    """Creating a worktree with git should work in our test environment."""
    project_path = str(git_env["project"])
    wt_path = str(git_env["base"] / "test-project-wt-create-test")

    result = subprocess.run(
        ["git", "-C", project_path, "worktree", "add", "-b", "change/create-test", wt_path],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"git worktree add failed: {result.stderr}"

    # Verify worktree exists
    assert os.path.isdir(wt_path)

    # Verify it appears in git worktree list
    list_result = subprocess.run(
        ["git", "-C", project_path, "worktree", "list"],
        capture_output=True, text=True,
    )
    assert "create-test" in list_result.stdout

    # Verify branch exists
    branch_result = subprocess.run(
        ["git", "-C", project_path, "branch", "--list", "change/create-test"],
        capture_output=True, text=True,
    )
    assert "change/create-test" in branch_result.stdout

    # Cleanup
    subprocess.run(
        ["git", "-C", project_path, "worktree", "remove", "--force", wt_path],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", project_path, "branch", "-D", "change/create-test"],
        capture_output=True,
    )


def test_worktree_appears_in_table(control_center, git_env, qtbot):
    """A created worktree should appear in the GUI table after status update."""
    project_path = str(git_env["project"])
    wt_path = str(git_env["base"] / "test-project-wt-table-test")

    subprocess.run(
        ["git", "-C", project_path, "worktree", "add", "-b", "change/table-test", wt_path],
        capture_output=True, check=True,
    )

    try:
        # Feed status data directly to the GUI
        status_data = {
            "worktrees": [{
                "project": "test-project",
                "change_id": "table-test",
                "path": wt_path,
                "branch": "change/table-test",
                "agents": [],
                "git": {"last_commit": 0, "uncommitted_changes": False},
            }],
            "summary": {"total": 1, "running": 0, "compacting": 0, "waiting": 0, "idle": 1},
        }
        control_center.update_status(status_data)
        qtbot.wait(200)

        # Check if "table-test" appears somewhere in the table
        found = False
        for row in range(control_center.table.rowCount()):
            for col in range(control_center.table.columnCount()):
                item = control_center.table.item(row, col)
                if item and "table-test" in item.text():
                    found = True
                    break
            if found:
                break

        assert found, "Worktree 'table-test' not found in table"
    finally:
        subprocess.run(
            ["git", "-C", project_path, "worktree", "remove", "--force", wt_path],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", project_path, "branch", "-D", "change/table-test"],
            capture_output=True,
        )


def test_copy_path_to_clipboard(control_center, git_env, qtbot):
    """Copy Path should put the worktree path in the clipboard."""
    wt_path = str(git_env["project"])

    # Use the copy_to_clipboard method directly
    control_center.copy_to_clipboard(wt_path)

    clipboard = QApplication.clipboard()
    assert clipboard.text() == wt_path


def test_close_worktree(git_env):
    """Removing a worktree with git should clean up directory and branch listing."""
    project_path = str(git_env["project"])
    wt_path = str(git_env["base"] / "test-project-set-close-test")

    # Create worktree
    subprocess.run(
        ["git", "-C", project_path, "worktree", "add", "-b", "change/close-test", wt_path],
        capture_output=True, check=True,
    )
    assert os.path.isdir(wt_path)

    # Remove worktree
    result = subprocess.run(
        ["git", "-C", project_path, "worktree", "remove", "--force", wt_path],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"git worktree remove failed: {result.stderr}"

    # Verify directory is gone
    assert not os.path.isdir(wt_path)

    # Verify not in worktree list
    list_result = subprocess.run(
        ["git", "-C", project_path, "worktree", "list"],
        capture_output=True, text=True,
    )
    assert "close-test" not in list_result.stdout

    # Cleanup branch
    subprocess.run(
        ["git", "-C", project_path, "branch", "-D", "change/close-test"],
        capture_output=True,
    )
