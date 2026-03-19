"""
Main Repo Tests - Verify main repo row display and context menu filtering
"""

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QMenu


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


def _make_main_repo_status(project_path, project_name="test-project", branch="master"):
    """Create status data with a main repo entry."""
    return {
        "worktrees": [{
            "project": project_name,
            "change_id": branch,
            "path": project_path,
            "branch": branch,
            "is_main_repo": True,
            "agents": [],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 0, "compacting": 0, "waiting": 0, "idle": 1},
    }


def _make_mixed_status(project_path, wt_path, project_name="test-project"):
    """Create status data with both main repo and regular worktree."""
    return {
        "worktrees": [
            {
                "project": project_name,
                "change_id": "my-feature",
                "path": wt_path,
                "branch": "change/my-feature",
                "is_main_repo": False,
                "agents": [],
                "git": {"last_commit": 0, "uncommitted_changes": False},
            },
            {
                "project": project_name,
                "change_id": "master",
                "path": project_path,
                "branch": "master",
                "is_main_repo": True,
                "agents": [],
                "git": {"last_commit": 0, "uncommitted_changes": False},
            },
        ],
        "summary": {"total": 2, "running": 0, "compacting": 0, "waiting": 0, "idle": 2},
    }


def test_main_repo_row_has_star_prefix(control_center, git_env, qtbot):
    """Main repo row should display change_id with a star prefix."""
    project_path = str(git_env["project"])
    status_data = _make_main_repo_status(project_path)
    control_center.update_status(status_data)
    qtbot.wait(200)

    # Find the main repo row
    main_row = None
    for row, wt in control_center.row_to_worktree.items():
        if wt.get("is_main_repo"):
            main_row = row
            break

    assert main_row is not None, "Main repo row not found in table"

    # Check the Name column (col 0) has star prefix
    name_item = control_center.table.item(main_row, 0)
    assert name_item is not None
    assert name_item.text().startswith("\u2605"), f"Expected star prefix, got: {name_item.text()}"
    assert "master" in name_item.text()


def test_main_repo_row_is_first_under_header(control_center, git_env, qtbot):
    """Main repo row should appear before regular worktree rows under the same project."""
    project_path = str(git_env["project"])
    wt_path = str(git_env["base"] / "test-project-set-main-test")
    status_data = _make_mixed_status(project_path, wt_path)
    control_center.update_status(status_data)
    qtbot.wait(200)

    # Find both rows
    main_row = None
    wt_row = None
    for row, wt in control_center.row_to_worktree.items():
        if wt.get("is_main_repo"):
            main_row = row
        elif wt.get("change_id") == "my-feature":
            wt_row = row

    assert main_row is not None, "Main repo row not found"
    assert wt_row is not None, "Worktree row not found"
    assert main_row < wt_row, f"Main repo row ({main_row}) should be before worktree row ({wt_row})"


def test_main_repo_context_menu_excludes_worktree_actions(control_center, git_env, qtbot):
    """Context menu for main repo should not have Worktree submenu or Merge to."""
    project_path = str(git_env["project"])
    status_data = _make_main_repo_status(project_path)
    control_center.update_status(status_data)
    qtbot.wait(200)

    # Find the main repo row
    main_row = None
    for row, wt in control_center.row_to_worktree.items():
        if wt.get("is_main_repo"):
            main_row = row
            break

    assert main_row is not None, "Main repo row not found"

    with _MenuCapture() as cap:
        row_rect = control_center.table.visualRect(
            control_center.table.model().index(main_row, 0)
        )
        control_center.show_row_context_menu(row_rect.center())

    assert len(cap.menus) > 0, "Context menu was not created"
    actions = cap.last_actions
    submenus = cap.last_submenus

    # Should NOT have Worktree submenu
    assert "Worktree" not in submenus, f"Worktree submenu should not appear for main repo, got submenus: {submenus}"

    # Should NOT have Worktree Config
    assert "Worktree Config..." not in actions, f"Worktree Config should not appear for main repo"


def test_main_repo_context_menu_includes_common_actions(control_center, git_env, qtbot):
    """Context menu for main repo should include Focus, Terminal, File Manager, Git submenu."""
    project_path = str(git_env["project"])
    status_data = _make_main_repo_status(project_path)
    control_center.update_status(status_data)
    qtbot.wait(200)

    # Find the main repo row
    main_row = None
    for row, wt in control_center.row_to_worktree.items():
        if wt.get("is_main_repo"):
            main_row = row
            break

    assert main_row is not None, "Main repo row not found"

    with _MenuCapture() as cap:
        row_rect = control_center.table.visualRect(
            control_center.table.model().index(main_row, 0)
        )
        control_center.show_row_context_menu(row_rect.center())

    assert len(cap.menus) > 0, "Context menu was not created"
    actions = cap.last_actions
    submenus = cap.last_submenus

    # Should have common actions
    assert "Focus Window" in actions
    assert "Open in Terminal" in actions
    assert "Open in File Manager" in actions
    assert "Copy Path" in actions

    # Should have Git submenu
    assert "Git" in submenus, f"Git submenu should appear, got submenus: {submenus}"

    # Should have Ralph Loop submenu
    assert "Ralph Loop" in submenus, f"Ralph Loop submenu should appear, got submenus: {submenus}"

    # Should have Project submenu
    assert "Project" in submenus, f"Project submenu should appear, got submenus: {submenus}"


def test_regular_worktree_context_menu_still_has_worktree_submenu(control_center, git_env, qtbot):
    """Regular worktree context menu should still have Worktree submenu (regression check)."""
    project_path = str(git_env["project"])
    wt_path = str(git_env["base"] / "test-project-set-main-test")
    status_data = _make_mixed_status(project_path, wt_path)
    control_center.update_status(status_data)
    qtbot.wait(200)

    # Find the regular worktree row
    wt_row = None
    for row, wt in control_center.row_to_worktree.items():
        if not wt.get("is_main_repo") and wt.get("change_id") == "my-feature":
            wt_row = row
            break

    assert wt_row is not None, "Worktree row not found"

    with _MenuCapture() as cap:
        row_rect = control_center.table.visualRect(
            control_center.table.model().index(wt_row, 0)
        )
        control_center.show_row_context_menu(row_rect.center())

    assert len(cap.menus) > 0, "Context menu was not created"
    submenus = cap.last_submenus
    actions = cap.last_actions

    # Should HAVE Worktree submenu for regular worktree
    assert "Worktree" in submenus, f"Worktree submenu should appear for regular worktree, got submenus: {submenus}"
    assert "Worktree Config..." in actions, f"Worktree Config should appear for regular worktree"
