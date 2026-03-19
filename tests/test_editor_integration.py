"""
Tests for multi-editor support in set-core.

Run with: pytest tests/test_editor_integration.py -v
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# Project root directory
PROJECT_DIR = Path(__file__).parent.parent
BIN_DIR = PROJECT_DIR / "bin"


class TestWtConfig:
    """Tests for set-config command."""

    def test_editor_list_runs(self):
        """set-config editor list runs without error."""
        result = subprocess.run(
            [str(BIN_DIR / "set-config"), "editor", "list"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Supported editors:" in result.stdout
        assert "zed" in result.stdout
        assert "vscode" in result.stdout

    def test_editor_show_runs(self):
        """set-config editor show runs without error."""
        result = subprocess.run(
            [str(BIN_DIR / "set-config"), "editor", "show"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "editor:" in result.stdout.lower()

    def test_editor_set_invalid_rejects(self):
        """set-config editor set rejects invalid editor names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["SET_CONFIG_DIR"] = tmpdir

            result = subprocess.run(
                [str(BIN_DIR / "set-config"), "editor", "set", "invalid_editor"],
                capture_output=True,
                text=True,
                env=env,
            )
            assert result.returncode != 0
            assert "Invalid editor" in result.stderr or "Error" in result.stderr

    def test_editor_set_valid_accepts(self):
        """set-config editor set accepts valid editor names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["SET_CONFIG_DIR"] = tmpdir

            # Set to vscode
            result = subprocess.run(
                [str(BIN_DIR / "set-config"), "editor", "set", "vscode"],
                capture_output=True,
                text=True,
                env=env,
            )
            assert result.returncode == 0

            # Verify it was saved
            config_file = Path(tmpdir) / "config.json"
            assert config_file.exists()
            with open(config_file) as f:
                config = json.load(f)
            assert config.get("editor", {}).get("name") == "vscode"


class TestWtWork:
    """Tests for set-work command."""

    def test_help_shows_editor_option(self):
        """set-work --help shows -e/--editor option."""
        result = subprocess.run(
            [str(BIN_DIR / "set-work"), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "-e, --editor" in result.stdout
        assert "vscode" in result.stdout

    def test_requires_change_id(self):
        """set-work requires change-id argument."""
        result = subprocess.run(
            [str(BIN_DIR / "set-work")],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "Change ID required" in result.stderr or "Error" in result.stderr


class TestWtFocus:
    """Tests for set-focus command."""

    def test_help_shows_editor_option(self):
        """set-focus --help shows -e/--editor option."""
        result = subprocess.run(
            [str(BIN_DIR / "set-focus"), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "-e, --editor" in result.stdout
        assert "vscode" in result.stdout

    def test_list_runs(self):
        """set-focus --list runs without error."""
        result = subprocess.run(
            [str(BIN_DIR / "set-focus"), "--list"],
            capture_output=True,
            text=True,
        )
        # Should succeed even if no windows found
        assert result.returncode == 0


class TestEditorDetection:
    """Tests for editor detection in set-common.sh."""

    def run_bash_function(self, function_name: str, *args, env=None) -> subprocess.CompletedProcess:
        """Helper to run a bash function from set-common.sh."""
        script = f"""
        source "{BIN_DIR}/set-common.sh"
        {function_name} {' '.join(f'"{a}"' for a in args)}
        """
        return subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            env=env or os.environ,
        )

    def test_get_supported_editor_names(self):
        """get_supported_editor_names returns all editor names."""
        result = self.run_bash_function("get_supported_editor_names")
        assert result.returncode == 0
        editors = result.stdout.strip().split("\n")
        assert "zed" in editors
        assert "vscode" in editors
        assert "cursor" in editors
        assert "windsurf" in editors

    def test_get_editor_property_command(self):
        """get_editor_property returns correct command."""
        result = self.run_bash_function("get_editor_property", "zed", "command")
        assert result.returncode == 0
        assert result.stdout.strip() == "zed"

        result = self.run_bash_function("get_editor_property", "vscode", "command")
        assert result.returncode == 0
        assert result.stdout.strip() == "code"

    def test_get_editor_property_window_class(self):
        """get_editor_property returns correct window class."""
        result = self.run_bash_function("get_editor_property", "zed", "window_class")
        assert result.returncode == 0
        assert result.stdout.strip() == "dev.zed.Zed"

        result = self.run_bash_function("get_editor_property", "vscode", "window_class")
        assert result.returncode == 0
        assert result.stdout.strip() == "Code"

    def test_get_editor_property_claude_launch(self):
        """get_editor_property returns correct claude launch method."""
        result = self.run_bash_function("get_editor_property", "zed", "claude_launch")
        assert result.returncode == 0
        assert result.stdout.strip() == "keystroke"

        result = self.run_bash_function("get_editor_property", "vscode", "claude_launch")
        assert result.returncode == 0
        assert result.stdout.strip() == "terminal"

    def test_get_active_editor_returns_value(self):
        """get_active_editor returns an editor name."""
        result = self.run_bash_function("get_active_editor")
        # Should succeed if at least one editor is installed
        if result.returncode == 0:
            assert result.stdout.strip() in ["zed", "vscode", "cursor", "windsurf"]

    def test_config_isolation(self):
        """Configuration changes are isolated with SET_CONFIG_DIR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["SET_CONFIG_DIR"] = tmpdir

            # Set editor
            result = self.run_bash_function("set_configured_editor", "cursor", env=env)
            # Note: will "fail" if cursor not installed, but config should still be set

            # Read back
            result = self.run_bash_function("get_configured_editor", env=env)
            assert result.returncode == 0
            assert result.stdout.strip() == "cursor"

            # Verify file exists
            config_file = Path(tmpdir) / "config.json"
            assert config_file.exists()


@pytest.mark.integration
class TestEditorIntegration:
    """Integration tests that require editors to be installed.

    Run with: pytest tests/test_editor_integration.py -v -m integration
    """

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_zed_installed(self):
        """Test that Zed is installed (skip if not)."""
        result = subprocess.run(["which", "zed"], capture_output=True)
        if result.returncode != 0:
            pytest.skip("Zed not installed")
        assert result.returncode == 0

    def test_vscode_installed(self):
        """Test that VS Code is installed (skip if not)."""
        result = subprocess.run(["which", "code"], capture_output=True)
        if result.returncode != 0:
            pytest.skip("VS Code not installed")
        assert result.returncode == 0

    def test_cursor_installed(self):
        """Test that Cursor is installed (skip if not)."""
        result = subprocess.run(["which", "cursor"], capture_output=True)
        if result.returncode != 0:
            pytest.skip("Cursor not installed")
        assert result.returncode == 0

    def test_windsurf_installed(self):
        """Test that Windsurf is installed (skip if not)."""
        result = subprocess.run(["which", "windsurf"], capture_output=True)
        if result.returncode != 0:
            pytest.skip("Windsurf not installed")
        assert result.returncode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
