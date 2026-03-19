"""
Memory Tests - Verify [M] button in project header, project header context menu,
MemoryBrowseDialog instantiation, and memory hooks status.
"""

import json
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QMenu, QPushButton

from gui.dialogs.memory_dialog import MemoryBrowseDialog


class _MenuCapture:
    """Context manager that intercepts QMenu.exec to prevent blocking."""

    def __init__(self):
        self.menus = []
        self._original_init = None

    def __enter__(self):
        self._original_init = QMenu.__init__
        capture = self
        original_init = self._original_init

        def patched_init(menu_self, *args, **kwargs):
            original_init(menu_self, *args, **kwargs)
            original_exec = menu_self.exec

            def non_blocking_exec(*a, **kw):
                actions = [act.text() for act in menu_self.actions() if not act.isSeparator()]
                submenus = [act.text() for act in menu_self.actions() if act.menu()]
                capture.menus.append({
                    "menu": menu_self,
                    "actions": actions,
                    "submenus": submenus,
                })
                return None

            menu_self.exec = non_blocking_exec

        QMenu.__init__ = patched_init
        return self

    def __exit__(self, *args):
        QMenu.__init__ = self._original_init

    @property
    def last_actions(self):
        return self.menus[-1]["actions"] if self.menus else []

    @property
    def last_submenus(self):
        return self.menus[-1]["submenus"] if self.menus else []


