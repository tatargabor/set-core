"""Linux platform implementation."""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from .base import PlatformInterface

logger = logging.getLogger("set-control.linux")


class LinuxPlatform(PlatformInterface):
    """Linux-specific platform implementation."""

    # Map app_name (from editor config) to X11 WM_CLASS for window filtering
    _WM_CLASS_MAP = {
        "Zed": "dev.zed.Zed",
        "Code": "code",
        "Cursor": "cursor",
        "Windsurf": "windsurf",
    }

    @property
    def name(self) -> str:
        return "linux"

    @property
    def is_supported(self) -> bool:
        return True

    def is_process_running(self, pid: int) -> bool:
        """Check if process is running using /proc."""
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def get_config_dir(self) -> Path:
        """Return XDG config directory for set-core."""
        xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        return Path(xdg_config) / "set-core"

    def get_cache_dir(self) -> Path:
        """Return XDG cache directory for set-core."""
        xdg_cache = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        return Path(xdg_cache) / "set-core"

    def get_process_cmdline(self, pid: int) -> Optional[str]:
        """Get command line from /proc filesystem."""
        try:
            proc_path = Path(f"/proc/{pid}/cmdline")
            if proc_path.exists():
                cmdline = proc_path.read_text().replace("\x00", " ").strip()
                return cmdline
        except (OSError, PermissionError):
            pass
        return None

    def focus_window(self, window_id: str, app_name: str = "") -> bool:
        """Focus window using xdotool."""
        logger.debug("focus_window: window_id=%r app_name=%r", window_id, app_name)
        if not shutil.which("xdotool"):
            logger.error("focus_window: xdotool not found")
            return False
        try:
            subprocess.run(
                ["xdotool", "windowactivate", window_id],
                check=True,
                capture_output=True,
            )
            logger.debug("focus_window: success")
            return True
        except subprocess.CalledProcessError as e:
            logger.error("focus_window: failed — %s", e)
            return False

    def close_window(self, window_id: str, app_name: str = "") -> bool:
        """Close window gracefully using xdotool windowclose (WM_DELETE_WINDOW)."""
        logger.debug("close_window: window_id=%r", window_id)
        if not shutil.which("xdotool"):
            logger.error("close_window: xdotool not found")
            return False
        try:
            subprocess.run(
                ["xdotool", "windowclose", window_id],
                check=True,
                capture_output=True,
            )
            logger.debug("close_window: success")
            return True
        except subprocess.CalledProcessError as e:
            logger.error("close_window: failed — %s", e)
            return False

    def find_window_by_title(self, title: str, app_name: str = "", exact: bool = False) -> Optional[str]:
        """Find window by title using xdotool.

        When app_name is provided and mapped to a WM_CLASS, uses two-step
        filtering: first by WM_CLASS (only editor windows), then precise
        Python-side title matching to avoid false positives from Chrome tabs
        or similarly-named worktree windows.
        """
        logger.debug("find_window_by_title: title=%r app_name=%r exact=%s", title, app_name, exact)
        if not shutil.which("xdotool"):
            logger.error("find_window_by_title: xdotool not found")
            return None

        # Two-step approach when we know the editor's WM_CLASS
        wm_class = self._WM_CLASS_MAP.get(app_name) if app_name else None
        if wm_class:
            try:
                result = subprocess.run(
                    ["xdotool", "search", "--class", wm_class],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0 and result.stdout.strip():
                    for wid in result.stdout.strip().split("\n"):
                        try:
                            wname = subprocess.run(
                                ["xdotool", "getwindowname", wid],
                                capture_output=True,
                                text=True,
                            )
                            if wname.returncode == 0:
                                window_title = wname.stdout.strip()
                                # Exact match or editor's "folder — file" pattern
                                if window_title == title or window_title.startswith(title + " \u2014 "):
                                    logger.debug("find_window_by_title: found wid=%s title=%r", wid, window_title)
                                    return wid
                        except subprocess.CalledProcessError:
                            continue
            except subprocess.CalledProcessError:
                pass
            logger.debug("find_window_by_title: not found (class search)")
            return None

        # Fallback: no app_name or unknown WM_CLASS — use xdotool substring search
        try:
            if exact:
                pattern = f"^{title}$"
            else:
                pattern = title
            result = subprocess.run(
                ["xdotool", "search", "--name", pattern],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                found = result.stdout.strip().split("\n")[0]
                logger.debug("find_window_by_title: found wid=%s", found)
                return found
        except subprocess.CalledProcessError:
            pass
        logger.debug("find_window_by_title: not found")
        return None

    def find_window_by_class(self, window_class: str) -> Optional[str]:
        """Find window by class using xdotool."""
        if not shutil.which("xdotool"):
            return None
        try:
            result = subprocess.run(
                ["xdotool", "search", "--class", window_class],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split("\n")[0]
        except subprocess.CalledProcessError:
            pass
        return None

    def find_window_by_pid(self, agent_pid: int) -> Optional[Tuple[str, str]]:
        """Find window by walking PPID chain using /proc and xdotool."""
        logger.debug("find_window_by_pid: agent_pid=%d", agent_pid)
        if not shutil.which("xdotool"):
            return None

        current_pid = agent_pid
        for _ in range(20):
            if current_pid <= 1:
                break
            try:
                result = subprocess.run(
                    ["xdotool", "search", "--pid", str(current_pid)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0 and result.stdout.strip():
                    candidates = result.stdout.strip().split("\n")
                    # Prefer top-level windows (_NET_WM_WINDOW_TYPE contains NORMAL)
                    window_id = None
                    for candidate in candidates:
                        try:
                            xprop_result = subprocess.run(
                                ["xprop", "-id", candidate, "_NET_WM_WINDOW_TYPE"],
                                capture_output=True, text=True,
                            )
                            if "NORMAL" in xprop_result.stdout:
                                window_id = candidate
                                break
                        except subprocess.CalledProcessError:
                            continue
                    # Fallback: use first window if no NORMAL type found
                    if not window_id:
                        window_id = candidates[0]
                    # Get process name
                    proc_name = "unknown"
                    try:
                        comm_path = Path(f"/proc/{current_pid}/comm")
                        if comm_path.exists():
                            proc_name = comm_path.read_text().strip()
                    except (OSError, PermissionError):
                        pass
                    return (window_id, proc_name)
            except subprocess.CalledProcessError:
                pass

            # Walk up to parent
            try:
                stat_path = Path(f"/proc/{current_pid}/stat")
                if stat_path.exists():
                    stat_content = stat_path.read_text()
                    # Format: pid (comm) state ppid ...
                    # Find closing paren to handle comm with spaces
                    close_paren = stat_content.rfind(")")
                    if close_paren >= 0:
                        fields = stat_content[close_paren + 2:].split()
                        ppid = int(fields[1])  # ppid is 4th field, index 1 after state
                        if ppid == current_pid or ppid <= 1:
                            break
                        current_pid = ppid
                        continue
                # Fallback to ps
                ps_result = subprocess.run(
                    ["ps", "-o", "ppid=", "-p", str(current_pid)],
                    capture_output=True,
                    text=True,
                )
                ppid = int(ps_result.stdout.strip())
                if ppid == current_pid or ppid <= 1:
                    break
                current_pid = ppid
            except (OSError, ValueError, subprocess.CalledProcessError):
                break
        return None

    def open_file(self, path: str) -> bool:
        """Open a file with xdg-open."""
        try:
            subprocess.Popen(
                ["xdg-open", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False
