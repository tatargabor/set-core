"""Tests for wt_orch.git_utils — uncommitted work detection."""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from wt_orch.git_utils import git_has_uncommitted_work


@pytest.fixture
def git_wt(tmp_path):
    """Create a real tiny git repo for testing."""
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"],
        capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Test"],
        capture_output=True, check=True,
    )
    # Initial commit so HEAD exists
    readme = tmp_path / "README.md"
    readme.write_text("init\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "init"],
        capture_output=True, check=True,
    )
    return str(tmp_path)


class TestGitHasUncommittedWork:
    def test_clean_worktree(self, git_wt):
        has_work, summary = git_has_uncommitted_work(git_wt)
        assert has_work is False
        assert summary == ""

    def test_modified_files(self, git_wt):
        with open(os.path.join(git_wt, "README.md"), "w") as f:
            f.write("changed\n")
        has_work, summary = git_has_uncommitted_work(git_wt)
        assert has_work is True
        assert "modified" in summary

    def test_untracked_files(self, git_wt):
        with open(os.path.join(git_wt, "newfile.txt"), "w") as f:
            f.write("new\n")
        has_work, summary = git_has_uncommitted_work(git_wt)
        assert has_work is True
        assert "untracked" in summary

    def test_mixed_modified_and_untracked(self, git_wt):
        with open(os.path.join(git_wt, "README.md"), "w") as f:
            f.write("changed\n")
        with open(os.path.join(git_wt, "new.txt"), "w") as f:
            f.write("new\n")
        has_work, summary = git_has_uncommitted_work(git_wt)
        assert has_work is True
        assert "modified" in summary
        assert "untracked" in summary

    def test_timeout_fails_open(self, monkeypatch):
        """Timeout → fail-open (False, '')."""
        def mock_run(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="git", timeout=10)

        monkeypatch.setattr(subprocess, "run", mock_run)
        has_work, summary = git_has_uncommitted_work("/nonexistent")
        assert has_work is False
        assert summary == ""

    def test_git_error_fails_open(self, monkeypatch):
        """Git returning non-zero → fail-open."""
        def mock_run(*a, **kw):
            return subprocess.CompletedProcess(args=a, returncode=128, stdout="", stderr="error")

        monkeypatch.setattr(subprocess, "run", mock_run)
        has_work, summary = git_has_uncommitted_work("/nonexistent")
        assert has_work is False
        assert summary == ""

    def test_os_error_fails_open(self, monkeypatch):
        """OSError (git not found) → fail-open."""
        def mock_run(*a, **kw):
            raise OSError("git not found")

        monkeypatch.setattr(subprocess, "run", mock_run)
        has_work, summary = git_has_uncommitted_work("/nonexistent")
        assert has_work is False
        assert summary == ""
