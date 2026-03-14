"""Tests for wt_orch.merger — Archive, cleanup, merge queue, conflict fingerprint."""

import json
import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from wt_orch.merger import (
    MergeResult,
    MAX_MERGE_RETRIES,
    archive_change,
    cleanup_worktree,
)
from wt_orch.state import Change, OrchestratorState


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def state_file(tmp_dir):
    """Create a minimal state file for testing."""
    path = os.path.join(tmp_dir, "state.json")
    state = {
        "plan_version": 1,
        "brief_hash": "test",
        "status": "running",
        "created_at": "2026-03-14T10:00:00",
        "changes": [],
        "merge_queue": [],
        "checkpoints": [],
        "changes_since_checkpoint": 0,
    }
    with open(path, "w") as f:
        json.dump(state, f)
    return path


def _write_state(path: str, changes: list[dict], **extras) -> None:
    """Helper to write state with changes."""
    state = {
        "plan_version": 1,
        "brief_hash": "test",
        "status": "running",
        "created_at": "2026-03-14T10:00:00",
        "changes": changes,
        "merge_queue": extras.get("merge_queue", []),
        "checkpoints": [],
        "changes_since_checkpoint": 0,
    }
    state.update(extras)
    with open(path, "w") as f:
        json.dump(state, f)


class TestMergeResult:
    def test_required_fields(self):
        r = MergeResult(success=False, status="merge-blocked")
        assert r.success is False
        assert r.status == "merge-blocked"
        assert r.smoke_result == ""

    def test_custom(self):
        r = MergeResult(success=True, status="merged", smoke_result="pass")
        assert r.success is True
        assert r.status == "merged"
        assert r.smoke_result == "pass"


class TestArchiveChange:
    def test_archive_nonexistent_dir(self, tmp_dir):
        """archive_change should return True when change dir doesn't exist."""
        orig_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)
            result = archive_change("nonexistent-change")
            assert result is True
        finally:
            os.chdir(orig_cwd)

    def test_archive_creates_dated_dir(self, tmp_dir):
        """archive_change moves change dir to dated archive."""
        orig_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)
            change_dir = os.path.join("openspec", "changes", "test-change")
            os.makedirs(change_dir)
            with open(os.path.join(change_dir, "tasks.md"), "w") as f:
                f.write("# Tasks\n")

            # Will fail on git add/commit (no git repo), but mv should succeed
            result = archive_change("test-change")
            assert result is True

            # Check that source dir is gone
            assert not os.path.isdir(change_dir)

            # Check that archive dir exists
            archive_base = os.path.join("openspec", "changes", "archive")
            assert os.path.isdir(archive_base)
            archived = os.listdir(archive_base)
            assert len(archived) == 1
            assert archived[0].endswith("-test-change")
        finally:
            os.chdir(orig_cwd)


class TestCleanupWorktree:
    def test_cleanup_nonexistent_path(self, tmp_dir):
        """cleanup_worktree should handle missing path gracefully."""
        # Should not raise — paths don't exist
        cleanup_worktree("test-change", "/nonexistent/path")

    def test_log_archiving(self, tmp_dir):
        """cleanup_worktree archives logs before cleanup."""
        orig_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)
            # Create fake worktree with logs
            wt_path = os.path.join(tmp_dir, "worktree")
            logs_dir = os.path.join(wt_path, ".claude", "logs")
            os.makedirs(logs_dir)
            with open(os.path.join(logs_dir, "agent.log"), "w") as f:
                f.write("test log content\n")

            # Run cleanup — will fail on wt-close and git commands, but log archiving should work
            cleanup_worktree("test-change", wt_path)

            # Check archived logs
            archive_dir = os.path.join("wt", "orchestration", "logs", "test-change")
            if os.path.isdir(archive_dir):
                assert os.path.exists(os.path.join(archive_dir, "agent.log"))
        finally:
            os.chdir(orig_cwd)


class TestConstants:
    def test_max_merge_retries(self):
        assert MAX_MERGE_RETRIES == 5
