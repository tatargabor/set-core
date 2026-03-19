"""
Work Dialog - Select worktree to open
"""

import json
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QListWidget, QListWidgetItem,
    QDialogButtonBox, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from ..constants import SCRIPT_DIR

__all__ = ["WorkDialog"]


class WorkDialog(QDialog):
    """Dialog to select which worktree to open"""

    def __init__(self, parent, open_worktrees: list):
        super().__init__(parent)
        self.setWindowTitle("Open Worktree")
        self.setMinimumSize(400, 300)
        # Ensure dialog has proper window decorations, resizable, stays on top
        self.setWindowFlags(
            Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint |
            Qt.WindowMinMaxButtonsHint | Qt.WindowStaysOnTopHint
        )
        self.selected_item = None
        self.open_worktrees = set(open_worktrees)  # Set of "project:change_id"

        layout = QVBoxLayout(self)

        # Tabs for local vs remote
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Local worktrees tab
        self.local_list = QListWidget()
        self.local_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabs.addTab(self.local_list, "Local Worktrees")

        # Remote branches tab
        self.remote_list = QListWidget()
        self.remote_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabs.addTab(self.remote_list, "Remote Branches")

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Load data
        self.load_local_worktrees()
        self.load_remote_branches()

    def load_local_worktrees(self):
        """Load local worktrees from set-list --all"""
        try:
            result = subprocess.run(
                [str(SCRIPT_DIR / "set-list"), "--all"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                current_path = None
                current_project = None
                current_change_id = None
                items = []  # Collect items for sorting

                for line in result.stdout.strip().split('\n'):
                    line_stripped = line.strip()
                    if not line_stripped or line_stripped.endswith(':'):
                        continue

                    # Parse "project / worktree-name" format (has leading spaces)
                    if ' / ' in line_stripped and not line_stripped.startswith('Path:') and not line_stripped.startswith('Branch:'):
                        parts = line_stripped.split(' / ', 1)
                        current_project = parts[0].strip()
                        rest = parts[1].strip()
                        if '-wt-' in rest:
                            current_change_id = rest.split('-wt-', 1)[1].split()[0]
                        else:
                            current_change_id = rest.split()[0]
                        current_path = None

                    elif line_stripped.startswith('Path:'):
                        current_path = line_stripped.replace('Path:', '').strip()

                    elif line_stripped.startswith('Branch:') and current_project and current_change_id:
                        # Get timestamp and formatted date
                        timestamp, last_modified = self.get_last_modified_info(current_path) if current_path else (0, "")
                        items.append({
                            "project": current_project,
                            "change_id": current_change_id,
                            "timestamp": timestamp,
                            "last_modified": last_modified
                        })

                # Sort by timestamp (most recent first)
                items.sort(key=lambda x: x["timestamp"], reverse=True)

                # Add items to list
                for item_data in items:
                    key = f"{item_data['project']}:{item_data['change_id']}"
                    display = f"{item_data['project']} / {item_data['change_id']}"
                    if item_data['last_modified']:
                        display += f"  ({item_data['last_modified']})"

                    item = QListWidgetItem(display)
                    item.setData(Qt.UserRole, {"project": item_data['project'], "change_id": item_data['change_id']})
                    if key in self.open_worktrees:
                        item.setForeground(QColor("#6b7280"))
                        item.setText(f"{item_data['project']} / {item_data['change_id']} (already open)")
                        item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    self.local_list.addItem(item)
        except Exception as e:
            self.local_list.addItem(f"Error: {e}")

    def get_last_modified_info(self, path: str) -> tuple:
        """Get last commit timestamp and relative date for a git repo path"""
        try:
            result = subprocess.run(
                ["git", "-C", path, "log", "-1", "--format=%ct|%cr"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split('|')
                timestamp = int(parts[0]) if parts[0] else 0
                relative = parts[1] if len(parts) > 1 else ""
                return (timestamp, relative)
        except:
            pass
        return (0, "")

    def load_remote_branches(self):
        """Load remote change branches from set-list --remote --all"""
        try:
            result = subprocess.run(
                [str(SCRIPT_DIR / "set-list"), "--remote", "--all"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                current_project = None
                current_change_id = None
                current_branch = None
                items = []  # Collect items for sorting

                for line in result.stdout.strip().split('\n'):
                    line_stripped = line.strip()
                    if not line_stripped or line_stripped.endswith(':'):
                        continue

                    # Parse "project / change_id (remote only)" format
                    if ' / ' in line_stripped and not line_stripped.startswith('Branch:'):
                        parts = line_stripped.split(' / ', 1)
                        current_project = parts[0].strip()
                        rest = parts[1].strip()
                        current_change_id = rest.replace('(remote only)', '').strip()
                        current_branch = None

                    elif line_stripped.startswith('Branch:') and current_project and current_change_id:
                        current_branch = line_stripped.replace('Branch:', '').strip()
                        # Get timestamp and formatted date from remote branch
                        timestamp, last_modified = self.get_remote_branch_info(current_project, current_branch)
                        items.append({
                            "project": current_project,
                            "change_id": current_change_id,
                            "timestamp": timestamp,
                            "last_modified": last_modified
                        })

                # Sort by timestamp (most recent first)
                items.sort(key=lambda x: x["timestamp"], reverse=True)

                # Add items to list
                for item_data in items:
                    key = f"{item_data['project']}:{item_data['change_id']}"
                    display = f"{item_data['project']} / {item_data['change_id']}"
                    if item_data['last_modified']:
                        display += f"  ({item_data['last_modified']})"

                    item = QListWidgetItem(display)
                    item.setData(Qt.UserRole, {"project": item_data['project'], "change_id": item_data['change_id']})
                    if key in self.open_worktrees:
                        item.setForeground(QColor("#6b7280"))
                        item.setText(f"{item_data['project']} / {item_data['change_id']} (already open)")
                        item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    self.remote_list.addItem(item)

            if self.remote_list.count() == 0:
                self.remote_list.addItem("No remote change/* branches found")
        except Exception as e:
            self.remote_list.addItem(f"Error: {e}")

    def get_remote_branch_info(self, project: str, branch: str) -> tuple:
        """Get last commit timestamp and relative date for a remote branch"""
        try:
            # Try to find project path from ~/.config/set-core/projects.json
            config_path = Path.home() / ".config" / "set-core" / "projects.json"
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
                    path = config.get("projects", {}).get(project, {}).get("path")
                    if path:
                        result = subprocess.run(
                            ["git", "-C", path, "log", "-1", "--format=%ct|%cr", branch],
                            capture_output=True, text=True, timeout=5
                        )
                        if result.returncode == 0:
                            parts = result.stdout.strip().split('|')
                            timestamp = int(parts[0]) if parts[0] else 0
                            relative = parts[1] if len(parts) > 1 else ""
                            return (timestamp, relative)
        except:
            pass
        return (0, "")

    def get_selection(self):
        """Get selected worktree data"""
        current_list = self.local_list if self.tabs.currentIndex() == 0 else self.remote_list
        item = current_list.currentItem()
        if item and item.flags() & Qt.ItemIsEnabled:
            return item.data(Qt.UserRole)
        return None