def _make_status_data(git_env):
    """Build a minimal status_data dict with one worktree."""
    return {
        "worktrees": [{
            "project": "test-project",
            "change_id": "mem-test",
            "path": str(git_env["project"]),
            "branch": "change/mem-test",
            "agents": [],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 0, "compacting": 0, "waiting": 0, "idle": 1},
    }


def _set_feature_cache(cc, memory=None, openspec=None):
    """Set feature cache directly on the control center."""
    if memory is None:
        memory = {"available": False, "count": 0}
    if openspec is None:
        openspec = {"installed": False, "changes_active": 0, "skills_present": False, "cli_available": False}
    cc._feature_cache = {"test-project": {"memory": memory, "openspec": openspec}}


def test_memory_button_in_project_header(control_center, git_env, qtbot):
    """Project header should contain an [M] button for memory."""
    _set_feature_cache(control_center)
    control_center.update_status(_make_status_data(git_env))
    qtbot.wait(200)

    # Find the project header row (row 0 should be header, spanning columns)
    assert control_center.table.rowCount() >= 2
    header_widget = control_center.table.cellWidget(0, 0)
    assert header_widget is not None, "Project header widget not found"

    # Find the [M] button inside the header widget
    mem_buttons = [btn for btn in header_widget.findChildren(QPushButton) if btn.text() == "M"]
    assert len(mem_buttons) == 1, f"Expected one [M] button, found {len(mem_buttons)}"

    mem_btn = mem_buttons[0]
    assert mem_btn.toolTip().startswith("Memory:")


def test_memory_button_purple_when_memories_exist(control_center, git_env, qtbot):
    """[M] button should be purple (status_compacting color) when memories exist."""
    _set_feature_cache(control_center, memory={"available": True, "count": 5})
    control_center.update_status(_make_status_data(git_env))
    qtbot.wait(200)

    header_widget = control_center.table.cellWidget(0, 0)
    mem_btn = [btn for btn in header_widget.findChildren(QPushButton) if btn.text() == "M"][0]

    purple_color = control_center.get_color("status_compacting")
    assert purple_color in mem_btn.styleSheet()
    assert "5 memories" in mem_btn.toolTip()


def test_project_header_context_menu(control_center, git_env, qtbot):
    """Right-click on project header row should show project header context menu with Memory submenu."""
    _set_feature_cache(control_center, memory={"available": True, "count": 3})
    control_center.update_status(_make_status_data(git_env))
    qtbot.wait(200)

    # Find the project header row
    header_row = None
    for row, proj in getattr(control_center, 'row_to_project', {}).items():
        if proj == "test-project":
            header_row = row
            break
    assert header_row is not None, "Project header row not found in row_to_project"

    with _MenuCapture() as cap:
        row_rect = control_center.table.visualRect(
            control_center.table.model().index(header_row, 0)
        )
        control_center.show_row_context_menu(row_rect.center())

    assert len(cap.menus) > 0, "Project header context menu was not created"
    actions = cap.last_actions
    # Memory submenu should appear
    assert "Memory" in cap.last_submenus or "Memory" in actions
    # Standard project actions
    assert "+ New Worktree..." in actions


def test_context_menu_install_hooks_action(control_center, git_env, qtbot):
    """Context menu should show 'Install Memory Hooks' when openspec present but hooks not installed."""
    _set_feature_cache(
        control_center,
        memory={"available": True, "count": 0},
        openspec={"installed": True, "changes_active": 1, "skills_present": True, "cli_available": True},
    )
    control_center.update_status(_make_status_data(git_env))
    qtbot.wait(200)

    header_row = None
    for row, proj in getattr(control_center, 'row_to_project', {}).items():
        if proj == "test-project":
            header_row = row
            break
    assert header_row is not None

    # Collect all actions from all menus (parent + submenus)
    all_actions = []
    with _MenuCapture() as cap:
        row_rect = control_center.table.visualRect(
            control_center.table.model().index(header_row, 0)
        )
        control_center.show_row_context_menu(row_rect.center())

    for menu_data in cap.menus:
        all_actions.extend(menu_data["actions"])

    assert "Install Memory Hooks..." in all_actions


def test_memory_browse_dialog_empty_state(control_center, qtbot):
    """MemoryBrowseDialog should show empty state when no memories exist."""
    with patch("gui.dialogs.memory_dialog._run_wt_memory", return_value="{}"):
        dialog = MemoryBrowseDialog(control_center, "test-project")

    assert dialog.windowTitle() == "Memory: test-project"
    assert dialog.windowFlags() & Qt.WindowStaysOnTopHint

    # Opens in summary mode with 0 total
    assert dialog._mode == MemoryBrowseDialog.MODE_SUMMARY
    assert "0 total memories" in dialog.status_label.text()

    dialog.close()


# -- Summary / List toggle and pagination tests --

_SAMPLE_CONTEXT = json.dumps({
    "total_memories": 5,
    "decisions": [
        {"id": "d1", "content": "Use JWT for auth", "created_at": "2026-02-15T10:00:00+00:00"},
    ],
    "learnings": [
        {"id": "l1", "content": "RocksDB needs lock", "created_at": "2026-02-15T09:00:00+00:00"},
    ],
    "context": [],
    "patterns": [],
    "errors": [],
})


def _make_memories(n):
    """Generate a list of n dummy memories as JSON string."""
    mems = []
    for i in range(n):
        mems.append({
            "id": f"mem-{i}",
            "content": f"Memory item {i}",
            "experience_type": "Learning",
            "created_at": "2026-02-15T10:00:00+00:00",
            "tags": ["test"],
        })
    return json.dumps(mems)


def test_browse_dialog_opens_in_summary_mode(control_center, qtbot):
    """Dialog should open in summary mode showing context summary."""
    with patch("gui.dialogs.memory_dialog._run_wt_memory", return_value=_SAMPLE_CONTEXT):
        dialog = MemoryBrowseDialog(control_center, "test-project")

    assert dialog._mode == MemoryBrowseDialog.MODE_SUMMARY
    assert dialog.toggle_btn.text() == "Show All"
    assert "5 total memories" in dialog.status_label.text()

    # Should have section headers + cards
    labels = [
        dialog.content_layout.itemAt(i).widget()
        for i in range(dialog.content_layout.count())
        if dialog.content_layout.itemAt(i).widget()
    ]
    texts = [lbl.text() for lbl in labels if hasattr(lbl, "text")]
    assert "Decisions" in texts
    assert "Learnings" in texts

    dialog.close()


def test_browse_dialog_toggle_to_list(control_center, qtbot):
    """Clicking 'Show All' should switch to paginated list view."""
    memories_60 = _make_memories(60)

    def mock_wt_memory(*args):
        args_list = list(args)
        if "context" in args_list:
            return _SAMPLE_CONTEXT
        if "list" in args_list:
            return memories_60
        return "[]"

    with patch("gui.dialogs.memory_dialog._run_wt_memory", side_effect=mock_wt_memory):
        dialog = MemoryBrowseDialog(control_center, "test-project")
        assert dialog._mode == MemoryBrowseDialog.MODE_SUMMARY

        # Toggle to list
        dialog._on_toggle()

    assert dialog._mode == MemoryBrowseDialog.MODE_LIST
    assert dialog.toggle_btn.text() == "Summary"
    # Should show first 50 of 60
    assert dialog._rendered_count == 50
    assert "50 of 60" in dialog.status_label.text()

    # Load More button should exist
    load_more = None
    for i in range(dialog.content_layout.count()):
        w = dialog.content_layout.itemAt(i).widget()
        if w and w.objectName() == "load_more_btn":
            load_more = w
            break
    assert load_more is not None
    assert "50 of 60" in load_more.text()

    dialog.close()


def test_browse_dialog_load_more(control_center, qtbot):
    """Clicking 'Load More' should render next batch from cache."""
    memories_60 = _make_memories(60)

    def mock_wt_memory(*args):
        args_list = list(args)
        if "context" in args_list:
            return _SAMPLE_CONTEXT
        if "list" in args_list:
            return memories_60
        return "[]"

    with patch("gui.dialogs.memory_dialog._run_wt_memory", side_effect=mock_wt_memory):
        dialog = MemoryBrowseDialog(control_center, "test-project")
        dialog._on_toggle()  # switch to list
        assert dialog._rendered_count == 50

        # Click Load More
        dialog._render_next_page()

    assert dialog._rendered_count == 60
    assert "60 of 60" in dialog.status_label.text()

    # Load More button should be gone
    load_more = None
    for i in range(dialog.content_layout.count()):
        w = dialog.content_layout.itemAt(i).widget()
        if w and w.objectName() == "load_more_btn":
            load_more = w
            break
    assert load_more is None

    dialog.close()


def test_browse_dialog_toggle_back_to_summary(control_center, qtbot):
    """Clicking 'Summary' from list mode should return to summary view."""
    def mock_wt_memory(*args):
        args_list = list(args)
        if "context" in args_list:
            return _SAMPLE_CONTEXT
        if "list" in args_list:
            return _make_memories(10)
        return "[]"

    with patch("gui.dialogs.memory_dialog._run_wt_memory", side_effect=mock_wt_memory):
        dialog = MemoryBrowseDialog(control_center, "test-project")
        dialog._on_toggle()  # to list
        assert dialog._mode == MemoryBrowseDialog.MODE_LIST

        dialog._on_toggle()  # back to summary

    assert dialog._mode == MemoryBrowseDialog.MODE_SUMMARY
    assert dialog.toggle_btn.text() == "Show All"

    dialog.close()


def test_browse_dialog_search_overrides_view(control_center, qtbot):
    """Search should override current view, Clear returns to previous mode."""
    recall_results = json.dumps([
        {"id": "r1", "content": "Found result", "experience_type": "Decision",
         "created_at": "2026-02-15T10:00:00+00:00", "tags": []},
    ])

    def mock_wt_memory(*args):
        args_list = list(args)
        if "context" in args_list:
            return _SAMPLE_CONTEXT
        if "recall" in args_list:
            return recall_results
        return "[]"

    with patch("gui.dialogs.memory_dialog._run_wt_memory", side_effect=mock_wt_memory):
        dialog = MemoryBrowseDialog(control_center, "test-project")
        assert dialog._mode == MemoryBrowseDialog.MODE_SUMMARY

        # Search
        dialog.search_input.setText("test query")
        dialog._on_search()

    assert dialog._mode == MemoryBrowseDialog.MODE_SEARCH
    assert "1 results" in dialog.status_label.text()

    # Clear should return to summary (pre-search mode)
    with patch("gui.dialogs.memory_dialog._run_wt_memory", return_value=_SAMPLE_CONTEXT):
        dialog._on_clear()

    assert dialog._mode == MemoryBrowseDialog.MODE_SUMMARY
    assert dialog.search_input.text() == ""

    dialog.close()


def test_browse_dialog_search_returns_to_list_mode(control_center, qtbot):
    """Clear after search should return to list mode if that was the pre-search mode."""
    recall_results = json.dumps([
        {"id": "r1", "content": "Found", "experience_type": "Learning",
         "created_at": "2026-02-15T10:00:00+00:00", "tags": []},
    ])

    def mock_wt_memory(*args):
        args_list = list(args)
        if "context" in args_list:
            return _SAMPLE_CONTEXT
        if "list" in args_list:
            return _make_memories(5)
        if "recall" in args_list:
            return recall_results
        return "[]"

    with patch("gui.dialogs.memory_dialog._run_wt_memory", side_effect=mock_wt_memory):
        dialog = MemoryBrowseDialog(control_center, "test-project")
        dialog._on_toggle()  # switch to list
        assert dialog._mode == MemoryBrowseDialog.MODE_LIST

        # Search from list mode
        dialog.search_input.setText("query")
        dialog._on_search()
        assert dialog._mode == MemoryBrowseDialog.MODE_SEARCH

        # Clear should return to list mode
        dialog._on_clear()

    assert dialog._mode == MemoryBrowseDialog.MODE_LIST

    dialog.close()


def test_browse_dialog_context_error_falls_back_to_list(control_center, qtbot):
    """If context_summary returns error, dialog falls back to list view."""
    error_response = json.dumps({"error": "context_summary not available"})

    def mock_wt_memory(*args):
        args_list = list(args)
        if "context" in args_list:
            return error_response
        if "list" in args_list:
            return _make_memories(3)
        return "[]"

    with patch("gui.dialogs.memory_dialog._run_wt_memory", side_effect=mock_wt_memory):
        dialog = MemoryBrowseDialog(control_center, "test-project")

    # Should have fallen back to list mode
    assert dialog._mode == MemoryBrowseDialog.MODE_LIST
    assert dialog._rendered_count == 3

    dialog.close()


# -- Export / Import button tests --


def test_export_import_buttons_exist(control_center, qtbot):
    """MemoryBrowseDialog should have Export and Import buttons."""
    with patch("gui.dialogs.memory_dialog._run_wt_memory", return_value=_SAMPLE_CONTEXT):
        dialog = MemoryBrowseDialog(control_center, "test-project")

    assert hasattr(dialog, "export_btn")
    assert hasattr(dialog, "import_btn")
    assert dialog.export_btn.text() == "Export"
    assert dialog.import_btn.text() == "Import"

    dialog.close()


def test_export_no_memories_shows_warning(control_center, qtbot):
    """Export with 0 memories should show a warning dialog."""
    status_json = json.dumps({"available": True, "count": 0})

    def mock_wt_memory(*args):
        args_list = list(args)
        if "context" in args_list:
            return _SAMPLE_CONTEXT
        if "status" in args_list and "--json" in args_list:
            return status_json
        return ""

    with patch("gui.dialogs.memory_dialog._run_wt_memory", side_effect=mock_wt_memory):
        dialog = MemoryBrowseDialog(control_center, "test-project")
        with patch("gui.dialogs.memory_dialog.show_warning") as mock_warn:
            dialog._on_export()

    mock_warn.assert_called_once()
    assert "No memories" in mock_warn.call_args[0][2]
    dialog.close()


def test_export_triggers_directory_picker(control_center, qtbot, tmp_path):
    """Export with memories should open directory picker and write file."""
    status_json = json.dumps({"available": True, "count": 5})
    export_json = json.dumps({"version": 1, "format": "set-memory-export", "count": 5, "records": []})

    def mock_wt_memory(*args):
        args_list = list(args)
        if "context" in args_list:
            return _SAMPLE_CONTEXT
        if "status" in args_list and "--json" in args_list:
            return status_json
        if "export" in args_list and "--output" in args_list:
            # Simulate writing the file
            idx = args_list.index("--output")
            filepath = args_list[idx + 1]
            with open(filepath, "w") as f:
                f.write(export_json)
            return ""
        return ""

    with patch("gui.dialogs.memory_dialog._run_wt_memory", side_effect=mock_wt_memory):
        dialog = MemoryBrowseDialog(control_center, "test-project")
        with patch("gui.dialogs.memory_dialog.get_existing_directory", return_value=str(tmp_path)) as mock_dir, \
             patch("gui.dialogs.memory_dialog.show_information") as mock_info:
            dialog._on_export()

    mock_dir.assert_called_once()
    mock_info.assert_called_once()
    assert "5 memories" in mock_info.call_args[0][2]
    dialog.close()


def test_import_triggers_file_picker_and_shows_result(control_center, qtbot, tmp_path):
    """Import should open file picker, run import, show result dialog, and refresh."""
    import_result = json.dumps({"imported": 3, "skipped": 1, "errors": 0})

    def mock_wt_memory(*args):
        args_list = list(args)
        if "context" in args_list:
            return _SAMPLE_CONTEXT
        if "import" in args_list:
            return import_result
        return ""

    fake_file = str(tmp_path / "import.json")
    with open(fake_file, "w") as f:
        f.write("{}")

    with patch("gui.dialogs.memory_dialog._run_wt_memory", side_effect=mock_wt_memory):
        dialog = MemoryBrowseDialog(control_center, "test-project")
        with patch("gui.dialogs.memory_dialog.get_open_filename", return_value=(fake_file, "")) as mock_open, \
             patch("gui.dialogs.memory_dialog.show_information") as mock_info:
            dialog._on_import()

    mock_open.assert_called_once()
    mock_info.assert_called_once()
    info_text = mock_info.call_args[0][2]
    assert "Imported: 3" in info_text
    assert "Skipped (duplicates): 1" in info_text
    dialog.close()


def test_import_error_shows_warning(control_center, qtbot, tmp_path):
    """Import with error response should show warning dialog."""
    error_result = json.dumps({"error": "Invalid JSON: blah"})

    def mock_wt_memory(*args):
        args_list = list(args)
        if "context" in args_list:
            return _SAMPLE_CONTEXT
        if "import" in args_list:
            return error_result
        return ""

    fake_file = str(tmp_path / "bad.json")
    with open(fake_file, "w") as f:
        f.write("not json")

    with patch("gui.dialogs.memory_dialog._run_wt_memory", side_effect=mock_wt_memory):
        dialog = MemoryBrowseDialog(control_center, "test-project")
        with patch("gui.dialogs.memory_dialog.get_open_filename", return_value=(fake_file, "")), \
             patch("gui.dialogs.memory_dialog.show_warning") as mock_warn:
            dialog._on_import()

    mock_warn.assert_called_once()
    assert "Invalid JSON" in mock_warn.call_args[0][2]
    dialog.close()
