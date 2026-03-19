"""
Worktree Config Dialog - View/edit worktree-specific config
"""

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTabWidget, QWidget, QDialogButtonBox, QMessageBox
)
from PySide6.QtCore import Qt

from .helpers import show_warning

__all__ = ["WorktreeConfigDialog"]


class WorktreeConfigDialog(QDialog):
    """Dialog for viewing/editing worktree-specific config"""

    def __init__(self, parent, wt_path: str, config_dir: Path):
        super().__init__(parent)
        self.wt_path = wt_path
        self.config_dir = config_dir
        self.config_editors = {}  # {config_file: {key: QLineEdit}}
        self.setWindowTitle(f"Worktree Config - {Path(wt_path).name}")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.setWindowFlags(
            Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint |
            Qt.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)

        # Path info
        path_label = QLabel(f"<b>Path:</b> {wt_path}")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        # Tabs for different config files
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Load config files
        self.load_configs()

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close)
        buttons.accepted.connect(self.save_configs)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load_configs(self):
        """Load and display config files from .set-core/"""
        if not self.config_dir.exists():
            label = QLabel("No .set-core/ config directory found.")
            self.tabs.addTab(label, "Info")
            return

        config_files = list(self.config_dir.glob("*.json"))
        if not config_files:
            label = QLabel("No config files found in .set-core/")
            self.tabs.addTab(label, "Info")
            return

        for config_file in sorted(config_files):
            try:
                with open(config_file) as f:
                    content = json.load(f)

                # Create a widget to display the config
                widget = QWidget()
                vlayout = QVBoxLayout(widget)
                self.config_editors[config_file] = {}

                # Display as editable key-value pairs
                for key, value in content.items():
                    row = QHBoxLayout()
                    key_label = QLabel(f"{key}:")
                    key_label.setMinimumWidth(120)
                    key_label.setStyleSheet("font-weight: bold;")

                    value_edit = QLineEdit()
                    value_edit.setText(str(value) if value else "")
                    value_edit.setPlaceholderText("<not set>")
                    self.config_editors[config_file][key] = value_edit

                    row.addWidget(key_label)
                    row.addWidget(value_edit, 1)
                    vlayout.addLayout(row)

                vlayout.addStretch()

                tab_name = config_file.stem.replace("-", " ").title()
                self.tabs.addTab(widget, tab_name)

            except Exception as e:
                error_label = QLabel(f"Error loading {config_file.name}: {e}")
                self.tabs.addTab(error_label, config_file.stem)

    def save_configs(self):
        """Save all edited config files"""
        for config_file, editors in self.config_editors.items():
            try:
                # Build new config from editors
                new_config = {}
                for key, editor in editors.items():
                    value = editor.text().strip()
                    new_config[key] = value if value else None

                # Write to file
                with open(config_file, "w") as f:
                    json.dump(new_config, f, indent=2)

            except Exception as e:
                show_warning(self, "Save Error", f"Failed to save {config_file.name}: {e}")
                return

        self.accept()
