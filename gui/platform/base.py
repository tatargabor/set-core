"""Base platform interface for cross-platform support."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple


class PlatformInterface(ABC):
    """Abstract base class for platform-specific implementations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the platform name (linux, darwin, windows)."""
        pass

    @property
    @abstractmethod
    def is_supported(self) -> bool:
        """Return True if the platform is fully supported."""
        pass

    @abstractmethod
    def is_process_running(self, pid: int) -> bool:
        """Check if a process with the given PID is running."""
        pass

    @abstractmethod
    def get_config_dir(self) -> Path:
        """Return the platform-specific configuration directory for set-core."""
        pass

    @abstractmethod
    def get_cache_dir(self) -> Path:
        """Return the platform-specific cache directory for set-core."""
        pass

    def get_process_cmdline(self, pid: int) -> Optional[str]:
        """Get the command line of a running process. Optional method."""
        return None

    def focus_window(self, window_id: str, app_name: str = "") -> bool:
        """Focus a window by its ID.

        Args:
            window_id: Platform-specific window identifier (X11 window ID on
                       Linux, window title on macOS).
            app_name: Application name hint (e.g. "Zed"). Used on macOS to
                      activate the app and raise the specific window.
        """
        return False

    def close_window(self, window_id: str, app_name: str = "") -> bool:
        """Close a window gracefully by its ID.

        Sends a close request (WM_DELETE_WINDOW on Linux, AppleScript on macOS).
        The application may prompt for unsaved changes.

        Args:
            window_id: Platform-specific window identifier.
            app_name: Application name hint (used on macOS).
        """
        return False

    def find_window_by_title(self, title: str, app_name: str = "", exact: bool = False) -> Optional[str]:
        """Find a window by title substring.

        Args:
            title: Substring to search for in window titles.
            app_name: Application process name to search (e.g. "Zed").
                      If empty, searches all processes.
            exact: If True, only match windows whose title is exactly
                   ``title`` (no substring fallback).  Use this for main
                   repo paths whose basename is a prefix of worktree names.

        Returns:
            Platform-specific window identifier, or None.
        """
        return None

    def find_window_by_class(self, window_class: str) -> Optional[str]:
        """Find a window by class. Returns window ID or None."""
        return None

    def find_window_by_pid(self, agent_pid: int) -> Optional[Tuple[str, str]]:
        """Find a window by walking the PPID chain from an agent PID.

        Walks up the process tree from agent_pid until finding a process
        that owns a window. Max depth: 20 levels.

        Args:
            agent_pid: PID of the agent process to trace.

        Returns:
            Tuple of (window_id, process_name) if found, None otherwise.
        """
        return None

    def open_file(self, path: str) -> bool:
        """Open a file with the system's default application.

        Args:
            path: Path to the file to open

        Returns:
            True if the file was opened successfully, False otherwise
        """
        return False
