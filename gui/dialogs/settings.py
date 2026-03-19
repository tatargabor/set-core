"""
Settings Dialog - Tabbed settings configuration
"""

import json
import shutil
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QSlider, QSpinBox, QLineEdit, QCheckBox, QComboBox,
    QGroupBox, QDialogButtonBox, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt

from ..config import Config
from ..constants import CONFIG_DIR

__all__ = ["SettingsDialog"]


class SettingsDialog(QDialog):
    """Settings dialog with tabs for different config sections"""

    def __init__(self, parent, config: Config, active_project: str = None):
        super().__init__(parent)
        self.config = config
        self.active_project = active_project
        self.setWindowTitle("Settings")
        self.setMinimumSize(450, 350)
        self.setWindowFlags(
            Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint |
            Qt.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)

        # Tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Create tabs
        self._create_control_center_tab()
        self._create_editor_tab()
        self._create_team_global_tab()  # Global team settings (sync interval only)
        self._create_ralph_tab()
        self._create_git_tab()
        self._create_notifications_tab()

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self.apply_settings)
        layout.addWidget(buttons)

        self._load_current_values()

    def _create_control_center_tab(self):
        """Create Control Center settings tab"""
        tab = QWidget()
        layout = QFormLayout(tab)

        # Opacity default
        self.opacity_default = QSlider(Qt.Horizontal)
        self.opacity_default.setRange(10, 100)
        self.opacity_default.setTickInterval(10)
        self.opacity_default_label = QLabel("50%")
        self.opacity_default.valueChanged.connect(
            lambda v: self.opacity_default_label.setText(f"{v}%")
        )
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(self.opacity_default)
        opacity_layout.addWidget(self.opacity_default_label)
        layout.addRow("Default Opacity:", opacity_layout)

        # Opacity hover
        self.opacity_hover = QSlider(Qt.Horizontal)
        self.opacity_hover.setRange(10, 100)
        self.opacity_hover.setTickInterval(10)
        self.opacity_hover_label = QLabel("100%")
        self.opacity_hover.valueChanged.connect(
            lambda v: self.opacity_hover_label.setText(f"{v}%")
        )
        hover_layout = QHBoxLayout()
        hover_layout.addWidget(self.opacity_hover)
        hover_layout.addWidget(self.opacity_hover_label)
        layout.addRow("Hover Opacity:", hover_layout)

        # Window width
        self.window_width = QSpinBox()
        self.window_width.setRange(300, 800)
        self.window_width.setSuffix(" px")
        layout.addRow("Window Width:", self.window_width)

        # Refresh interval
        self.refresh_interval = QSpinBox()
        self.refresh_interval.setRange(500, 10000)
        self.refresh_interval.setSingleStep(500)
        self.refresh_interval.setSuffix(" ms")
        layout.addRow("Refresh Interval:", self.refresh_interval)

        # Blink interval
        self.blink_interval = QSpinBox()
        self.blink_interval.setRange(100, 2000)
        self.blink_interval.setSingleStep(100)
        self.blink_interval.setSuffix(" ms")
        layout.addRow("Blink Interval:", self.blink_interval)

        # Color profile
        self.color_profile = QComboBox()
        self.color_profile.addItems(["light", "gray", "dark", "high_contrast"])
        layout.addRow("Color Profile:", self.color_profile)

        self.tabs.addTab(tab, "Control Center")

    def _create_editor_tab(self):
        """Create Editor & Permission settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Editor Selection
        editor_group = QGroupBox("Editor")
        editor_layout = QFormLayout(editor_group)

        self.editor_combo = QComboBox()
        self.editor_combo.addItem("auto (detect at runtime)", "auto")

        # IDE group
        ide_editors = [
            ("zed", "Zed"),
            ("vscode", "VS Code"),
            ("cursor", "Cursor"),
            ("windsurf", "Windsurf"),
        ]
        terminal_editors = [
            ("kitty", "kitty"),
            ("alacritty", "Alacritty"),
            ("wezterm", "WezTerm"),
            ("gnome-terminal", "GNOME Terminal"),
            ("konsole", "Konsole"),
            ("iterm2", "iTerm2"),
            ("terminal-app", "Terminal.app"),
        ]

        self.editor_combo.insertSeparator(self.editor_combo.count())
        for key, label in ide_editors:
            installed = shutil.which(key) is not None or self._check_editor_installed(key)
            display = f"{label} (IDE)" if installed else f"{label} (IDE) [not found]"
            self.editor_combo.addItem(display, key)
            if not installed:
                idx = self.editor_combo.count() - 1
                model = self.editor_combo.model()
                item = model.item(idx)
                item.setEnabled(False)

        self.editor_combo.insertSeparator(self.editor_combo.count())
        for key, label in terminal_editors:
            installed = shutil.which(key) is not None or self._check_editor_installed(key)
            display = f"{label} (Terminal)" if installed else f"{label} (Terminal) [not found]"
            self.editor_combo.addItem(display, key)
            if not installed:
                idx = self.editor_combo.count() - 1
                model = self.editor_combo.model()
                item = model.item(idx)
                item.setEnabled(False)

        editor_layout.addRow("Editor:", self.editor_combo)
        layout.addWidget(editor_group)

        # Permission Mode
        perm_group = QGroupBox("Claude Permission Mode")
        perm_layout = QVBoxLayout(perm_group)

        self.perm_button_group = QButtonGroup(self)
        self.perm_auto_accept = QRadioButton("auto-accept — Full autonomy (--dangerously-skip-permissions)")
        self.perm_allowed_tools = QRadioButton("allowedTools — Selective permissions (Edit, Write, Bash, etc.)")
        self.perm_plan = QRadioButton("plan — Interactive, approve each action")

        self.perm_button_group.addButton(self.perm_auto_accept, 0)
        self.perm_button_group.addButton(self.perm_allowed_tools, 1)
        self.perm_button_group.addButton(self.perm_plan, 2)

        perm_layout.addWidget(self.perm_auto_accept)
        perm_layout.addWidget(self.perm_allowed_tools)
        perm_layout.addWidget(self.perm_plan)
        layout.addWidget(perm_group)

        layout.addStretch()
        self.tabs.addTab(tab, "Editor")

    def _check_editor_installed(self, name: str) -> bool:
        """Check if an editor is installed (platform-specific)"""
        checks = {
            "zed": [Path.home() / ".local/bin/zed"],
            "vscode": [Path("/usr/bin/code"), Path("/snap/bin/code")],
            "cursor": [Path.home() / ".local/bin/cursor"],
            "iterm2": [Path("/Applications/iTerm.app")],
            "terminal-app": [Path("/Applications/Utilities/Terminal.app")],
        }
        for path in checks.get(name, []):
            if path.exists():
                return True
        return False

    def _create_team_global_tab(self):
        """Create global Team settings tab (sync interval only)"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info_label = QLabel("Global team sync settings. Project-specific settings\n"
                           "(enable/disable, chat key) are in Project → Team Settings.")
        info_label.setStyleSheet("color: #6b7280; font-style: italic;")
        layout.addWidget(info_label)

        layout.addSpacing(15)

        # Sync interval (global)
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Sync interval:"))
        self.team_sync_interval = QSpinBox()
        self.team_sync_interval.setRange(10000, 120000)
        self.team_sync_interval.setSingleStep(5000)
        self.team_sync_interval.setSuffix(" ms")
        self.team_sync_interval.setToolTip("How often to sync team status (applies to all projects)")
        interval_layout.addWidget(self.team_sync_interval)
        interval_layout.addStretch()
        layout.addLayout(interval_layout)

        layout.addStretch()
        self.tabs.addTab(tab, "Team")

    def _create_git_tab(self):
        """Create Git settings tab"""
        tab = QWidget()
        layout = QFormLayout(tab)

        self.git_branch_prefix = QLineEdit()
        self.git_branch_prefix.setPlaceholderText("change/")
        layout.addRow("Branch Prefix:", self.git_branch_prefix)

        self.git_fetch_timeout = QSpinBox()
        self.git_fetch_timeout.setRange(5, 120)
        self.git_fetch_timeout.setSuffix(" s")
        layout.addRow("Fetch Timeout:", self.git_fetch_timeout)

        self.tabs.addTab(tab, "Git")

    def _create_ralph_tab(self):
        """Create Ralph Loop settings tab"""
        tab = QWidget()
        layout = QFormLayout(tab)

        # Fullscreen terminal
        self.ralph_fullscreen = QCheckBox("Open terminal in fullscreen")
        layout.addRow("Terminal:", self.ralph_fullscreen)

        # Default max iterations
        self.ralph_max_iter = QSpinBox()
        self.ralph_max_iter.setRange(1, 50)
        self.ralph_max_iter.setValue(10)
        layout.addRow("Default max iterations:", self.ralph_max_iter)

        # Default stall threshold
        self.ralph_stall_threshold = QSpinBox()
        self.ralph_stall_threshold.setRange(1, 10)
        self.ralph_stall_threshold.setValue(2)
        layout.addRow("Default stall threshold:", self.ralph_stall_threshold)

        # Default iteration timeout
        self.ralph_iter_timeout = QSpinBox()
        self.ralph_iter_timeout.setRange(5, 120)
        self.ralph_iter_timeout.setSuffix(" min")
        self.ralph_iter_timeout.setValue(45)
        layout.addRow("Default iteration timeout:", self.ralph_iter_timeout)

        self.tabs.addTab(tab, "Ralph")

    def _create_notifications_tab(self):
        """Create Notifications settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.notif_enabled = QCheckBox("Enable desktop notifications")
        layout.addWidget(self.notif_enabled)

        self.notif_sound = QCheckBox("Play sound on notification")
        layout.addWidget(self.notif_sound)

        layout.addStretch()
        self.tabs.addTab(tab, "Notifications")

    def _load_current_values(self):
        """Load current config values into widgets"""
        cc = self.config.control_center
        self.opacity_default.setValue(int(cc["opacity_default"] * 100))
        self.opacity_hover.setValue(int(cc["opacity_hover"] * 100))
        self.window_width.setValue(cc["window_width"])
        self.refresh_interval.setValue(cc["refresh_interval_ms"])
        self.blink_interval.setValue(cc["blink_interval_ms"])
        profile = cc.get("color_profile", "light")
        idx = self.color_profile.findText(profile)
        if idx >= 0:
            self.color_profile.setCurrentIndex(idx)

        git = self.config.git
        self.git_branch_prefix.setText(git["branch_prefix"])
        self.git_fetch_timeout.setValue(git["fetch_timeout_s"])

        notif = self.config.notifications
        self.notif_enabled.setChecked(notif["enabled"])
        self.notif_sound.setChecked(notif["sound"])

        self.ralph_fullscreen.setChecked(self.config.get("ralph", "terminal_fullscreen", False))
        self.ralph_max_iter.setValue(self.config.get("ralph", "default_max_iterations", 10))
        self.ralph_stall_threshold.setValue(self.config.get("ralph", "default_stall_threshold", 2))
        self.ralph_iter_timeout.setValue(self.config.get("ralph", "default_iteration_timeout", 45))

        # Team settings (global only - sync interval)
        team = self.config.team
        self.team_sync_interval.setValue(team.get("sync_interval_ms", 30000))

        # Editor & Permission settings (from set-core config.json)
        self._load_editor_config()

    def apply_settings(self):
        """Apply settings to config"""
        self.config.set("control_center", "opacity_default", self.opacity_default.value() / 100.0)
        self.config.set("control_center", "opacity_hover", self.opacity_hover.value() / 100.0)
        self.config.set("control_center", "window_width", self.window_width.value())
        self.config.set("control_center", "refresh_interval_ms", self.refresh_interval.value())
        self.config.set("control_center", "blink_interval_ms", self.blink_interval.value())
        self.config.set("control_center", "color_profile", self.color_profile.currentText())

        self.config.set("git", "branch_prefix", self.git_branch_prefix.text())
        self.config.set("git", "fetch_timeout_s", self.git_fetch_timeout.value())

        self.config.set("notifications", "enabled", self.notif_enabled.isChecked())
        self.config.set("notifications", "sound", self.notif_sound.isChecked())

        self.config.set("ralph", "terminal_fullscreen", self.ralph_fullscreen.isChecked())
        self.config.set("ralph", "default_max_iterations", self.ralph_max_iter.value())
        self.config.set("ralph", "default_stall_threshold", self.ralph_stall_threshold.value())
        self.config.set("ralph", "default_iteration_timeout", self.ralph_iter_timeout.value())

        # Team settings (global only - sync interval)
        self.config.set("team", "sync_interval_ms", self.team_sync_interval.value())

        self.config.save()

        # Editor & Permission settings (to set-core config.json)
        self._save_editor_config()

        # Apply theme to parent window if it has the method
        if hasattr(self.parent(), 'apply_theme'):
            self.parent().apply_theme()

    def _get_wt_config_path(self) -> Path:
        """Get the set-core config.json path"""
        return CONFIG_DIR / "config.json"

    def _load_editor_config(self):
        """Load editor and permission settings from set-core config.json"""
        config_path = self._get_wt_config_path()
        editor_name = "auto"
        perm_mode = "auto-accept"
        try:
            if config_path.exists():
                with open(config_path) as f:
                    data = json.load(f)
                editor_name = data.get("editor", {}).get("name", "auto")
                perm_mode = data.get("claude", {}).get("permission_mode", "auto-accept")
        except Exception:
            pass

        # Set editor combo
        for i in range(self.editor_combo.count()):
            if self.editor_combo.itemData(i) == editor_name:
                self.editor_combo.setCurrentIndex(i)
                break

        # Set permission mode
        if perm_mode == "allowedTools":
            self.perm_allowed_tools.setChecked(True)
        elif perm_mode == "plan":
            self.perm_plan.setChecked(True)
        else:
            self.perm_auto_accept.setChecked(True)

    def _save_editor_config(self):
        """Save editor and permission settings to set-core config.json"""
        config_path = self._get_wt_config_path()
        data = {}
        try:
            if config_path.exists():
                with open(config_path) as f:
                    data = json.load(f)
        except Exception:
            pass

        # Editor
        editor_name = self.editor_combo.currentData()
        if editor_name:
            data.setdefault("editor", {})["name"] = editor_name

        # Permission mode
        if self.perm_allowed_tools.isChecked():
            perm_mode = "allowedTools"
        elif self.perm_plan.isChecked():
            perm_mode = "plan"
        else:
            perm_mode = "auto-accept"
        data.setdefault("claude", {})["permission_mode"] = perm_mode

        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def accept(self):
        """OK button - apply and close"""
        self.apply_settings()
        super().accept()
