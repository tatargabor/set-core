"""
Team Worker - Background thread for team synchronization via set-control
"""

import json
import logging
import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ..constants import SCRIPT_DIR, CONFIG_DIR
from ..config import Config

__all__ = ["TeamWorker"]

logger = logging.getLogger("set-control.workers.team")


class TeamWorker(QThread):
    """Background thread for team synchronization via set-control"""
    team_updated = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, config: Config):
        super().__init__()
        self._running = True
        self.config = config

    def _normalize_url(self, url: str) -> str:
        """Normalize git URL for comparison (strip .git suffix)"""
        return url.rstrip(".git") if url else ""

    def _get_main_repo_path(self, worktree_path: str) -> str:
        """Get the main repo path from a worktree path using git worktree list"""
        try:
            result = subprocess.run(
                ["git", "-C", worktree_path, "worktree", "list", "--porcelain"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # First "worktree" line is the main repo
                for line in result.stdout.split("\n"):
                    if line.startswith("worktree "):
                        return line[9:]  # Remove "worktree " prefix
        except Exception:
            pass
        return ""

    def _get_enabled_project_paths(self) -> list:
        """Get list of project paths that have team enabled.

        Discovers project paths from set-status worktrees instead of relying
        solely on projects.json, which may not contain all projects.
        """
        # Collect enabled URLs (normalize for comparison)
        enabled_urls = set()
        for url, settings in self.config.team.get("projects", {}).items():
            if settings.get("enabled", False):
                enabled_urls.add(self._normalize_url(url))

        if not enabled_urls:
            return []

        # Get all worktrees from set-status
        try:
            result = subprocess.run(
                [str(SCRIPT_DIR / "set-status"), "--json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return []

            worktrees = json.loads(result.stdout).get("worktrees", [])
        except Exception:
            return []

        # Build mapping of remote_url -> main repo path
        project_paths = {}
        for wt in worktrees:
            remote_url = self._normalize_url(wt.get("remote_url", ""))
            wt_path = wt.get("path", "")

            if not remote_url or not wt_path or remote_url in project_paths:
                continue

            if remote_url not in enabled_urls:
                continue

            # Find main repo path from this worktree
            main_path = self._get_main_repo_path(wt_path)
            if not main_path:
                continue

            main_path = Path(main_path)
            if not main_path.exists():
                continue

            # Check if .set-control exists (or can be auto-initialized)
            if (main_path / ".set-control").exists():
                project_paths[remote_url] = str(main_path)

        return list(project_paths.values())

    def run(self):
        while self._running:
            # Check if ANY project has team enabled
            projects = self.config.team.get("projects", {})
            any_enabled = any(p.get("enabled", False) for p in projects.values())
            if not any_enabled:
                self.msleep(5000)  # Check less frequently when disabled
                continue

            try:
                # Get all project paths with team enabled
                project_paths = self._get_enabled_project_paths()

                all_members = []
                all_conflicts = []
                my_name = ""

                # Sync each project
                for project_path in project_paths:
                    sync_result = subprocess.run(
                        [str(SCRIPT_DIR / "set-control-sync"), "--full", "--json"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        cwd=project_path
                    )

                    if sync_result.returncode == 0:
                        try:
                            # Extract JSON from output (may have git messages before it)
                            output = sync_result.stdout
                            json_start = output.find('{')
                            if json_start < 0:
                                continue
                            data = json.loads(output[json_start:])
                            if not my_name:
                                my_name = data.get("my_name", "")
                            # Merge members - combine changes from all projects
                            existing_by_name = {m.get("name"): m for m in all_members}
                            for member in data.get("members", []):
                                member_name = member.get("name")
                                if member_name in existing_by_name:
                                    # Merge changes into existing member
                                    existing_member = existing_by_name[member_name]
                                    existing_changes = {(c.get("id"), c.get("remote_url")) for c in existing_member.get("changes", [])}
                                    for change in member.get("changes", []):
                                        change_key = (change.get("id"), change.get("remote_url"))
                                        if change_key not in existing_changes:
                                            existing_member.setdefault("changes", []).append(change)
                                            existing_changes.add(change_key)
                                    # Add this project path to shared projects list
                                    existing_member.setdefault("shared_projects", [])
                                    if project_path not in existing_member["shared_projects"]:
                                        existing_member["shared_projects"].append(project_path)
                                else:
                                    # Track which project this member came from (for chat)
                                    member["shared_projects"] = [project_path]
                                    all_members.append(member)
                                    existing_by_name[member_name] = member
                            all_conflicts.extend(data.get("conflicts", []))
                        except json.JSONDecodeError:
                            pass

                # Emit merged result
                self.team_updated.emit({
                    "my_name": my_name,
                    "members": all_members,
                    "conflicts": all_conflicts,
                    "initialized": len(project_paths) > 0
                })

            except subprocess.TimeoutExpired:
                logger.error("team sync timed out")
                self.error_occurred.emit("Team sync timed out")
            except FileNotFoundError:
                logger.error("set-control-sync not found")
                self.error_occurred.emit("set-control-sync not found")
            except json.JSONDecodeError as e:
                logger.error("team sync invalid JSON: %s", e)
                self.error_occurred.emit(f"Invalid team JSON: {e}")
            except Exception as e:
                logger.error("team sync error: %s", e)
                self.error_occurred.emit(str(e))

            # Sleep for configured interval
            interval = self.config.team.get("sync_interval_ms", 30000)
            self.msleep(interval)

    def stop(self):
        self._running = False

    def trigger_sync(self):
        """Trigger an immediate sync (called from manual refresh)"""
        # This would require a more complex implementation with events
        # For now, just let the regular polling handle it
        pass
