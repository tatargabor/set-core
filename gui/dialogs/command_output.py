"""
Command Output Dialog - Show command execution and output
"""

import logging
import os
import subprocess

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QApplication
)
from PySide6.QtCore import Qt, QTimer

__all__ = ["CommandOutputDialog"]

logger = logging.getLogger("set-control.dialogs")


class CommandOutputDialog(QDialog):
    """Dialog for showing command execution and output"""

    def __init__(self, parent, title: str, cmd: list, cwd: str = None):
        super().__init__(parent)
        self.cmd = cmd
        self.cwd = cwd
        self.process = None

        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        self.setWindowFlags(
            Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint |
            Qt.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)

        # Command label with copy button
        self.cmd_str = " ".join(str(c) for c in cmd)
        cmd_layout = QHBoxLayout()
        cmd_label = QLabel(f"<b>$</b> {self.cmd_str}")
        cmd_label.setWordWrap(True)
        # Get colors from parent if available
        if hasattr(parent, 'get_color'):
            cmd_bg = parent.get_color("bg_dialog")
            cmd_text = parent.get_color("row_idle_text")
            cmd_label.setStyleSheet(f"font-family: monospace; background: {cmd_bg}; color: {cmd_text}; padding: 8px; border: 1px solid {parent.get_color('border')};")
        else:
            cmd_label.setStyleSheet("font-family: monospace; background: #f0f0f0; padding: 8px;")
        cmd_layout.addWidget(cmd_label, 1)
        copy_btn = QPushButton("📋")
        copy_btn.setFixedWidth(32)
        copy_btn.setToolTip("Copy command to clipboard")
        copy_btn.clicked.connect(self.copy_command)
        cmd_layout.addWidget(copy_btn)
        layout.addLayout(cmd_layout)

        # Output area
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet("font-family: monospace; font-size: 11px;")
        layout.addWidget(self.output)

        # Status label
        self.status_label = QLabel("Running...")
        layout.addWidget(self.status_label)

        # Close button - always enabled so user can close anytime
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.on_close)
        layout.addWidget(self.close_btn)

        # Start command execution
        QTimer.singleShot(100, self.run_command)

    def run_command(self):
        """Run the command and capture output"""
        logger.info("run_command: cmd=%s cwd=%s", self.cmd, self.cwd)
        try:
            self.process = subprocess.Popen(
                self.cmd,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            # Read output in chunks
            self.read_timer = QTimer(self)
            self.read_timer.timeout.connect(self.read_output)
            self.read_timer.start(100)

        except Exception as e:
            logger.error("run_command: failed — %s", e)
            self.output.append(f"Error: {e}")
            self.finish_with_error()

    def read_output(self):
        """Read available output from process"""
        if self.process is None:
            return

        # Check if process has finished
        retcode = self.process.poll()

        # Read any available output
        try:
            import select
            import fcntl
            if hasattr(select, 'select'):
                # Unix - use select for non-blocking read
                fd = self.process.stdout.fileno()
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                try:
                    data = self.process.stdout.read()
                    if data:
                        self.output.insertPlainText(data)
                        self.output.verticalScrollBar().setValue(
                            self.output.verticalScrollBar().maximum()
                        )
                except:
                    pass
        except:
            pass

        if retcode is not None:
            # Process finished - read remaining output
            self.read_timer.stop()
            try:
                if self.process.stdout:
                    remaining = self.process.stdout.read()
                    if remaining:
                        self.output.insertPlainText(remaining)
            except:
                pass

            if retcode == 0:
                logger.info("run_command: completed successfully cmd=%s", self.cmd)
                self.status_label.setText("✓ Completed successfully")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                logger.error("run_command: failed exit_code=%d cmd=%s", retcode, self.cmd)
                self.status_label.setText(f"✗ Failed (exit code {retcode})")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")

    def finish_with_error(self):
        """Handle error state"""
        self.status_label.setText("✗ Failed")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")

    def copy_command(self):
        """Copy command to clipboard"""
        QApplication.clipboard().setText(self.cmd_str)

    def on_close(self):
        """Handle close - stop process if still running"""
        if self.process and self.process.poll() is None:
            # Process still running - just close dialog, let it run in background
            pass
        if hasattr(self, 'read_timer'):
            self.read_timer.stop()
        self.accept()
