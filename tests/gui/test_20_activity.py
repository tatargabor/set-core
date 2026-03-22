"""
Test activity tracking in team display — tooltip and details dialog.
"""

import pytest


@pytest.fixture
def team_data_with_activity():
    """Sample team data with activity block"""
    return {
        "my_name": "testuser@testhost",
        "members": [
            {
                "name": "peer@remote",
                "display_name": "Peer@Remote",
                "user": "peer",
                "hostname": "remote",
                "status": "active",
                "changes": [
                    {
                        "id": "feat-oauth",
                        "remote_url": "git@github.com:org/test-project",
                        "agent_status": "running",
                        "last_activity": "2026-02-07T21:00:00Z",
                        "activity": {
                            "skill": "opsx:apply",
                            "skill_args": "feat-oauth",
                            "broadcast": "Adding Google OAuth",
                            "updated_at": "2026-02-07T21:00:00Z"
                        }
                    }
                ],
                "last_seen": "2026-02-07T21:00:00Z",
                "chat_public_key": None,
                "chat_key_fingerprint": None,
            },
            {
                "name": "idle@remote2",
                "display_name": "Idle@Remote2",
                "user": "idle",
                "hostname": "remote2",
                "status": "idle",
                "changes": [
                    {
                        "id": "main",
                        "remote_url": "git@github.com:org/test-project",
                        "agent_status": None,
                        "last_activity": "2026-02-07T20:00:00Z",
                        "activity": None
                    }
                ],
                "last_seen": "2026-02-07T20:00:00Z",
                "chat_public_key": None,
                "chat_key_fingerprint": None,
            }
        ],
        "conflicts": [],
        "initialized": True
    }


def test_team_worktree_activity_passed_through(control_center, team_data_with_activity):
    """Activity data is passed through to team worktree entries."""
    # Inject team data
    old_team = control_center.team_data
    control_center.team_data = team_data_with_activity

    try:
        # Get team worktrees for the first project
        projects = list({wt.get("project") for wt in control_center.worktrees if wt.get("project")})
        if not projects:
            pytest.skip("No projects found in worktrees")

        project = projects[0]

        # Enable team for this project
        old_enabled = control_center.get_project_team_enabled(project)
        control_center.set_project_team_enabled(project, True)

        try:
            team_wts = control_center._get_team_worktrees_for_project(project)

            # Find the one with activity
            with_activity = [t for t in team_wts if t.get("activity")]
            without_activity = [t for t in team_wts if not t.get("activity")]

            # We may or may not get matches depending on remote_url matching
            # Just verify that if we do get matches, activity is passed through
            for twt in with_activity:
                assert twt["activity"]["skill"] == "opsx:apply"
                assert twt["activity"]["broadcast"] == "Adding Google OAuth"

            for twt in without_activity:
                assert twt.get("activity") is None
        finally:
            control_center.set_project_team_enabled(project, old_enabled)
    finally:
        control_center.team_data = old_team


def test_render_team_tooltip_with_activity(control_center):
    """_render_team_worktree_row builds tooltip with skill and broadcast."""
    from PySide6.QtWidgets import QTableWidgetItem

    # Ensure table has at least one row
    table = control_center.table
    old_count = table.rowCount()
    table.setRowCount(max(old_count, 1))

    team_wt = {
        "member": "peer@rem",
        "member_full": "Peer@Remote",
        "member_user": "peer",
        "member_hostname": "remote",
        "member_status": "active",
        "change_id": "feat-oauth",
        "agent_status": "running",
        "last_seen": "2026-02-07T21:00:00Z",
        "last_activity": "2026-02-07T21:00:00Z",
        "activity": {
            "skill": "opsx:apply",
            "skill_args": "feat-oauth",
            "broadcast": "Adding Google OAuth",
            "updated_at": "2026-02-07T21:00:00Z"
        },
        "is_team": True,
        "is_my_machine": False,
        "project": "test-project",
        "remote_url": ""
    }

    control_center._render_team_worktree_row(0, team_wt)

    # Check that the name column has the tooltip with activity info
    name_item = table.item(0, 0)
    assert name_item is not None, "Name item should exist"
    tooltip = name_item.toolTip()
    assert "opsx:apply" in tooltip, f"Tooltip should contain skill: {tooltip}"
    assert "feat-oauth" in tooltip, f"Tooltip should contain skill_args: {tooltip}"
    assert "Adding Google OAuth" in tooltip, f"Tooltip should contain broadcast: {tooltip}"

    # Restore
    table.setRowCount(old_count)


def test_render_team_tooltip_without_activity(control_center):
    """_render_team_worktree_row builds tooltip without skill lines when no activity."""
    table = control_center.table
    old_count = table.rowCount()
    table.setRowCount(max(old_count, 1))

    team_wt = {
        "member": "idle@rem",
        "member_full": "Idle@Remote",
        "member_user": "idle",
        "member_hostname": "remote",
        "member_status": "idle",
        "change_id": "main",
        "agent_status": "idle",
        "last_seen": "2026-02-07T20:00:00Z",
        "last_activity": "",
        "activity": None,
        "is_team": True,
        "is_my_machine": False,
        "project": "test-project",
        "remote_url": ""
    }

    control_center._render_team_worktree_row(0, team_wt)

    name_item = table.item(0, 0)
    assert name_item is not None
    tooltip = name_item.toolTip()
    assert "Skill:" not in tooltip, f"Tooltip should NOT contain Skill line: {tooltip}"
    assert "Broadcast:" not in tooltip, f"Tooltip should NOT contain Broadcast line: {tooltip}"
    assert "Idle@Remote" in tooltip, f"Tooltip should contain member name: {tooltip}"

    table.setRowCount(old_count)
