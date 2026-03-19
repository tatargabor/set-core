"""
Linux Window Focus Tests - Verify find_window_by_title uses WM_CLASS filtering
and precise title matching to avoid false positives from Chrome or other worktrees.
"""

import sys
from unittest.mock import patch, MagicMock

import pytest

# Skip entirely on non-Linux (the class is Linux-specific)
pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux-only tests")


@pytest.fixture
def linux_platform():
    """Create a LinuxPlatform instance with xdotool available."""
    from gui.platform.linux import LinuxPlatform
    plat = LinuxPlatform()
    return plat


def _mock_run_for_windows(window_map):
    """Create a mock subprocess.run that simulates xdotool search and getwindowname.

    window_map: dict of {wm_class: {window_id: window_title, ...}, ...}
    """
    def mock_run(cmd, **kwargs):
        result = MagicMock()
        if cmd[0] != "xdotool":
            result.returncode = 1
            result.stdout = ""
            return result

        if cmd[1] == "search" and "--class" in cmd:
            wm_class = cmd[cmd.index("--class") + 1]
            matching_ids = []
            for cls, windows in window_map.items():
                if wm_class in cls:
                    matching_ids.extend(windows.keys())
            if matching_ids:
                result.returncode = 0
                result.stdout = "\n".join(matching_ids)
            else:
                result.returncode = 1
                result.stdout = ""

        elif cmd[1] == "search" and "--name" in cmd:
            pattern = cmd[cmd.index("--name") + 1]
            matching_ids = []
            for cls, windows in window_map.items():
                for wid, title in windows.items():
                    if pattern in title:
                        matching_ids.append(wid)
            if matching_ids:
                result.returncode = 0
                result.stdout = "\n".join(matching_ids)
            else:
                result.returncode = 1
                result.stdout = ""

        elif cmd[1] == "getwindowname":
            wid = cmd[2]
            for cls, windows in window_map.items():
                if wid in windows:
                    result.returncode = 0
                    result.stdout = windows[wid]
                    return result
            result.returncode = 1
            result.stdout = ""

        else:
            result.returncode = 1
            result.stdout = ""

        return result

    return mock_run


class TestWMClassFiltering:
    """Tests for WM_CLASS-based window filtering."""

    def test_filters_out_chrome_windows(self, linux_platform):
        """Chrome tabs containing the worktree name should NOT be matched."""
        window_map = {
            "dev.zed.Zed": {"73400398": "set-core"},
            "Google-chrome": {"52428823": "tatargabor/set-core - Google Chrome"},
        }
        with patch("shutil.which", return_value="/usr/bin/xdotool"), \
             patch("subprocess.run", side_effect=_mock_run_for_windows(window_map)):
            result = linux_platform.find_window_by_title("set-core", app_name="Zed")

        assert result == "73400398"

    def test_filters_out_other_worktree_windows(self, linux_platform):
        """Worktree windows with prefix-similar names should NOT be matched."""
        window_map = {
            "dev.zed.Zed": {
                "73400431": "set-core-wt-o_test",
                "73400398": "set-core",
            },
        }
        with patch("shutil.which", return_value="/usr/bin/xdotool"), \
             patch("subprocess.run", side_effect=_mock_run_for_windows(window_map)):
            result = linux_platform.find_window_by_title("set-core", app_name="Zed")

        assert result == "73400398"

    def test_matches_folder_file_pattern(self, linux_platform):
        """Zed's 'folder — filename' title pattern should match."""
        window_map = {
            "dev.zed.Zed": {
                "73400398": "set-core \u2014 CLAUDE.md",
            },
        }
        with patch("shutil.which", return_value="/usr/bin/xdotool"), \
             patch("subprocess.run", side_effect=_mock_run_for_windows(window_map)):
            result = linux_platform.find_window_by_title("set-core", app_name="Zed")

        assert result == "73400398"

    def test_no_match_returns_none(self, linux_platform):
        """When no Zed window matches the title, return None (so caller opens new editor)."""
        window_map = {
            "dev.zed.Zed": {
                "73400425": "mediapipe-python-mirror \u2014 CLAUDE.md",
                "73400422": "tgholsters-dryfire",
            },
            "Google-chrome": {"52428823": "tatargabor/set-core - Google Chrome"},
        }
        with patch("shutil.which", return_value="/usr/bin/xdotool"), \
             patch("subprocess.run", side_effect=_mock_run_for_windows(window_map)):
            result = linux_platform.find_window_by_title("set-core", app_name="Zed")

        assert result is None

    def test_combined_scenario_real_window_list(self, linux_platform):
        """Full scenario: Chrome + wrong worktree + correct worktree — should pick correct one."""
        window_map = {
            "dev.zed.Zed": {
                "73400425": "mediapipe-python-mirror \u2014 CLAUDE.md",
                "73400428": "mediapipe-python-mirror-wt-limb-rendering \u2014 IK_proposal.txt",
                "73400422": "tgholsters-dryfire",
                "73400431": "set-core-wt-o_test",
                "73400398": "set-core",
            },
            "Google-chrome": {
                "52428823": "tatargabor/set-core - Google Chrome",
            },
        }
        with patch("shutil.which", return_value="/usr/bin/xdotool"), \
             patch("subprocess.run", side_effect=_mock_run_for_windows(window_map)):
            result = linux_platform.find_window_by_title("set-core", app_name="Zed")

        assert result == "73400398"


