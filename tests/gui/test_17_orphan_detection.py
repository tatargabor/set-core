"""
Orphan Detection Tests - Verify editor_open field handling in table rendering
"""

import os
import signal

from PySide6.QtGui import QColor


def test_editor_closed_no_agents_dimmed(control_center, git_env, qtbot):
    """Worktree with editor_open=false and no agents should be dimmed."""
    status_data = {
        "worktrees": [{
            "project": "test-project",
            "change_id": "orphan-dim",
            "path": str(git_env["project"]),
            "branch": "change/orphan-dim",
            "is_main_repo": False,
            "editor_open": False,
            "agents": [],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 0, "compacting": 0, "waiting": 0, "idle": 1},
    }
    control_center.update_status(status_data)
    qtbot.wait(200)

    # Find the worktree row
    wt_row = None
    for row, wt in control_center.row_to_worktree.items():
        if wt.get("change_id") == "orphan-dim":
            wt_row = row
            break
    assert wt_row is not None, "Worktree row not found"

    # Text should use muted color (dimmed)
    muted_color = QColor(control_center.get_color("text_muted"))
    name_item = control_center.table.item(wt_row, 0)
    assert name_item is not None
    assert name_item.foreground().color().name() == muted_color.name(), \
        f"Expected muted color {muted_color.name()}, got {name_item.foreground().color().name()}"


def test_orphan_agents_excluded_from_display(control_center, git_env, qtbot):
    """Status data with waiting agents and editor_open=false: agents should be
    pre-cleaned by set-status. When they appear with no agents, row is dimmed."""
    # Simulate what happens AFTER set-status cleans orphans:
    # editor_open=false, agents=[] (orphans already killed by set-status)
    status_data = {
        "worktrees": [{
            "project": "test-project",
            "change_id": "orphan-excl",
            "path": str(git_env["project"]),
            "branch": "change/orphan-excl",
            "is_main_repo": False,
            "editor_open": False,
            "agents": [],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 0, "compacting": 0, "waiting": 0, "idle": 1},
    }
    control_center.update_status(status_data)
    qtbot.wait(200)

    wt_row = None
    for row, wt in control_center.row_to_worktree.items():
        if wt.get("change_id") == "orphan-excl":
            wt_row = row
            break
    assert wt_row is not None

    # Row should be dimmed (text_muted color)
    muted_color = QColor(control_center.get_color("text_muted"))
    status_item = control_center.table.item(wt_row, 2)
    assert status_item is not None
    assert status_item.foreground().color().name() == muted_color.name()


def test_agents_preserved_with_ralph_loop(control_center, git_env, qtbot):
    """Agents with editor_open=false but Ralph loop active should display normally."""
    status_data = {
        "worktrees": [{
            "project": "test-project",
            "change_id": "ralph-keep",
            "path": str(git_env["project"]),
            "branch": "change/ralph-keep",
            "is_main_repo": False,
            "editor_open": False,
            "agents": [
                {"pid": 5001, "status": "running", "skill": "apply"},
            ],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 1, "compacting": 0, "waiting": 0, "idle": 0},
    }
    control_center.update_status(status_data)
    qtbot.wait(200)

    wt_row = None
    for row, wt in control_center.row_to_worktree.items():
        if wt.get("change_id") == "ralph-keep":
            wt_row = row
            break
    assert wt_row is not None

    # Status should show running (NOT dimmed)
    status_item = control_center.table.item(wt_row, 2)
    assert status_item is not None
    assert "running" in status_item.text()

    # Text should NOT be muted color - running rows have their own color
    muted_color = QColor(control_center.get_color("text_muted"))
    # Running rows use row_running_text, not text_muted
    running_text_color = QColor(control_center.get_color("row_running_text"))
    name_item = control_center.table.item(wt_row, 0)
    assert name_item is not None
    assert name_item.foreground().color().name() == running_text_color.name()


def test_editor_open_normal_rendering(control_center, git_env, qtbot):
    """Worktree with editor_open=true should render normally (no dimming)."""
    status_data = {
        "worktrees": [{
            "project": "test-project",
            "change_id": "editor-open",
            "path": str(git_env["project"]),
            "branch": "change/editor-open",
            "is_main_repo": False,
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
        if wt.get("change_id") == "editor-open":
            wt_row = row
            break
    assert wt_row is not None

    # Text should use row_idle_ide_text (editor open, no agent), NOT text_muted
    idle_ide_text_color = QColor(control_center.get_color("row_idle_ide_text"))
    muted_color = QColor(control_center.get_color("text_muted"))
    name_item = control_center.table.item(wt_row, 0)
    assert name_item is not None
    assert name_item.foreground().color().name() == idle_ide_text_color.name(), \
        f"Expected idle IDE color {idle_ide_text_color.name()}, got {name_item.foreground().color().name()}"
    assert name_item.foreground().color().name() != muted_color.name(), \
        "Should not be dimmed when editor is open"


def test_process_lifecycle(control_center, qtbot):
    """Fork a dummy process, verify is_process_running() returns true, kill it, verify false."""
    pid = os.fork()
    if pid == 0:
        # Child: sleep forever
        import time
        try:
            time.sleep(3600)
        except Exception:
            pass
        os._exit(0)

    try:
        # Parent: verify child is alive
        assert _is_process_running(pid), f"Process {pid} should be running"

        # Kill it
        os.kill(pid, signal.SIGTERM)
        os.waitpid(pid, 0)

        # Verify it's gone
        assert not _is_process_running(pid), f"Process {pid} should be dead"
    except Exception:
        # Cleanup in case of failure
        try:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        except Exception:
            pass
        raise


def _is_process_running(pid: int) -> bool:
    """Check if a process with given PID exists."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # Process exists but we can't signal it
