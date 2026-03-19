"""Windows platform implementation."""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from .base import PlatformInterface

logger = logging.getLogger("set-control.windows")


class WindowsPlatform(PlatformInterface):
    """Windows-specific platform implementation."""

    @property
    def name(self) -> str:
        return "windows"

    @property
    def is_supported(self) -> bool:
        return True

    def is_process_running(self, pid: int) -> bool:
        """Check if process is running using tasklist."""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
            )
            return str(pid) in result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_config_dir(self) -> Path:
        """Return Windows config directory for set-core."""
        appdata = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
        return Path(appdata) / "set-core"

    def get_cache_dir(self) -> Path:
        """Return Windows cache directory for set-core."""
        localappdata = os.environ.get(
            "LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")
        )
        return Path(localappdata) / "set-core" / "cache"

    def get_process_cmdline(self, pid: int) -> Optional[str]:
        """Get command line using wmic."""
        try:
            result = subprocess.run(
                [
                    "wmic",
                    "process",
                    "where",
                    f"ProcessId={pid}",
                    "get",
                    "CommandLine",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    return lines[1].strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        return None

    def focus_window(self, window_id: str, app_name: str = "") -> bool:
        """Focus window - not implemented on Windows without additional libs."""
        logger.debug("focus_window: not implemented (window_id=%r)", window_id)
        return False

    def find_window_by_title(self, title: str, app_name: str = "", exact: bool = False) -> Optional[str]:
        """Find window by title - not implemented on Windows without additional libs."""
        logger.debug("find_window_by_title: not implemented (title=%r)", title)
        return None

    def open_file(self, path: str) -> bool:
        """Open a file with Windows start command."""
        try:
            os.startfile(path)
            return True
        except Exception:
            return False
