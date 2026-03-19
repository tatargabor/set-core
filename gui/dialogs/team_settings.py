"""
Team Settings Dialog - Project-specific team settings
"""

import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QGroupBox, QDialogButtonBox, QMessageBox
)
from PySide6.QtCore import Qt

from ..constants import SCRIPT_DIR
from ..config import Config
from ..utils import get_main_repo_path
from .helpers import show_warning

__all__ = ["TeamSettingsDialog"]


class TeamSettingsDialog(QDialog):
    """Project-specific team settings dialog"""

    def __init__(self, parent, config: Config, project: str, remote_url: str = ""):
        super().__init__(parent)
        self.config = config
        self.project = project
        self.remote_url = remote_url  # Use remote_url as config key
        self.setWindowTitle(f"Team Settings - {project}")
        self.setMinimumSize(400, 350)
        self.setWindowFlags(
            Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint |
            Qt.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)

        # Project header
        header = QLabel(f"Project: {project}")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)
        layout.addSpacing(10)

        # Enable team sync (project-specific, stored by remote_url)
        self.team_enabled = QCheckBox("Enable team synchronization")
        self.team_enabled.setToolTip("Sync your status with team members via set-control branch")
        # Use remote_url as key for settings
        config_key = remote_url if remote_url else project
        proj_settings = config.team.get("projects", {}).get(config_key, {})
        self.team_enabled.setChecked(proj_settings.get("enabled", False))
        layout.addWidget(self.team_enabled)

        # Auto sync (project-specific)
        self.team_auto_sync = QCheckBox("Auto-sync in background")
        self.team_auto_sync.setToolTip("Automatically pull and push team status")
        self.team_auto_sync.setChecked(proj_settings.get("auto_sync", True))
        layout.addWidget(self.team_auto_sync)

        layout.addSpacing(10)

        # Initialize button
        self.init_btn = QPushButton("Initialize set-control branch")
        self.init_btn.setToolTip("Create the set-control branch if it doesn't exist")
        self.init_btn.clicked.connect(self._init_set_control)
        layout.addWidget(self.init_btn)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Check set-control status and update button
        self._check_wt_control_status()

        layout.addSpacing(15)

        # Chat encryption section
        chat_group = QGroupBox("Encrypted Chat")
        chat_layout = QVBoxLayout(chat_group)

        # Key status
        self.chat_key_label = QLabel("Checking key status...")
        chat_layout.addWidget(self.chat_key_label)

        # Key fingerprint
        self.chat_fingerprint_label = QLabel("")
        self.chat_fingerprint_label.setStyleSheet("font-family: monospace; color: #6b7280;")
        chat_layout.addWidget(self.chat_fingerprint_label)

        # Generate key button
        key_btn_layout = QHBoxLayout()
        self.generate_key_btn = QPushButton("Generate Chat Key")
        self.generate_key_btn.setToolTip("Generate a new encryption keypair for chat")
        self.generate_key_btn.clicked.connect(self._generate_chat_key)
        key_btn_layout.addWidget(self.generate_key_btn)
        key_btn_layout.addStretch()
        chat_layout.addLayout(key_btn_layout)

        layout.addWidget(chat_group)

        # Update key status
        self._update_chat_key_status()

        layout.addStretch()

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _check_wt_control_status(self):
        """Check if set-control is initialized and update UI accordingly"""
        try:
            # Get project path using set-status
            result = subprocess.run(
                [str(SCRIPT_DIR / "set-status"), "--json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return

            import json
            data = json.loads(result.stdout)
            for wt in data.get("worktrees", []):
                if wt.get("project") == self.project:
                    wt_path = wt.get("path", "")
                    main_repo = get_main_repo_path(wt_path)
                    if main_repo and Path(main_repo, ".set-control").exists():
                        self.init_btn.setText("set-control (initialized)")
                        self.init_btn.setEnabled(False)
                        self.status_label.setText(f"set-control active at {main_repo}/.set-control")
                        self.status_label.setStyleSheet("color: green;")
                    return
        except Exception:
            pass  # Silently fail - button remains enabled

    def _init_set_control(self):
        """Initialize set-control branch for the project"""
        self.status_label.setText("Initializing set-control...")
        self.status_label.setStyleSheet("")

        try:
            result = subprocess.run(
                [str(SCRIPT_DIR / "set-control-init"), "-p", self.project],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                self.status_label.setText("set-control initialized successfully!")
                self.status_label.setStyleSheet("color: green;")
                self.init_btn.setText("set-control (initialized)")
                self.init_btn.setEnabled(False)
            else:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                self.status_label.setText(f"Init failed: {error_msg}")
                self.status_label.setStyleSheet("color: red;")
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            self.status_label.setStyleSheet("color: red;")

    def _update_chat_key_status(self):
        """Update chat key status display"""
        try:
            import sys
            gui_dir = Path(__file__).parent.parent
            if str(gui_dir) not in sys.path:
                sys.path.insert(0, str(gui_dir))

            import chat_crypto
            if not chat_crypto.is_available():
                self.chat_key_label.setText("PyNaCl not installed - run: pip install PyNaCl")
                self.chat_fingerprint_label.setText("")
                self.generate_key_btn.setEnabled(False)
                return

            if chat_crypto.has_key(self.project):
                pub_key, fingerprint = chat_crypto.get_public_key(self.project)
                self.chat_key_label.setText(f"Chat key configured")
                self.chat_key_label.setStyleSheet("color: green;")
                self.chat_fingerprint_label.setText(f"Fingerprint: {fingerprint}")
                self.generate_key_btn.setText("Regenerate Key")
            else:
                self.chat_key_label.setText("No chat key - generate one to enable encrypted chat")
                self.chat_key_label.setStyleSheet("color: orange;")
                self.chat_fingerprint_label.setText("")
                self.generate_key_btn.setText("Generate Chat Key")
        except Exception as e:
            self.chat_key_label.setText(f"Error checking key: {e}")
            self.chat_key_label.setStyleSheet("color: red;")

    def _generate_chat_key(self):
        """Generate new chat encryption key and sync to share it"""
        try:
            import sys
            gui_dir = Path(__file__).parent.parent
            if str(gui_dir) not in sys.path:
                sys.path.insert(0, str(gui_dir))

            import chat_crypto
            chat_crypto.generate_keypair(self.project)
            self._update_chat_key_status()
            self.status_label.setText("Chat key generated! Syncing...")
            self.status_label.setStyleSheet("color: green;")

            # Auto-sync to share public key with team
            try:
                result = subprocess.run(
                    [str(SCRIPT_DIR / "set-control-sync"), "-p", self.project, "--full"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    self.status_label.setText("Chat key generated and synced!")
                else:
                    self.status_label.setText("Key generated but sync failed - will sync in background")
            except Exception:
                self.status_label.setText("Key generated - will sync in background")
        except Exception as e:
            self.status_label.setText(f"Key generation failed: {e}")
            self.status_label.setStyleSheet("color: red;")

    def _save_and_accept(self):
        """Save project-specific team settings and close (using remote_url as key)"""
        config_key = self.remote_url if self.remote_url else self.project
        if "projects" not in self.config.team:
            self.config.team["projects"] = {}
        if config_key not in self.config.team["projects"]:
            self.config.team["projects"][config_key] = {}

        enabling_team = self.team_enabled.isChecked()

        self.config.team["projects"][config_key]["enabled"] = enabling_team
        self.config.team["projects"][config_key]["auto_sync"] = self.team_auto_sync.isChecked()
        self.config.save()

        # Auto-initialize set-control when team is enabled (silently skip if already initialized)
        if enabling_team:
            self._auto_init_set_control()

        self.accept()

    def _auto_init_set_control(self):
        """Auto-initialize set-control branch when team is enabled"""
        try:
            # set-control-init will fetch from remote if branch exists, or create new
            result = subprocess.run(
                [str(SCRIPT_DIR / "set-control-init"), "-p", self.project],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                # Don't show error if already initialized
                if "already initialized" not in error_msg:
                    show_warning(
                        self, "set-control Init",
                        f"Could not auto-initialize set-control:\n{error_msg}\n\n"
                        "You can initialize manually from Project menu."
                    )
        except Exception as e:
            show_warning(
                self, "set-control Init",
                f"Error initializing set-control: {e}"
            )
