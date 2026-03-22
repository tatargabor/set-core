"""
Compact View Filter Tests - Verify the active filter button behavior
"""


def _make_worktree(change_id, status="idle", is_main_repo=False, project="test-project", editor_open=False):
    """Create a minimal worktree dict for testing."""
    agents = [] if status == "idle" else [{"pid": 99999, "status": status, "skill": None}]
    return {
        "project": project,
        "change_id": change_id,
        "path": f"/tmp/test/{change_id}",
        "branch": f"change/{change_id}",
        "is_main_repo": is_main_repo,
        "editor_open": editor_open,
        "agents": agents,
        "git": {"last_commit": 0, "uncommitted_changes": False},
    }


def test_filter_button_exists(control_center):
    """Filter button should exist and be checkable."""
    btn = control_center.btn_filter
    assert btn is not None
    assert btn.isCheckable()


def test_filter_button_tooltip(control_center):
    """Filter button tooltip should say 'Show only active worktrees'."""
    assert control_center.btn_filter.toolTip() == "Show only active worktrees"


def test_filter_shows_only_active_worktrees(control_center, qapp):
    """When filter is active, only running/waiting worktrees appear."""
    original_wts = control_center.worktrees
    original_filter = control_center.filter_active

    try:
        control_center.worktrees = [
            _make_worktree("idle-one", status="idle"),
            _make_worktree("running-one", status="running"),
            _make_worktree("waiting-one", status="waiting"),
            _make_worktree("running-two", status="running"),
        ]

        # Enable filter
        control_center.filter_active = True
        control_center.refresh_table_display()
        qapp.processEvents()

        # Collect visible change_ids from the table
        visible = []
        for row_idx, wt in control_center.row_to_worktree.items():
            visible.append(wt["change_id"])

        assert "running-one" in visible
        assert "waiting-one" in visible
        assert "running-two" in visible
        assert "idle-one" not in visible
    finally:
        control_center.worktrees = original_wts
        control_center.filter_active = original_filter
        control_center.refresh_table_display()
        qapp.processEvents()


def test_filter_hides_idle_main_repo(control_center, qapp):
    """When filter is active, idle main repo is hidden."""
    original_wts = control_center.worktrees
    original_filter = control_center.filter_active

    try:
        control_center.worktrees = [
            _make_worktree("main", status="idle", is_main_repo=True),
            _make_worktree("active-one", status="running"),
        ]

        control_center.filter_active = True
        control_center.refresh_table_display()
        qapp.processEvents()

        visible = [wt["change_id"] for wt in control_center.row_to_worktree.values()]

        assert "main" not in visible
        assert "active-one" in visible
    finally:
        control_center.worktrees = original_wts
        control_center.filter_active = original_filter
        control_center.refresh_table_display()
        qapp.processEvents()


def test_filter_shows_active_main_repo(control_center, qapp):
    """Main repo with running agent is shown in compact view."""
    original_wts = control_center.worktrees
    original_filter = control_center.filter_active

    try:
        control_center.worktrees = [
            _make_worktree("main", status="running", is_main_repo=True),
            _make_worktree("feature", status="running"),
        ]

        control_center.filter_active = True
        control_center.refresh_table_display()
        qapp.processEvents()

        visible = [wt["change_id"] for wt in control_center.row_to_worktree.values()]

        assert "main" in visible
        assert "feature" in visible
    finally:
        control_center.worktrees = original_wts
        control_center.filter_active = original_filter
        control_center.refresh_table_display()
        qapp.processEvents()


def test_filter_off_shows_all(control_center, qapp):
    """When filter is off, all worktrees are shown."""
    original_wts = control_center.worktrees
    original_filter = control_center.filter_active

    try:
        control_center.worktrees = [
            _make_worktree("main", status="idle", is_main_repo=True),
            _make_worktree("idle-one", status="idle"),
            _make_worktree("running-one", status="running"),
        ]

        control_center.filter_active = False
        control_center.refresh_table_display()
        qapp.processEvents()

        visible = [wt["change_id"] for wt in control_center.row_to_worktree.values()]

        assert "main" in visible
        assert "idle-one" in visible
        assert "running-one" in visible
    finally:
        control_center.worktrees = original_wts
        control_center.filter_active = original_filter
        control_center.refresh_table_display()
        qapp.processEvents()


def test_filter_shows_ide_open_worktrees(control_center, qapp):
    """When filter is active, worktrees with editor_open are shown even without agents."""
    original_wts = control_center.worktrees
    original_filter = control_center.filter_active

    try:
        control_center.worktrees = [
            _make_worktree("idle-no-ide", status="idle", editor_open=False),
            _make_worktree("idle-with-ide", status="idle", editor_open=True),
            _make_worktree("running-one", status="running"),
        ]

        control_center.filter_active = True
        control_center.refresh_table_display()
        qapp.processEvents()

        visible = [wt["change_id"] for wt in control_center.row_to_worktree.values()]

        assert "idle-with-ide" in visible
        assert "running-one" in visible
        assert "idle-no-ide" not in visible
    finally:
        control_center.worktrees = original_wts
        control_center.filter_active = original_filter
        control_center.refresh_table_display()
        qapp.processEvents()
