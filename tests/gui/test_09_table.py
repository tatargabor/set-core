"""
Table Tests - Verify table rendering, columns, and interactions
"""

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidget


def test_empty_table_renders(control_center):
    """Empty table (no worktrees) should render without crash."""
    table = control_center.table
    assert isinstance(table, QTableWidget)
    # Table may have 0 or more rows (depending on status worker response)
    assert table.rowCount() >= 0


def test_table_columns_correct(control_center):
    """Table should have 6 columns with correct headers."""
    table = control_center.table
    assert table.columnCount() == 6

    expected = ["Branch", "PID", "Status", "Skill", "Ctx%", "Extra"]
    for i, text in enumerate(expected):
        header = table.horizontalHeaderItem(i)
        assert header is not None
        assert header.text() == text


def test_table_with_worktree_shows_project_header(control_center, git_env, qtbot):
    """With a worktree, table should show a project header row."""
    status_data = {
        "worktrees": [{
            "project": "test-project",
            "change_id": "header-test",
            "path": str(git_env["project"]),
            "branch": "change/header-test",
            "agents": [],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 0, "compacting": 0, "waiting": 0, "idle": 1},
    }
    control_center.update_status(status_data)
    qtbot.wait(200)

    # Should have at least 2 rows: project header + worktree
    assert control_center.table.rowCount() >= 2

    # First row should be a project header (spanning columns)
    span = control_center.table.columnSpan(0, 0)
    assert span > 1, f"Project header row should span columns, but span is {span}"


def test_double_click_no_crash(control_center, git_env, qtbot):
    """Double-clicking on a row should not crash (even if no action succeeds)."""
    status_data = {
        "worktrees": [{
            "project": "test-project",
            "change_id": "dblclick-test",
            "path": str(git_env["project"]),
            "branch": "change/dblclick-test",
            "agents": [],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 0, "compacting": 0, "waiting": 0, "idle": 1},
    }
    control_center.update_status(status_data)
    qtbot.wait(200)

    # Find a worktree row (not header)
    wt_row = None
    for row, wt in control_center.row_to_worktree.items():
        wt_row = row
        break

    if wt_row is not None:
        # Double-click - should not raise exception
        rect = control_center.table.visualRect(
            control_center.table.model().index(wt_row, 0)
        )
        qtbot.mouseDClick(control_center.table.viewport(), Qt.LeftButton, pos=rect.center())


def test_multi_agent_rows(control_center, git_env, qtbot):
    """Worktree with multiple agents should render multiple rows."""
    status_data = {
        "worktrees": [{
            "project": "test-project",
            "change_id": "main",
            "path": str(git_env["project"]),
            "branch": "main",
            "is_main_repo": True,
            "agents": [
                {"pid": 1001, "status": "running", "skill": "apply"},
                {"pid": 1002, "status": "waiting", "skill": "explore"},
            ],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 1, "compacting": 0, "waiting": 1, "idle": 0},
    }
    control_center.update_status(status_data)
    qtbot.wait(200)

    # Should have 3 rows: 1 header + 2 agent rows
    assert control_center.table.rowCount() == 3

    # Row 1 (first agent): Name should have the branch label
    name_item = control_center.table.item(1, 0)
    assert name_item is not None
    assert "main" in name_item.text()

    # Row 1: PID should be "1001"
    pid_item = control_center.table.item(1, 1)
    assert pid_item is not None
    assert pid_item.text() == "1001"

    # Row 1: Status should be "running"
    status_item = control_center.table.item(1, 2)
    assert status_item is not None
    assert "running" in status_item.text()

    # Row 1: Skill should be "apply"
    skill_item = control_center.table.item(1, 3)
    assert skill_item is not None
    assert skill_item.text() == "apply"

    # Row 2 (second agent): Name should be empty
    name_item2 = control_center.table.item(2, 0)
    assert name_item2 is not None
    assert name_item2.text() == ""

    # Row 2: PID should be "1002"
    pid_item2 = control_center.table.item(2, 1)
    assert pid_item2 is not None
    assert pid_item2.text() == "1002"

    # Row 2: Status should be "waiting"
    status_item2 = control_center.table.item(2, 2)
    assert status_item2 is not None
    assert "waiting" in status_item2.text()

    # Row 2: Skill should be "explore"
    skill_item2 = control_center.table.item(2, 3)
    assert skill_item2 is not None
    assert skill_item2.text() == "explore"

    # Both rows should map to the same worktree
    assert control_center.row_to_worktree[1] == control_center.row_to_worktree[2]


def test_single_agent_row(control_center, git_env, qtbot):
    """Worktree with single agent should render one row."""
    status_data = {
        "worktrees": [{
            "project": "test-project",
            "change_id": "feature-x",
            "path": str(git_env["project"]),
            "branch": "change/feature-x",
            "is_main_repo": False,
            "agents": [
                {"pid": 2001, "status": "running", "skill": "commit"},
            ],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 1, "compacting": 0, "waiting": 0, "idle": 0},
    }
    control_center.update_status(status_data)
    qtbot.wait(200)

    # Should have 2 rows: 1 header + 1 worktree row
    assert control_center.table.rowCount() == 2

    # Row 1: Name should have change_id
    name_item = control_center.table.item(1, 0)
    assert name_item is not None
    assert "feature-x" in name_item.text()


def test_idle_worktree_row(control_center, git_env, qtbot):
    """Worktree with no agents should render one idle row."""
    status_data = {
        "worktrees": [{
            "project": "test-project",
            "change_id": "idle-wt",
            "path": str(git_env["project"]),
            "branch": "change/idle-wt",
            "is_main_repo": False,
            "agents": [],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 0, "compacting": 0, "waiting": 0, "idle": 1},
    }
    control_center.update_status(status_data)
    qtbot.wait(200)

    # Should have 2 rows: 1 header + 1 worktree row
    assert control_center.table.rowCount() == 2

    # Row 1: Status should be idle (col 2)
    status_item = control_center.table.item(1, 2)
    assert status_item is not None
    assert "idle" in status_item.text()


def test_set_row_background_covers_all_columns(control_center, git_env, qtbot):
    """_set_row_background should set background on items AND cellWidgets."""
    status_data = {
        "worktrees": [{
            "project": "test-project",
            "change_id": "bg-test",
            "path": str(git_env["project"]),
            "branch": "change/bg-test",
            "is_main_repo": False,
            "agents": [{"pid": 9999, "status": "waiting"}],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 0, "compacting": 0, "waiting": 1, "idle": 0},
    }
    control_center.update_status(status_data)
    qtbot.wait(200)

    # Find the worktree row
    wt_row = None
    for row in control_center.row_to_worktree:
        wt_row = row
        break
    assert wt_row is not None

    # Apply a fully opaque color via the helper
    test_color = QColor(255, 0, 0)
    control_center._set_row_background(wt_row, test_color)

    # Verify all columns with items got the background
    for col in range(control_center.table.columnCount()):
        item = control_center.table.item(wt_row, col)
        if item:
            bg = item.background().color()
            assert bg.red() == 255, f"Column {col} item background red should be 255, got {bg.red()}"
            assert bg.alpha() == 255, f"Column {col} item background should be opaque"

        # Verify cellWidgets are transparent (item background shows through)
        widget = control_center.table.cellWidget(wt_row, col)
        if widget:
            assert "transparent" in widget.styleSheet(), f"Column {col} cellWidget should be transparent"


def test_pulse_covers_cellwidget(control_center, git_env, qtbot):
    """Pulse animation should color cellWidgets (Extra column) too."""
    status_data = {
        "worktrees": [{
            "project": "test-project",
            "change_id": "pulse-test",
            "path": str(git_env["project"]),
            "branch": "change/pulse-test",
            "is_main_repo": False,
            "agents": [{"pid": 8888, "status": "running"}],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 1, "compacting": 0, "waiting": 0, "idle": 0},
    }
    control_center.update_status(status_data)
    qtbot.wait(200)

    assert len(control_center.running_rows) > 0

    # Trigger one pulse update
    control_center.update_pulse()

    # Check that all columns in running rows got colored
    for row in control_center.running_rows:
        for col in range(control_center.table.columnCount()):
            item = control_center.table.item(row, col)
            if item:
                bg = item.background().color()
                # Pulse uses green (34, 197, 94) blended with bg_dialog (opaque)
                assert bg.green() > 50, f"Row {row} col {col}: expected green-tinted pulse, got g={bg.green()}"
                assert bg.alpha() == 255, f"Row {row} col {col}: pulse color should be opaque"
