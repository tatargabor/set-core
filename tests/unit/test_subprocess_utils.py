"""Tests for wt_orch.subprocess_utils."""

import subprocess
import sys

import pytest

from wt_orch.subprocess_utils import (
    ClaudeResult,
    CommandResult,
    GitResult,
    _truncate_output,
    run_command,
    run_git,
)


class TestTruncateOutput:
    def test_short_output_unchanged(self):
        assert _truncate_output("hello", 100) == "hello"

    def test_exact_size_unchanged(self):
        text = "x" * 100
        assert _truncate_output(text, 100) == text

    def test_long_output_truncated(self):
        text = "a" * 50 + "b" * 50
        result = _truncate_output(text, 60)
        assert result.startswith("[...truncated")
        # Last 60 chars of original: 10 a's + 50 b's
        tail = result.split("\n", 1)[1]
        assert len(tail) == 60
        assert tail == "a" * 10 + "b" * 50

    def test_empty_string(self):
        assert _truncate_output("", 100) == ""


class TestRunCommand:
    def test_successful_command(self):
        result = run_command(["echo", "hello"])
        assert result.exit_code == 0
        assert result.stdout.strip() == "hello"
        assert result.timed_out is False
        assert result.duration_ms >= 0

    def test_failing_command(self):
        result = run_command(["false"])
        assert result.exit_code != 0
        assert result.timed_out is False

    def test_command_not_found(self):
        result = run_command(["nonexistent_command_xyz"])
        assert result.exit_code == 127
        assert "not found" in result.stderr.lower()

    def test_timeout(self):
        result = run_command(["sleep", "10"], timeout=1)
        assert result.timed_out is True
        assert result.exit_code == -1

    def test_cwd(self, tmp_path):
        result = run_command(["pwd"], cwd=tmp_path)
        assert result.exit_code == 0
        assert str(tmp_path) in result.stdout

    def test_stdin_data(self):
        result = run_command(["cat"], stdin_data="hello world")
        assert result.exit_code == 0
        assert result.stdout.strip() == "hello world"

    def test_output_truncation(self):
        # Generate output larger than max_output_size
        result = run_command(
            [sys.executable, "-c", "print('x' * 200)"],
            max_output_size=50,
        )
        assert result.exit_code == 0
        assert "[...truncated" in result.stdout

    def test_env_variables(self):
        result = run_command(
            [sys.executable, "-c", "import os; print(os.environ.get('TEST_VAR', ''))"],
            env={"TEST_VAR": "hello"},
        )
        assert result.exit_code == 0
        assert result.stdout.strip() == "hello"

    def test_stderr_captured(self):
        result = run_command(
            [sys.executable, "-c", "import sys; sys.stderr.write('err\\n')"]
        )
        assert "err" in result.stderr


class TestRunGit:
    def test_git_version(self):
        result = run_git("--version")
        assert result.exit_code == 0
        assert "git version" in result.stdout
        assert isinstance(result, GitResult)

    def test_git_status(self):
        result = run_git("status", "--short")
        assert result.exit_code == 0
        assert isinstance(result, GitResult)

    def test_git_invalid_command(self):
        result = run_git("nonexistent-subcommand")
        assert result.exit_code != 0
        assert isinstance(result, GitResult)


class TestDataclasses:
    def test_command_result_defaults(self):
        r = CommandResult(exit_code=0, stdout="", stderr="", duration_ms=100)
        assert r.timed_out is False

    def test_claude_result_inherits(self):
        r = ClaudeResult(exit_code=0, stdout="out", stderr="", duration_ms=50)
        assert isinstance(r, CommandResult)
        assert r.stdout == "out"

    def test_git_result_inherits(self):
        r = GitResult(exit_code=1, stdout="", stderr="err", duration_ms=30)
        assert isinstance(r, CommandResult)
        assert r.stderr == "err"
