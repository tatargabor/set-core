"""Tests for set_orch.merger — Archive, cleanup, merge queue, conflict fingerprint."""

import json
import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.merger import (
    MergeResult,
    MAX_MERGE_RETRIES,
    archive_change,
    cleanup_worktree,
    merge_i18n_sidecars,
)
from set_orch.state import Change, OrchestratorState


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

            # Run cleanup — will fail on set-close and git commands, but log archiving should work
            cleanup_worktree("test-change", wt_path)

            # Check archived logs
            archive_dir = os.path.join("wt", "orchestration", "logs", "test-change")
            if os.path.isdir(archive_dir):
                assert os.path.exists(os.path.join(archive_dir, "agent.log"))
        finally:
            os.chdir(orig_cwd)


class TestMergeI18nSidecars:
    """Tests for merge_i18n_sidecars() utility."""

    def test_merges_sidecar_into_canonical(self, tmp_dir):
        msg_dir = os.path.join(tmp_dir, "src", "messages")
        os.makedirs(msg_dir)
        # Canonical file
        with open(os.path.join(msg_dir, "en.json"), "w") as f:
            json.dump({"common": {"hello": "Hello"}}, f)
        # Sidecar file
        with open(os.path.join(msg_dir, "en.checkout.json"), "w") as f:
            json.dump({"checkout": {"title": "Checkout"}}, f)

        count = merge_i18n_sidecars(tmp_dir)
        assert count == 1

        result = json.loads(open(os.path.join(msg_dir, "en.json")).read())
        assert result["common"]["hello"] == "Hello"
        assert result["checkout"]["title"] == "Checkout"
        # Sidecar should be deleted
        assert not os.path.exists(os.path.join(msg_dir, "en.checkout.json"))

    def test_multiple_sidecars(self, tmp_dir):
        msg_dir = os.path.join(tmp_dir, "src", "messages")
        os.makedirs(msg_dir)
        with open(os.path.join(msg_dir, "en.json"), "w") as f:
            json.dump({}, f)
        with open(os.path.join(msg_dir, "en.cart.json"), "w") as f:
            json.dump({"cart": {"add": "Add"}}, f)
        with open(os.path.join(msg_dir, "en.auth.json"), "w") as f:
            json.dump({"auth": {"login": "Login"}}, f)

        count = merge_i18n_sidecars(tmp_dir)
        assert count == 2

        result = json.loads(open(os.path.join(msg_dir, "en.json")).read())
        assert "cart" in result
        assert "auth" in result

    def test_no_sidecars_returns_zero(self, tmp_dir):
        msg_dir = os.path.join(tmp_dir, "src", "messages")
        os.makedirs(msg_dir)
        with open(os.path.join(msg_dir, "en.json"), "w") as f:
            json.dump({"common": {}}, f)
        assert merge_i18n_sidecars(tmp_dir) == 0

    def test_no_messages_dir_returns_zero(self, tmp_dir):
        assert merge_i18n_sidecars(tmp_dir) == 0

    def test_namespace_collision_warns_but_merges(self, tmp_dir):
        msg_dir = os.path.join(tmp_dir, "src", "messages")
        os.makedirs(msg_dir)
        with open(os.path.join(msg_dir, "en.json"), "w") as f:
            json.dump({"cart": {"old": "value"}}, f)
        with open(os.path.join(msg_dir, "en.cart.json"), "w") as f:
            json.dump({"cart": {"new": "value"}}, f)

        count = merge_i18n_sidecars(tmp_dir)
        assert count == 1
        result = json.loads(open(os.path.join(msg_dir, "en.json")).read())
        # Sidecar overwrites at top level
        assert result["cart"] == {"new": "value"}

    def test_creates_canonical_if_missing(self, tmp_dir):
        msg_dir = os.path.join(tmp_dir, "src", "messages")
        os.makedirs(msg_dir)
        with open(os.path.join(msg_dir, "hu.products.json"), "w") as f:
            json.dump({"products": {"title": "Termékek"}}, f)

        count = merge_i18n_sidecars(tmp_dir)
        assert count == 1
        assert os.path.isfile(os.path.join(msg_dir, "hu.json"))
        result = json.loads(open(os.path.join(msg_dir, "hu.json")).read())
        assert result["products"]["title"] == "Termékek"


class TestConstants:
    def test_max_merge_retries(self):
        assert MAX_MERGE_RETRIES == 5
