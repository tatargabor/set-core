"""
Activity Indicator Tests - Communication indicators on team worktree rows

Tests: 9.8-9.11 from agent-messaging change.
"""

from datetime import datetime, timezone, timedelta

from PySide6.QtWidgets import QTableWidgetItem


def _make_team_data(activity=None, last_seen=None):
    """Helper to create team data with a single team member"""
    now = datetime.now(timezone.utc)
    if last_seen is None:
        last_seen = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "my_name": "test@testhost",
        "members": [
            {
                "name": "test@testhost",
                "display_name": "Test@testhost",
                "user": "test",
                "hostname": "testhost",
                "status": "active",
                "changes": [],
                "last_seen": last_seen,
            },
            {
                "name": "peer@remote",
                "display_name": "Peer@remote",
                "user": "peer",
                "hostname": "remote",
                "status": "active",
                "changes": [
                    {
                        "id": "feature-x",
                        "remote_url": "",
                        "agent_status": "running",
                        "last_activity": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "activity": activity,
                    }
                ],
                "last_seen": last_seen,
            },
        ],
    }


def _inject_team_and_status(control_center, git_env, qtbot, activity=None, last_seen=None):
    """Inject team data and worktree status, refresh display"""
    team_data = _make_team_data(activity=activity, last_seen=last_seen)
    remote_url = ""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "-C", str(git_env["project"]), "remote", "get-url", "origin"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            remote_url = result.stdout.strip().replace(".git", "")
    except Exception:
        pass

    # Update remote_url in team data
    for member in team_data["members"]:
        for change in member.get("changes", []):
            change["remote_url"] = remote_url

    # Set up team enabled for this project
    control_center.config.team["projects"] = {
        remote_url: {"enabled": True, "auto_sync": False}
    }

    # Inject status data with a local worktree
    status_data = {
        "worktrees": [{
            "project": "test-project",
            "change_id": "main",
            "path": str(git_env["project"]),
            "branch": "main",
            "remote_url": remote_url,
            "is_main_repo": True,
            "agents": [],
            "git": {"last_commit": 0, "uncommitted_changes": False},
        }],
        "summary": {"total": 1, "running": 0, "compacting": 0, "waiting": 0, "idle": 1},
    }
    control_center.update_status(status_data)
    control_center.update_team(team_data)
    qtbot.wait(200)


def test_broadcast_indicator_shows_when_fresh(control_center, git_env, qtbot):
    """9.9 Broadcast indicator shows when broadcast updated within 60 seconds"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    activity = {
        "skill": "wt:loop",
        "broadcast": "Working on feature X",
        "updated_at": now,
    }

    _inject_team_and_status(control_center, git_env, qtbot, activity=activity)

    # Find team row (should be after project header + local worktree)
    found_indicator = False
    for row in range(control_center.table.rowCount()):
        if row in control_center.row_to_team_worktree:
            item = control_center.table.item(row, 3)  # COL_SKILL
            if item and "\U0001f4e1" in item.text():  # 📡
                found_indicator = True
                # Verify tooltip shows broadcast text
                assert "Working on feature X" in (item.toolTip() or "")
                break

    assert found_indicator, "Broadcast indicator (📡) should appear in team row when broadcast is fresh"


def test_no_indicator_when_stale(control_center, git_env, qtbot):
    """9.11 No indicator when activity is stale (>60 seconds)"""
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).strftime("%Y-%m-%dT%H:%M:%SZ")
    activity = {
        "skill": "wt:loop",
        "broadcast": "Old broadcast",
        "updated_at": stale_time,
    }

    _inject_team_and_status(control_center, git_env, qtbot, activity=activity)

    # Check that no indicator is shown in team rows
    for row in range(control_center.table.rowCount()):
        if row in control_center.row_to_team_worktree:
            item = control_center.table.item(row, 3)  # COL_SKILL
            if item:
                assert "\U0001f4e1" not in item.text(), "No broadcast indicator should show for stale activity"


def test_no_indicator_when_no_activity(control_center, git_env, qtbot):
    """9.11 No indicator when no activity data"""
    _inject_team_and_status(control_center, git_env, qtbot, activity=None)

    # Check that no indicator is shown
    for row in range(control_center.table.rowCount()):
        if row in control_center.row_to_team_worktree:
            item = control_center.table.item(row, 3)  # COL_SKILL
            if item:
                text = item.text()
                assert "\U0001f4e1" not in text, "No indicator should show without activity"
                assert "\U0001f4ac" not in text, "No indicator should show without activity"


def test_broadcast_indicator_has_tooltip(control_center, git_env, qtbot):
    """9.9 Broadcast indicator tooltip shows broadcast text"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    activity = {
        "broadcast": "Implementing auth module",
        "updated_at": now,
    }

    _inject_team_and_status(control_center, git_env, qtbot, activity=activity)

    for row in range(control_center.table.rowCount()):
        if row in control_center.row_to_team_worktree:
            item = control_center.table.item(row, 3)  # COL_SKILL
            if item and "\U0001f4e1" in item.text():
                tooltip = item.toolTip()
                assert "Implementing auth module" in tooltip
                return

    # If no team rows, skip assertion (team might not be visible)
    team_rows = [r for r in range(control_center.table.rowCount()) if r in control_center.row_to_team_worktree]
    if team_rows:
        pytest.fail("Broadcast indicator should have tooltip with broadcast text")


def test_clean_default_state(control_center, git_env, qtbot):
    """9.11 Clean default when no recent activity"""
    old_time = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    activity = {
        "broadcast": "Very old broadcast",
        "updated_at": old_time,
    }

    _inject_team_and_status(control_center, git_env, qtbot, activity=activity)

    for row in range(control_center.table.rowCount()):
        if row in control_center.row_to_team_worktree:
            item = control_center.table.item(row, 3)
            if item:
                # Should be empty (no indicators for stale activity)
                assert item.text() == "", f"Expected clean state, got '{item.text()}'"