class TestFallbackBehavior:
    """Tests for fallback when no app_name or unknown WM_CLASS."""

    def test_no_app_name_uses_substring_search(self, linux_platform):
        """Without app_name, falls back to xdotool --name substring search."""
        window_map = {
            "dev.zed.Zed": {"73400398": "set-core"},
            "Google-chrome": {"52428823": "tatargabor/set-core - Google Chrome"},
        }
        with patch("shutil.which", return_value="/usr/bin/xdotool"), \
             patch("subprocess.run", side_effect=_mock_run_for_windows(window_map)):
            result = linux_platform.find_window_by_title("set-core", app_name="")

        # Fallback returns first match (may be Chrome — old behavior preserved)
        assert result is not None

    def test_unknown_app_name_uses_substring_search(self, linux_platform):
        """Unknown app_name (not in WM_CLASS_MAP) falls back to substring search."""
        window_map = {
            "dev.zed.Zed": {"73400398": "set-core"},
        }
        with patch("shutil.which", return_value="/usr/bin/xdotool"), \
             patch("subprocess.run", side_effect=_mock_run_for_windows(window_map)):
            result = linux_platform.find_window_by_title("set-core", app_name="UnknownEditor")

        # Unknown editor: no WM_CLASS match, should fall back to substring
        # and since "UnknownEditor" is not in _WM_CLASS_MAP, it goes to fallback
        assert result is not None

    def test_no_xdotool_returns_none(self, linux_platform):
        """When xdotool is not installed, return None."""
        with patch("shutil.which", return_value=None):
            result = linux_platform.find_window_by_title("set-core", app_name="Zed")
        assert result is None


class TestWMClassMap:
    """Tests for the WM_CLASS mapping."""

    def test_map_has_known_editors(self, linux_platform):
        """All supported editors should be in the WM_CLASS map."""
        assert "Zed" in linux_platform._WM_CLASS_MAP
        assert "Code" in linux_platform._WM_CLASS_MAP
        assert "Cursor" in linux_platform._WM_CLASS_MAP
        assert "Windsurf" in linux_platform._WM_CLASS_MAP

    def test_zed_class_is_correct(self, linux_platform):
        """Zed's WM_CLASS should be dev.zed.Zed (verified empirically)."""
        assert linux_platform._WM_CLASS_MAP["Zed"] == "dev.zed.Zed"
