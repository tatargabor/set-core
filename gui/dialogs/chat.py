"""
Chat Dialog - Encrypted team chat
"""

import json
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt, QTimer

from ..constants import SCRIPT_DIR
from ..config import Config
from .helpers import show_warning

__all__ = ["ChatDialog"]


class ChatDialog(QDialog):
    """Dialog for encrypted team chat"""

    def __init__(self, parent, config: Config, team_data: dict, current_project: str):
        super().__init__(parent)
        self.config = config
        self.team_data = team_data
        self.current_project = current_project
        self.messages = []
        self.member_data = {}  # Stores full member info including shared_projects

        self.setWindowTitle("Team Chat")
        self.setMinimumSize(500, 400)
        self.setWindowFlags(
            Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint |
            Qt.WindowStaysOnTopHint
        )

        self.setup_ui()
        self.load_messages()

        # Auto-refresh timer (every 5 seconds)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.load_messages)
        self.refresh_timer.start(5000)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Recipient dropdown with refresh button
        recipient_layout = QHBoxLayout()
        recipient_layout.addWidget(QLabel("To:"))
        self.recipient_combo = QComboBox()
        self.recipient_combo.setMinimumWidth(200)
        recipient_layout.addWidget(self.recipient_combo, 1)
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setFixedWidth(30)
        self.refresh_btn.setToolTip("Refresh messages")
        self.refresh_btn.clicked.connect(self.load_messages)
        recipient_layout.addWidget(self.refresh_btn)
        layout.addLayout(recipient_layout)

        # Message history
        self.message_list = QTextEdit()
        self.message_list.setReadOnly(True)
        self.message_list.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.message_list, 1)

        # Message input
        input_layout = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type a message...")
        self.message_input.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.message_input, 1)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_btn)
        layout.addLayout(input_layout)

        # Encryption indicator
        crypto_label = QLabel("End-to-end encrypted")
        crypto_label.setStyleSheet("color: #22c55e; font-size: 10px;")
        layout.addWidget(crypto_label)

        # Load recipients AFTER send_btn is created
        self.load_recipients()
        self.recipient_combo.currentTextChanged.connect(self.load_messages)

    def load_recipients(self):
        """Load team members with chat keys"""
        self.recipient_combo.clear()
        self.member_data = {}  # Store full member data for lookup
        members = self.team_data.get("members", [])
        my_name = self.team_data.get("my_name", "")

        for member in members:
            if member.get("name") != my_name and member.get("chat_public_key"):
                display = member.get("display_name") or member.get("name")
                name = member.get("name")
                self.recipient_combo.addItem(display, name)
                self.member_data[name] = member  # Store for later lookup

        if self.recipient_combo.count() == 0:
            # Show more helpful message based on whether there are any other members
            other_members = [m for m in members if m.get("name") != my_name]
            if not other_members:
                self.recipient_combo.addItem("No team members found")
            else:
                # There are members but none have chat keys - show full name with hostname
                member_names = ", ".join(m.get("display_name", m.get("name", "?")) for m in other_members[:2])
                if len(other_members) > 2:
                    member_names += f" +{len(other_members) - 2}"
                self.recipient_combo.addItem(f"Waiting for keys: {member_names}")
            self.send_btn.setEnabled(False)
            self.message_input.setEnabled(False)

    def load_messages(self):
        """Load and display messages for current recipient"""
        recipient = self.recipient_combo.currentData()
        if not recipient:
            return

        # Get the correct project path for this recipient
        project_path = self._get_project_for_recipient(recipient)
        if not project_path:
            return

        try:
            result = subprocess.run(
                [str(SCRIPT_DIR / "set-control-chat"), "--path", project_path, "--json", "read"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                all_messages = json.loads(result.stdout)
                # Filter for this conversation - use flexible matching
                # (handles name changes like 'andrás' -> 'andrs')
                my_name = self.team_data.get("my_name", "")
                my_host = my_name.split("@")[-1] if "@" in my_name else my_name

                def is_me(name):
                    """Check if name refers to me (flexible match by hostname)"""
                    if name == my_name:
                        return True
                    if "@" in name and name.split("@")[-1] == my_host:
                        return True
                    return False

                self.messages = [
                    m for m in all_messages
                    if (is_me(m.get("from", "")) and m.get("to") == recipient) or
                       (m.get("from") == recipient and is_me(m.get("to", "")))
                ]
                self.display_messages()

                # Mark as read
                try:
                    import sys
                    gui_dir = Path(__file__).parent.parent
                    if str(gui_dir) not in sys.path:
                        sys.path.insert(0, str(gui_dir))

                    import chat_crypto
                    if self.messages:
                        last_msg = self.messages[-1]
                        state = chat_crypto.ChatReadState()
                        state.mark_read(self.current_project, last_msg.get("id", ""), last_msg.get("ts", ""))
                except ImportError:
                    pass
        except Exception as e:
            self.message_list.setPlainText(f"Error loading messages: {e}")

    def display_messages(self):
        """Display messages in the list"""
        my_name = self.team_data.get("my_name", "")
        lines = []
        for msg in self.messages:
            ts = msg.get("ts", "")[:19].replace("T", " ")
            sender = "Me" if msg.get("from") == my_name else msg.get("from", "?").split("@")[0]
            text = msg.get("text", "[encrypted]")
            lines.append(f"[{ts}] {sender}: {text}")

        self.message_list.setPlainText("\n".join(lines))
        # Scroll to bottom
        scrollbar = self.message_list.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _get_project_for_recipient(self, recipient: str) -> str:
        """Get the project path to use for chatting with this recipient"""
        member = self.member_data.get(recipient, {})
        shared_projects = member.get("shared_projects", [])
        if shared_projects:
            return shared_projects[0]

        # Fallback: find any project with set-control where this member exists
        try:
            result = subprocess.run(
                [str(SCRIPT_DIR / "set-status"), "--json"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                from ..utils import get_main_repo_path
                data = json.loads(result.stdout)
                seen_repos = set()
                for wt in data.get("worktrees", []):
                    wt_path = wt.get("path", "")
                    main_path = get_main_repo_path(wt_path)
                    if main_path and main_path not in seen_repos:
                        seen_repos.add(main_path)
                        control_path = Path(main_path) / ".set-control"
                        if control_path.exists():
                            # Check if recipient exists in this project's members
                            members_dir = control_path / "members"
                            for member_file in members_dir.glob("*.json"):
                                try:
                                    with open(member_file) as f:
                                        m = json.load(f)
                                        if m.get("name") == recipient:
                                            return main_path
                                except Exception:
                                    pass
        except Exception:
            pass

        return None

    def send_message(self):
        """Send a message to the selected recipient"""
        recipient = self.recipient_combo.currentData()
        message = self.message_input.text().strip()

        if not recipient or not message:
            return

        # Get the correct project path for this recipient
        project_path = self._get_project_for_recipient(recipient)
        if not project_path:
            show_warning(self, "Send Failed", "No shared project found with recipient")
            return

        try:
            cmd = [str(SCRIPT_DIR / "set-control-chat"), "--path", project_path, "send", recipient, message]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                self.message_input.clear()
                self.load_messages()
            else:
                show_warning(self, "Send Failed", result.stderr or result.stdout or "Unknown error")
        except Exception as e:
            show_warning(self, "Send Failed", str(e))
