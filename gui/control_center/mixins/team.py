"""
Team Mixin - Team sync and worktree management
"""

import json
import subprocess
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from ...constants import SCRIPT_DIR, CONFIG_DIR, ICON_RUNNING, ICON_WAITING
from ...dialogs.helpers import show_warning, show_information, show_question
from ...logging_setup import safe_slot

__all__ = ["TeamMixin"]

# Cache directory for MCP server access
CACHE_DIR = Path.home() / ".cache" / "set-core"


class TeamMixin:
    """Mixin for team sync functionality"""

    def _get_project_remote_url(self, project: str) -> str:
        """Get the git remote URL for a project from worktrees"""
        for wt in getattr(self, 'worktrees', []):
            if wt.get("project") == project:
                return wt.get("remote_url", "")
        return ""

    def get_project_team_enabled(self, project: str) -> bool:
        """Check if team is enabled for a specific project (by remote_url)"""
        remote_url = self._get_project_remote_url(project)
        if not remote_url:
            return False
        projects = self.config.team.get("projects", {})
        return projects.get(remote_url, {}).get("enabled", False)

    def set_project_team_enabled(self, project: str, enabled: bool):
        """Set team enabled for a specific project (by remote_url)"""
        remote_url = self._get_project_remote_url(project)
        if not remote_url:
            return
        if "projects" not in self.config.team:
            self.config.team["projects"] = {}
        if remote_url not in self.config.team["projects"]:
            self.config.team["projects"][remote_url] = {}
        self.config.team["projects"][remote_url]["enabled"] = enabled

    def get_project_team_auto_sync(self, project: str) -> bool:
        """Get auto_sync setting for a specific project (by remote_url)"""
        remote_url = self._get_project_remote_url(project)
        if not remote_url:
            return True
        projects = self.config.team.get("projects", {})
        return projects.get(remote_url, {}).get("auto_sync", True)

    def set_project_team_auto_sync(self, project: str, auto_sync: bool):
        """Set auto_sync for a specific project (by remote_url)"""
        remote_url = self._get_project_remote_url(project)
        if not remote_url:
            return
        if "projects" not in self.config.team:
            self.config.team["projects"] = {}
        if remote_url not in self.config.team["projects"]:
            self.config.team["projects"][remote_url] = {}
        self.config.team["projects"][remote_url]["auto_sync"] = auto_sync

    def any_project_team_enabled(self) -> bool:
        """Check if ANY project has team enabled"""
        projects = self.config.team.get("projects", {})
        return any(p.get("enabled", False) for p in projects.values())

    def _get_project_remote_urls(self) -> dict:
        """Build mapping of remote_url -> local project name from worktrees"""
        url_to_project = {}
        for wt in self.worktrees:
            remote_url = wt.get("remote_url", "")
            project = wt.get("project", "")
            if remote_url and project:
                url_to_project[remote_url] = project
        return url_to_project

    def _get_team_project(self) -> str:
        """Get the project for which we have team data (the active project)"""
        return self.get_active_project() or ""

    def _project_has_team_data(self, project: str) -> bool:
        """Check if a project has team data (by matching remote_url)"""
        if not self.team_data.get("members"):
            return False

        # Get remote URLs for this local project
        url_to_project = self._get_project_remote_urls()
        project_urls = {url for url, proj in url_to_project.items() if proj == project}

        if not project_urls:
            return False

        # Check if any team member has changes for this remote_url
        for member in self.team_data.get("members", []):
            for change in member.get("changes", []):
                if change.get("remote_url", "") in project_urls:
                    return True

        # Also return True if this is the active project (where set-control lives)
        team_project = self._get_team_project()
        return project == team_project

    def _get_team_worktrees_for_project(self, project: str) -> list:
        """Get team worktrees for a specific project, filtered by project's team_filter_state

        Team worktrees are matched by remote_url, not project name, since different
        machines may use different local directory names for the same repo.
        """
        if not self.team_data.get("members"):
            return []

        # Build remote_url -> local project mapping
        url_to_project = self._get_project_remote_urls()

        # Get remote URLs for this local project
        project_urls = {url for url, proj in url_to_project.items() if proj == project}
        if not project_urls:
            return []

        proj_filter = self.team_filter_state.get(project, 0)
        if proj_filter == 2:  # Hidden
            return []

        my_name = self.team_data.get("my_name", "")
        my_user = my_name.split("@")[0] if my_name else ""
        my_hostname = my_name.split("@")[1] if "@" in my_name else ""

        team_worktrees = []

        for member in self.team_data.get("members", []):
            member_name = member.get("name", "")
            if member_name == my_name:
                continue  # Skip self

            member_user = member.get("user", member_name.split("@")[0])
            member_hostname = member.get("hostname", "")
            if not member_hostname and "@" in member_name:
                member_hostname = member_name.split("@")[1]
            display_name = member.get("display_name") or member_name
            # Build short display: user@host (truncated to fit column)
            user_short = member_user[:8] if len(member_user) > 8 else member_user
            host_short = member_hostname[:8] if len(member_hostname) > 8 else member_hostname
            member_display = f"{user_short}@{host_short}" if host_short else user_short
            member_status = member.get("status", "idle")
            last_seen = member.get("last_seen", "")

            # Apply "My Machines" filter
            is_my_machine = (member_user == my_user and member_hostname != my_hostname)
            if proj_filter == 1 and not is_my_machine:
                continue

            for change in member.get("changes", []):
                # Match by remote_url instead of project name
                change_remote_url = change.get("remote_url", "")
                if change_remote_url not in project_urls:
                    continue

                team_worktrees.append({
                    "member": member_display,
                    "member_full": display_name,
                    "member_user": member_user,
                    "member_hostname": member_hostname,
                    "member_status": member_status,
                    "change_id": change.get("id", "?"),
                    "agent_status": change.get("agent_status", "idle"),
                    "last_seen": last_seen,
                    "last_activity": change.get("last_activity", ""),
                    "activity": change.get("activity"),
                    "is_team": True,
                    "is_my_machine": is_my_machine,
                    "project": project,
                    "remote_url": change_remote_url
                })

        # Sort: my machines first, then running > waiting > idle, then by member
        status_order = {"running": 0, "waiting": 1, "idle": 2}
        team_worktrees.sort(key=lambda t: (
            0 if t["is_my_machine"] else 1,
            status_order.get(t["agent_status"], 2),
            t["member"]
        ))

        return team_worktrees

    def toggle_project_team_filter(self, project: str):
        """Cycle team filter for specific project: All Team -> My Machines -> Hide -> All Team"""
        current = self.team_filter_state.get(project, 0)
        self.team_filter_state[project] = (current + 1) % 3
        self.refresh_table_display()

    @safe_slot
    def update_team(self, data: dict):
        """Handle team data update from worker"""
        self.team_data = data
        self.update_team_display()
        # Refresh table to show team buttons and rows
        self.refresh_table_display()
        # Write team status cache for MCP server
        self._write_team_status_cache(data)

    def on_team_error(self, error: str):
        """Handle team sync error"""
        # Silently ignore errors for now - team sync is optional
        pass

    def update_team_display(self):
        """Update the team status display"""
        if not hasattr(self, 'team_label'):
            return

        # Check if any project has team enabled
        any_team_enabled = self.any_project_team_enabled()

        # Update chat worker project
        if hasattr(self, 'chat_worker') and self.worktrees:
            self.chat_worker.set_project(self.worktrees[0].get("project"))

        if not any_team_enabled:
            self.team_label.setText("")
            self.team_label.setVisible(False)
            return

        members = self.team_data.get("members", [])
        conflicts = self.team_data.get("conflicts", [])
        my_name = self.team_data.get("my_name", "")

        if not members:
            if not self.team_data.get("initialized", True):
                self.team_label.setText("Team: not initialized")
                self.team_label.setStyleSheet(f"color: {self.get_color('text_muted')}; padding: 2px 5px;")
            else:
                self.team_label.setText("Team: syncing...")
                self.team_label.setStyleSheet(f"color: {self.get_color('text_muted')}; padding: 2px 5px;")
            self.team_label.setVisible(True)
            return

        # Count active team members (excluding self)
        active_others = [m for m in members if m.get("status") == "active" and m.get("name") != my_name]
        waiting_others = [m for m in members if m.get("status") == "waiting" and m.get("name") != my_name]

        parts = []
        if active_others:
            names = ", ".join(m.get("display_name", m.get("name", "?"))[:15] for m in active_others[:3])
            if len(active_others) > 3:
                names += f" +{len(active_others) - 3}"
            parts.append(f"<span style='color: {self.get_color('status_running')}'>{ICON_RUNNING} {names}</span>")

        if waiting_others:
            names = ", ".join(m.get("display_name", m.get("name", "?"))[:15] for m in waiting_others[:2])
            if len(waiting_others) > 2:
                names += f" +{len(waiting_others) - 2}"
            parts.append(f"<span style='color: {self.get_color('status_waiting')}'>{ICON_WAITING} {names}</span>")

        if conflicts:
            conflict_ids = ", ".join(c.get("change_id", "?") for c in conflicts[:2])
            parts.append(f"<span style='color: {self.get_color('burn_high')}'>! {conflict_ids}</span>")

        from PySide6.QtCore import Qt
        if parts:
            self.team_label.setText("Team: " + " | ".join(parts))
            self.team_label.setTextFormat(Qt.RichText)
        else:
            idle_count = len([m for m in members if m.get("name") != my_name])
            if idle_count > 0:
                self.team_label.setText(f"Team: {idle_count} member{'s' if idle_count > 1 else ''} idle")
            else:
                self.team_label.setText("Team: just you")
            self.team_label.setStyleSheet(f"color: {self.get_color('text_muted')}; padding: 2px 5px;")

        self.team_label.setVisible(True)

    def generate_chat_key_for_project(self, project: str):
        """Generate chat encryption key for the given project"""
        if not project:
            show_warning(self, "Error", "No project specified")
            return

        try:
            import sys
            gui_dir = Path(__file__).parent.parent.parent
            if str(gui_dir) not in sys.path:
                sys.path.insert(0, str(gui_dir))

            import chat_crypto
            if not chat_crypto.is_available():
                show_warning(self, "Error", "PyNaCl not installed - run: pip install PyNaCl")
                return

            # Check if key exists and confirm regeneration
            if chat_crypto.has_key(project):
                reply = show_question(
                    self, "Confirm",
                    f"A chat key already exists for '{project}'.\nRegenerate?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

            pub_key, fingerprint = chat_crypto.generate_keypair(project, force=True)
            show_information(
                self, "Success",
                f"Chat key generated for '{project}'!\n\nFingerprint: {fingerprint}\n\n"
                "Run Team Sync to share your public key with teammates."
            )
        except Exception as e:
            show_warning(self, "Error", f"Failed to generate key: {e}")

    def init_set_control_for_project(self, project: str):
        """Initialize set-control branch for the given project"""
        if not project:
            show_warning(self, "Error", "No project specified")
            return

        try:
            result = subprocess.run(
                [str(SCRIPT_DIR / "set-control-init"), "-p", project],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                show_information(self, "Success", f"set-control initialized for '{project}'")
                # Trigger team sync
                self.team_worker.start()
            else:
                error = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                show_warning(self, "Error", f"Failed to initialize set-control:\n{error}")
        except subprocess.TimeoutExpired:
            show_warning(self, "Error", "Initialization timed out")
        except Exception as e:
            show_warning(self, "Error", f"Failed to initialize: {e}")

    def _write_team_status_cache(self, data: dict):
        """Write team status to cache file for MCP server access.

        Schema:
        {
            "members": [
                {
                    "member": "user@host",
                    "member_full": "User Name",
                    "agent_status": "running|waiting|idle",
                    "change_id": "feature-xyz",
                    "project": "myproject",
                    "broadcast": "Working on X",
                    "last_seen": "2026-01-29T10:00:00"
                }
            ],
            "updated_at": "2026-01-29T10:00:00"
        }
        """
        try:
            # Ensure cache directory exists
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

            # Build simplified team status for MCP
            members = []
            my_name = data.get("my_name", "")

            for member in data.get("members", []):
                member_name = member.get("name", "")
                if member_name == my_name:
                    continue  # Skip self

                member_user = member.get("user", member_name.split("@")[0])
                member_hostname = member.get("hostname", "")
                if not member_hostname and "@" in member_name:
                    member_hostname = member_name.split("@")[1]
                display_name = member.get("display_name") or member_name

                for change in member.get("changes", []):
                    activity = change.get("activity") or {}
                    members.append({
                        "member": f"{member_user}@{member_hostname}" if member_hostname else member_user,
                        "member_full": display_name,
                        "agent_status": change.get("agent_status", "idle"),
                        "change_id": change.get("id", "?"),
                        "project": change.get("project", ""),
                        "broadcast": activity.get("broadcast"),
                        "activity": activity if activity else None,
                        "last_seen": member.get("last_seen", "")
                    })

            from datetime import datetime
            cache_data = {
                "members": members,
                "updated_at": datetime.now().isoformat()
            }

            cache_file = CACHE_DIR / "team_status.json"
            cache_file.write_text(json.dumps(cache_data, indent=2))
        except Exception:
            # Silently ignore cache write errors
            pass
