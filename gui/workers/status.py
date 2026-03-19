"""
Status Worker - Background thread for polling set-status
"""

import json
import logging
import subprocess

from PySide6.QtCore import QThread, Signal

from ..constants import SCRIPT_DIR
from ..config import Config

__all__ = ["StatusWorker"]

logger = logging.getLogger("set-control.workers.status")


class StatusWorker(QThread):
    """Background thread for polling set-status"""
    status_updated = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, config: Config):
        super().__init__()
        self._running = True
        self.config = config

    def run(self):
        while self._running:
            try:
                result = subprocess.run(
                    [str(SCRIPT_DIR / "set-status"), "--json"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    self.status_updated.emit(data)
                else:
                    self.error_occurred.emit(result.stderr)
            except subprocess.TimeoutExpired:
                logger.error("set-status timed out")
                self.error_occurred.emit("Status check timed out")
            except json.JSONDecodeError as e:
                logger.error("set-status invalid JSON: %s", e)
                self.error_occurred.emit(f"Invalid JSON: {e}")
            except Exception as e:
                logger.error("set-status error: %s", e)
                self.error_occurred.emit(str(e))

            # Sleep for configured interval
            self.msleep(self.config.control_center["refresh_interval_ms"])

    def stop(self):
        self._running = False
