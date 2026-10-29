"""
Chat Worker - Background thread for chat message polling
"""

import json
import logging
import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ..constants import SCRIPT_DIR, CONFIG_DIR
from ..config import Config

__all__ = ["ChatWorker"]

logger = logging.getLogger("set-control.workers.chat")


class ChatWorker(QThread):
    """Background thread for chat message polling"""
    messages_updated = Signal(list)
    unread_count_changed = Signal(int)
    error_occurred = Signal(str)

    def __init__(self, config: Config):
        super().__init__()
        self._running = True
        self.config = config
        self.last_check_ts = None
        self.current_project = None
        self.current_remote_url = ""

    def set_project(self, project_name: str, remote_url: str = ""):
        """Set current project for chat.

        `remote_url` is the key the team settings are stored under (see
        `TeamSettingsDialog`), while the project name is what the chat CLI
        and projects.json are addressed by. They are different strings, so
        both are needed.
        """
        self.current_project = project_name
        self.current_remote_url = remote_url

    def run(self):
        while self._running:
            # Check if current project has team enabled
            if not self.current_project:
                self.msleep(5000)
                continue
            projects = self.config.team.get("projects", {})
            # The team settings are keyed by the project's remote URL, not by
            # its name -- TeamSettingsDialog writes team["projects"][remote_url]
            # and TeamMixin reads them back the same way. Looking the flag up
            # by name never finds it, and the poll loop below never starts.
            team_key = self.current_remote_url or self.current_project
            project_enabled = projects.get(team_key, {}).get("enabled", False)
            if not project_enabled:
                self.msleep(5000)
                continue

            try:
                # Get project path
                config_path = CONFIG_DIR / "projects.json"
                if not config_path.exists():
                    self.msleep(5000)
                    continue

                with open(config_path) as f:
                    projects_config = json.load(f)

                project_path = projects_config.get("projects", {}).get(self.current_project, {}).get("path")
                if not project_path:
                    self.msleep(5000)
                    continue

                control_worktree = Path(project_path) / ".set-control"
                if not control_worktree.exists():
                    self.msleep(5000)
                    continue

                # Pull latest
                subprocess.run(
                    ["git", "-C", str(control_worktree), "pull", "--rebase", "origin", "set-control"],
                    capture_output=True, text=True, timeout=15
                )

                # Read messages
                messages_file = control_worktree / "chat" / "messages.jsonl"
                if messages_file.exists():
                    result = subprocess.run(
                        [str(SCRIPT_DIR / "set-control-chat"), "-p", self.current_project, "--json", "read"],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        try:
                            messages = json.loads(result.stdout)
                            self.messages_updated.emit(messages)

                            # Count unread
                            try:
                                import sys
                                gui_dir = Path(__file__).parent.parent
                                if str(gui_dir) not in sys.path:
                                    sys.path.insert(0, str(gui_dir))

                                import chat_crypto
                                state = chat_crypto.ChatReadState()
                                last_ts = state.get_last_read_ts(self.current_project)
                                unread = sum(1 for m in messages if not last_ts or m.get("ts", "") > last_ts)
                                self.unread_count_changed.emit(unread)
                            except ImportError:
                                pass
                        except json.JSONDecodeError:
                            pass

            except subprocess.TimeoutExpired:
                logger.error("chat poll timed out")
            except Exception as e:
                logger.error("chat poll error: %s", e)
                self.error_occurred.emit(str(e))

            # Poll every 10 seconds
            self.msleep(10000)

    def stop(self):
        self._running = False
