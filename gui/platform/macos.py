"""macOS platform implementation."""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from .base import PlatformInterface

logger = logging.getLogger("set-control.macos")


class MacOSPlatform(PlatformInterface):
    """macOS-specific platform implementation."""

    @property
    def name(self) -> str:
        return "darwin"

    @property
    def is_supported(self) -> bool:
        return True

    def is_process_running(self, pid: int) -> bool:
        """Check if process is running using kill(0)."""
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def get_config_dir(self) -> Path:
        """Return macOS config directory for set-core."""
        return Path.home() / "Library" / "Application Support" / "set-core"

    def get_cache_dir(self) -> Path:
        """Return macOS cache directory for set-core."""
        return Path.home() / "Library" / "Caches" / "set-core"

    def get_process_cmdline(self, pid: int) -> Optional[str]:
        """Get command line using ps command."""
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "args="],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except subprocess.CalledProcessError:
            pass
        return None

    def focus_window(self, window_id: str, app_name: str = "") -> bool:
        """Focus window using AppleScript.

        Args:
            window_id: On macOS this is the window title (as returned by
                       find_window_by_title). Falls back to PID-based
                       activation if app_name is empty.
            app_name: Application name to activate (e.g. "Zed").
                      When provided, activates the app and raises the
                      specific window matching window_id by title.

        Returns:
            True if the window was focused successfully.
        """
        logger.debug("focus_window: window_id=%r app_name=%r", window_id, app_name)
        if app_name:
            # Activate the app, then raise the specific window by title
            # Try exact match first, fall back to substring
            script = f'''
            tell application "{app_name}" to activate
            delay 0.1
            tell application "System Events"
                tell process "{app_name}"
                    set exactList to every window whose name is "{window_id}"
                    if (count of exactList) > 0 then
                        perform action "AXRaise" of first item of exactList
                    else
                        perform action "AXRaise" of (first window whose name contains "{window_id}")
                    end if
                end tell
            end tell
            '''
        else:
            # Legacy: PID-based activation
            script = f'tell application "System Events" to set frontmost of first process whose unix id is {window_id} to true'
        try:
            subprocess.run(
                ["osascript", "-e", script],
                check=True,
                capture_output=True,
                timeout=5,
            )
            logger.debug("focus_window: success")
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.error("focus_window: failed — %s", e)
            return False

    def close_window(self, window_id: str, app_name: str = "") -> bool:
        """Close window gracefully using AppleScript.

        Args:
            window_id: The window title (as returned by find_window_by_title).
            app_name: Application name (e.g. "Zed").
        """
        logger.debug("close_window: window_id=%r app_name=%r", window_id, app_name)
        if app_name:
            # Use System Events (not the app's scripting API) — works with all editors
            script = f'''
            tell application "System Events"
                tell process "{app_name}"
                    set exactList to every window whose name is "{window_id}"
                    if (count of exactList) > 0 then
                        click (first button of first item of exactList whose description is "close button")
                    else
                        set partialList to every window whose name contains "{window_id}"
                        if (count of partialList) > 0 then
                            click (first button of first item of partialList whose description is "close button")
                        end if
                    end if
                end tell
            end tell
            '''
        else:
            return False
        try:
            subprocess.run(
                ["osascript", "-e", script],
                check=True,
                capture_output=True,
                timeout=5,
            )
            logger.debug("close_window: success")
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.error("close_window: failed — %s", e)
            return False

    def find_window_by_title(self, title: str, app_name: str = "", exact: bool = False) -> Optional[str]:
        """Find window by title using AppleScript.

        Args:
            title: Substring to search for in window titles.
            app_name: Application process name to search (e.g. "Zed").
                      If empty, searches all non-background processes.
            exact: If True, only match windows whose title is exactly
                   ``title`` (no substring fallback).

        Returns:
            The matching window's title (used as identifier on macOS), or None.
        """
        logger.debug("find_window_by_title: title=%r app_name=%r exact=%s", title, app_name, exact)
        if app_name:
            if exact:
                script = f'''
                tell application "System Events"
                    tell process "{app_name}"
                        set exactList to every window whose name is "{title}"
                        if (count of exactList) > 0 then
                            return name of first item of exactList
                        end if
                    end tell
                end tell
                return ""
                '''
            else:
                # Try exact match first, then fall back to substring.
                script = f'''
                tell application "System Events"
                    tell process "{app_name}"
                        set exactList to every window whose name is "{title}"
                        if (count of exactList) > 0 then
                            return name of first item of exactList
                        end if
                        set partialList to every window whose name contains "{title}"
                        if (count of partialList) > 0 then
                            return name of first item of partialList
                        end if
                    end tell
                end tell
                return ""
                '''
        else:
            if exact:
                script = f'''
                tell application "System Events"
                    repeat with p in (every process whose background only is false)
                        repeat with w in (every window of p)
                            if name of w is "{title}" then
                                return name of w
                            end if
                        end repeat
                    end repeat
                end tell
                return ""
                '''
            else:
                script = f'''
                tell application "System Events"
                    repeat with p in (every process whose background only is false)
                        repeat with w in (every window of p)
                            if name of w is "{title}" then
                                return name of w
                            end if
                        end repeat
                    end repeat
                    repeat with p in (every process whose background only is false)
                        repeat with w in (every window of p)
                            if name of w contains "{title}" then
                                return name of w
                            end if
                        end repeat
                    end repeat
                end tell
                return ""
                '''
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                found = result.stdout.strip()
                logger.debug("find_window_by_title: found=%r", found)
                return found
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.error("find_window_by_title: error — %s", e)
        logger.debug("find_window_by_title: not found")
        return None

    def find_window_by_pid(self, agent_pid: int) -> Optional[Tuple[str, str]]:
        """Find window by walking PPID chain using AppleScript."""
        logger.debug("find_window_by_pid: agent_pid=%d", agent_pid)
        current_pid = agent_pid
        for _ in range(20):
            if current_pid <= 1:
                break
            try:
                script = f'''
                tell application "System Events"
                    try
                        set targetProc to first process whose unix id is {current_pid}
                        if (count of windows of targetProc) > 0 then
                            return name of targetProc & "|" & (id of first window of targetProc)
                        end if
                    end try
                end tell
                return ""
                '''
                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                output = result.stdout.strip()
                if output and "|" in output:
                    proc_name, window_id = output.split("|", 1)
                    logger.debug("find_window_by_pid: found proc=%s wid=%s at pid=%d", proc_name, window_id, current_pid)
                    return (window_id, proc_name)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass

            # Walk up to parent
            try:
                ps_result = subprocess.run(
                    ["ps", "-o", "ppid=", "-p", str(current_pid)],
                    capture_output=True,
                    text=True,
                )
                ppid = int(ps_result.stdout.strip())
                if ppid == current_pid or ppid <= 1:
                    break
                current_pid = ppid
            except (ValueError, subprocess.CalledProcessError):
                break
        return None

    def open_file(self, path: str) -> bool:
        """Open a file with macOS open command."""
        try:
            subprocess.Popen(
                ["open", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False
