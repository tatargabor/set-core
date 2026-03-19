#!/usr/bin/env python3
"""
SET Control Center - Entry Point

A GUI tool for managing git worktrees with Claude AI integration.

This file was refactored from a 4880 line monolithic file into a modular structure:
- gui/constants.py: Colors, paths, default configuration
- gui/config.py: Configuration manager
- gui/utils.py: Utility functions
- gui/widgets/: Custom widgets
- gui/dialogs/: Dialog windows (10 dialogs)
- gui/workers/: Background workers (4 workers)
- gui/control_center/: Main window with mixins
"""

import fcntl
import os
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

# Import from modular structure
# Add gui package to path when run as script
if __name__ == "__main__" or __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from gui.control_center import ControlCenter
else:
    from .control_center import ControlCenter

LOCK_FILE = Path("/tmp/set-control-gui.lock")
PID_FILE = Path("/tmp/set-control-gui.pid")


def kill_existing_instance():
    """Kill any existing instance of the GUI"""
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, 15)  # SIGTERM
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        PID_FILE.unlink(missing_ok=True)


def acquire_lock():
    """Try to acquire single instance lock, returns lock file or None"""
    lock_fd = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        PID_FILE.write_text(str(os.getpid()))
        return lock_fd
    except BlockingIOError:
        lock_fd.close()
        return None


def main():
    """Main entry point"""
    # Initialize logging before anything else
    from gui.logging_setup import setup_logging
    setup_logging()

    # Kill existing instance (for development reload)
    kill_existing_instance()

    app = QApplication(sys.argv)
    app.setApplicationName("WT Control")
    app.setApplicationDisplayName("WT Control")
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray

    # Set application icon
    icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Acquire single instance lock
    lock = acquire_lock()
    if lock is None:
        QMessageBox.warning(None, "Already Running",
                          "SET Control Center is already running.")
        sys.exit(1)

    window = ControlCenter()
    window.show()

    result = app.exec()

    # Cleanup
    PID_FILE.unlink(missing_ok=True)
    lock.close()
    LOCK_FILE.unlink(missing_ok=True)

    sys.exit(result)


if __name__ == "__main__":
    main()
