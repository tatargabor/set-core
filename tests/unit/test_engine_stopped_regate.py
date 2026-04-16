"""Tests for FIX 1: Ralph stopped/stuck → re-gate if new commits exist.

When the ralph agent exits its fix loop cleanly (loop_status="stopped" or
"stuck"), the engine should check for new commits in the worktree.  If the
agent made progress (new commits since the last gate run), route to
handle_change_done() for re-gating instead of marking stalled.
"""

import json
import os
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.engine import _has_commits_since_gate


@pytest.fixture
def git_wt(tmp_path):
    """Create a minimal git repo acting as a worktree."""
    wt = tmp_path / "wt"
    wt.mkdir()
    subprocess.run(["git", "init", str(wt)], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(wt), "commit", "--allow-empty", "-m", "initial"],
        capture_output=True, check=True,
    )
    return wt


class TestHasCommitsSinceGate:
    """Test the _has_commits_since_gate helper."""

    def test_no_baseline_assumes_progress(self, git_wt):
        """Without a last_gate_commit, assume agent made progress."""
        assert _has_commits_since_gate(str(git_wt), last_gate_commit="") is True

    def test_new_commits_detected(self, git_wt):
        """Detect new commits after the baseline."""
        baseline = subprocess.run(
            ["git", "-C", str(git_wt), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        # Agent makes a fix commit
        (git_wt / "fix.py").write_text("pass\n")
        subprocess.run(["git", "-C", str(git_wt), "add", "fix.py"], capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(git_wt), "commit", "-m", "fix: resolve test failure"],
            capture_output=True, check=True,
        )
        assert _has_commits_since_gate(str(git_wt), last_gate_commit=baseline) is True

    def test_no_new_commits(self, git_wt):
        """No new commits since baseline → no progress."""
        head = subprocess.run(
            ["git", "-C", str(git_wt), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        assert _has_commits_since_gate(str(git_wt), last_gate_commit=head) is False

    def test_invalid_baseline_assumes_progress(self, git_wt):
        """Invalid baseline commit hash → assume progress (safe fallback)."""
        assert _has_commits_since_gate(str(git_wt), last_gate_commit="0000dead") is True

    def test_missing_wt_returns_false(self):
        """Missing worktree path → no progress."""
        assert _has_commits_since_gate("/nonexistent/path", last_gate_commit="abc") is False
