"""Unit tests for PPID chain walking in gui/platform/linux.py"""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestLinuxFindWindowByPid:
    """Test find_window_by_pid on Linux platform."""

    @pytest.fixture
    def linux_platform(self):
        from gui.platform.linux import LinuxPlatform
        return LinuxPlatform()

    def test_no_xdotool_returns_none(self, linux_platform):
        """When xdotool is not installed, returns None."""
        with patch("shutil.which", return_value=None):
            result = linux_platform.find_window_by_pid(12345)
            assert result is None

    def test_direct_pid_owns_window(self, linux_platform):
        """Agent PID directly owns a window."""
        mock_run = MagicMock()
        mock_run.returncode = 0
        mock_run.stdout = "96469037\n"

        with patch("shutil.which", return_value="/usr/bin/xdotool"), \
             patch("subprocess.run", return_value=mock_run), \
             patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value="zed-editor\n"):
            result = linux_platform.find_window_by_pid(1000)
            assert result is not None
            assert result[0] == "96469037"
            assert result[1] == "zed-editor"

    def test_parent_owns_window(self, linux_platform):
        """Window found at parent level (2 hops)."""
        call_count = [0]

        def mock_run_side_effect(cmd, **kwargs):
            result = MagicMock()
            if cmd[0] == "xdotool":
                call_count[0] += 1
                if call_count[0] == 1:
                    # First call: agent PID has no window
                    result.returncode = 1
                    result.stdout = ""
                else:
                    # Second call: parent has a window
                    result.returncode = 0
                    result.stdout = "12345678\n"
            elif cmd[0] == "ps":
                result.returncode = 0
                result.stdout = "500"  # ppid = 500
            return result

        with patch("shutil.which", return_value="/usr/bin/xdotool"), \
             patch("subprocess.run", side_effect=mock_run_side_effect), \
             patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", side_effect=["1000 (claude) S 500 1000 1000 0 -1\n", "kitty\n"]):
            result = linux_platform.find_window_by_pid(1000)
            assert result is not None
            assert result[0] == "12345678"

    def test_max_depth_reached(self, linux_platform):
        """Returns None when max depth (20) is reached."""
        def mock_run_side_effect(cmd, **kwargs):
            result = MagicMock()
            if cmd[0] == "xdotool":
                result.returncode = 1
                result.stdout = ""
            elif cmd[0] == "ps":
                result.returncode = 0
                result.stdout = "2"  # always returns pid 2 (never 1, never loops)
            return result

        with patch("shutil.which", return_value="/usr/bin/xdotool"), \
             patch("subprocess.run", side_effect=mock_run_side_effect), \
             patch.object(Path, "exists", return_value=False):
            result = linux_platform.find_window_by_pid(1000)
            assert result is None

    def test_pid_1_stops_walk(self, linux_platform):
        """Walk stops at PID 1 (init)."""
        def mock_run_side_effect(cmd, **kwargs):
            result = MagicMock()
            if cmd[0] == "xdotool":
                result.returncode = 1
                result.stdout = ""
            elif cmd[0] == "ps":
                result.returncode = 0
                result.stdout = "1"  # parent is init
            return result

        with patch("shutil.which", return_value="/usr/bin/xdotool"), \
             patch("subprocess.run", side_effect=mock_run_side_effect), \
             patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value="1000 (claude) S 1 1000 1000 0 -1\n"):
            result = linux_platform.find_window_by_pid(1000)
            assert result is None


class TestPermissionFlags:
    """Test get_claude_permission_flags() bash function."""

    def _run_bash(self, script: str) -> str:
        """Run a bash snippet that sources set-common.sh."""
        full_script = f"""
        set -euo pipefail
        export SET_CONFIG_DIR=$(mktemp -d)
        source bin/set-common.sh
        {script}
        rm -rf "$SET_CONFIG_DIR"
        """
        result = subprocess.run(
            ["bash", "-c", full_script],
            capture_output=True, text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        return result.stdout.strip()

    def test_auto_accept_mode(self):
        flags = self._run_bash('get_claude_permission_flags "auto-accept"')
        assert flags == "--dangerously-skip-permissions"

    def test_allowed_tools_mode(self):
        flags = self._run_bash('get_claude_permission_flags "allowedTools"')
        assert "allowedTools" in flags

    def test_plan_mode(self):
        flags = self._run_bash('get_claude_permission_flags "plan"')
        assert flags == ""

    def test_default_mode(self):
        flags = self._run_bash("get_claude_permission_flags")
        assert flags == "--dangerously-skip-permissions"
