"""Tests for _run_memory() process group kill on timeout."""

import os
import signal
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest


def _import_run_memory():
    """Import _run_memory with fastmcp mocked out (not needed for this function)."""
    import importlib

    # Mock fastmcp before importing set_mcp_server
    mock_fastmcp = MagicMock()
    mock_fastmcp.FastMCP.return_value = MagicMock()
    sys.modules["fastmcp"] = mock_fastmcp

    mcp_path = os.path.join(os.path.dirname(__file__), "..", "..", "mcp-server")
    sys.path.insert(0, mcp_path)

    # Force reimport
    if "set_mcp_server" in sys.modules:
        del sys.modules["set_mcp_server"]

    import set_mcp_server

    return set_mcp_server._run_memory, set_mcp_server


_run_memory, _mcp_mod = _import_run_memory()


class TestRunMemoryTimeout:
    """Verify _run_memory kills process group on timeout."""

    def test_kills_process_group_on_timeout(self):
        """When subprocess times out, os.killpg is called to kill entire group."""
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_proc.communicate.side_effect = subprocess.TimeoutExpired(
            cmd="set-memory", timeout=1
        )

        with patch.object(_mcp_mod.subprocess, "Popen", return_value=mock_proc), \
             patch.object(_mcp_mod.os, "killpg") as mock_killpg, \
             patch.object(_mcp_mod, "MEMORY_PROJECT_DIR", "/tmp"):
            result = _run_memory(["dedup"], timeout=1)

            mock_killpg.assert_called_once_with(99999, signal.SIGKILL)
            mock_proc.wait.assert_called_once()
            assert "timed out" in result

    def test_falls_back_to_proc_kill_on_oserror(self):
        """If killpg fails (OSError), falls back to proc.kill()."""
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_proc.communicate.side_effect = subprocess.TimeoutExpired(
            cmd="set-memory", timeout=1
        )

        with patch.object(_mcp_mod.subprocess, "Popen", return_value=mock_proc), \
             patch.object(_mcp_mod.os, "killpg", side_effect=OSError("No such process")), \
             patch.object(_mcp_mod, "MEMORY_PROJECT_DIR", "/tmp"):
            result = _run_memory(["dedup"], timeout=1)

            mock_proc.kill.assert_called_once()
            assert "timed out" in result

    def test_popen_uses_start_new_session(self):
        """Popen must use start_new_session=True for process group isolation."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("output", "")
        mock_proc.returncode = 0

        with patch.object(_mcp_mod.subprocess, "Popen", return_value=mock_proc) as mock_popen, \
             patch.object(_mcp_mod, "MEMORY_PROJECT_DIR", "/tmp"):
            _run_memory(["stats"])

            call_kwargs = mock_popen.call_args[1]
            assert call_kwargs["start_new_session"] is True


class TestRunMemoryNormal:
    """Verify normal (non-timeout) behavior is preserved."""

    def test_returns_stdout_on_success(self):
        """Normal call returns stdout."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ('{"total": 5}', "")
        mock_proc.returncode = 0

        with patch.object(_mcp_mod.subprocess, "Popen", return_value=mock_proc), \
             patch.object(_mcp_mod, "MEMORY_PROJECT_DIR", "/tmp"):
            result = _run_memory(["stats"])
            assert result == '{"total": 5}'

    def test_returns_error_on_nonzero_exit(self):
        """Non-zero exit with stderr returns error."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", "something went wrong")
        mock_proc.returncode = 1

        with patch.object(_mcp_mod.subprocess, "Popen", return_value=mock_proc), \
             patch.object(_mcp_mod, "MEMORY_PROJECT_DIR", "/tmp"):
            result = _run_memory(["bad-cmd"])
            assert result.startswith("Error:")

    def test_returns_no_output_on_empty_stdout(self):
        """Empty stdout returns '(no output)'."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", "")
        mock_proc.returncode = 0

        with patch.object(_mcp_mod.subprocess, "Popen", return_value=mock_proc), \
             patch.object(_mcp_mod, "MEMORY_PROJECT_DIR", "/tmp"):
            result = _run_memory(["stats"])
            assert result == "(no output)"

    def test_file_not_found(self):
        """FileNotFoundError returns friendly message."""
        with patch.object(_mcp_mod.subprocess, "Popen", side_effect=FileNotFoundError), \
             patch.object(_mcp_mod, "MEMORY_PROJECT_DIR", "/tmp"):
            result = _run_memory(["stats"])
            assert "not found" in result
