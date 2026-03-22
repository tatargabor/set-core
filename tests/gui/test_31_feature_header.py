"""
Feature Header Tests - Verify project header renders correctly with feature cache,
and that all table backgrounds are opaque (no alpha transparency).
"""

from PySide6.QtWidgets import QPushButton


def _make_status_data(git_env, agents=None):
    """Build minimal status data for one project."""
    return {
        "worktrees": [{
            "project": "test-project",
            "change_id": "main",
            "path": str(git_env["project"]),
            "branch": "main",
            "is_main_repo": True,
            "agents": agents or [],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 0, "compacting": 0, "waiting": 0, "idle": 1},
    }


def _find_header_buttons(control_center):
    """Find [M] and [O] buttons in the first project header row."""
    m_btn = None
    o_btn = None
    for row in range(control_center.table.rowCount()):
        widget = control_center.table.cellWidget(row, 0)
        if widget and control_center.table.columnSpan(row, 0) > 1:
            layout = widget.layout()
            if layout:
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item and item.widget() and isinstance(item.widget(), QPushButton):
                        btn = item.widget()
                        if btn.text() == "M":
                            m_btn = btn
                        elif btn.text() == "O":
                            o_btn = btn
            break
    return m_btn, o_btn


def test_header_with_populated_feature_cache(control_center, git_env, qtbot):
    """Project header renders without exception when _feature_cache has data."""
    control_center._feature_cache = {
        "test-project": {
            "memory": {"available": True, "count": 42},
            "openspec": {"installed": True, "changes_active": 2,
                         "skills_present": True, "cli_available": True},
        }
    }
    control_center.update_status(_make_status_data(git_env))
    qtbot.wait(200)

    m_btn, o_btn = _find_header_buttons(control_center)
    assert m_btn is not None, "Memory [M] button not found"
    assert o_btn is not None, "OpenSpec [O] button not found"

    # M button should be purple (memory available with count > 0)
    assert "checking" not in m_btn.toolTip().lower()
    assert "42" in m_btn.toolTip()

    # O button should be green (installed)
    assert "checking" not in o_btn.toolTip().lower()
    assert "2 active" in o_btn.toolTip()


def test_header_with_empty_feature_cache(control_center, git_env, qtbot):
    """Project header shows gray 'checking...' when cache is empty."""
    control_center._feature_cache = {}
    control_center.update_status(_make_status_data(git_env))
    qtbot.wait(200)

    m_btn, o_btn = _find_header_buttons(control_center)
    assert m_btn is not None, "Memory [M] button not found"
    assert o_btn is not None, "OpenSpec [O] button not found"

    assert "checking" in m_btn.toolTip().lower()
    assert "checking" in o_btn.toolTip().lower()


def test_all_row_backgrounds_opaque(control_center, git_env, qtbot):
    """Every table cell background must have alpha=255 (fully opaque)."""
    # Populate with mixed statuses
    status_data = {
        "worktrees": [
            {
                "project": "test-project",
                "change_id": "main",
                "path": str(git_env["project"]),
                "branch": "main",
                "is_main_repo": True,
                "agents": [{"pid": 1001, "status": "running"}],
                "git": {"last_commit": 0, "uncommitted_changes": False},
            },
            {
                "project": "test-project",
                "change_id": "idle-wt",
                "path": str(git_env["project"]) + "-idle",
                "branch": "change/idle-wt",
                "is_main_repo": False,
                "agents": [],
                "git": {"last_commit": 0, "uncommitted_changes": False},
            },
        ],
        "summary": {"total": 2, "running": 1, "compacting": 0, "waiting": 0, "idle": 1},
    }
    control_center._feature_cache = {}
    control_center.update_status(status_data)
    qtbot.wait(200)

    # Trigger pulse so running rows get their background set
    control_center.update_pulse()

    for row in range(control_center.table.rowCount()):
        # Skip header rows (cell widgets spanning columns)
        if control_center.table.columnSpan(row, 0) > 1:
            continue
        for col in range(control_center.table.columnCount()):
            item = control_center.table.item(row, col)
            if item:
                bg = item.background().color()
                assert bg.alpha() == 255, (
                    f"Row {row} col {col}: background alpha={bg.alpha()}, "
                    f"expected 255 (color={bg.name()})"
                )
