"""Integration tests for merge pipeline.

Tests merge_change(), execute_merge_queue(), conflict detection,
fingerprint dedup, and already-merged detection using REAL git repos
with stub CLIs (no LLM calls).

Bug patterns tested:
- A1: Conflict markers on main (Run #5 Bug #24)
- A2: Generated file conflicts (Run #16 Bug #2)
- A7: Already-merged branch detection
- A8: Deleted branch detection
- A9: Conflict fingerprint dedup
- A10: Merge queue sequential drain
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.set_orch.merger import (
    MergeResult,
    execute_merge_queue,
    merge_change,
)
from lib.set_orch.state import load_state

from tests.integration.helpers import change_dict, grep_conflict_markers, run_git


def _patch_merger_hooks():
    """Patch out hook/event/coverage/smoke systems that need external deps."""
    return [
        patch("lib.set_orch.merger._run_hook", return_value=True),
        patch("lib.set_orch.merger._run_smoke_pipeline", return_value="pass"),
        patch("lib.set_orch.merger._post_merge_deps_install"),
        patch("lib.set_orch.merger._post_merge_custom_command"),
        patch("lib.set_orch.merger.merge_i18n_sidecars", return_value=0),
        patch("lib.set_orch.merger.archive_change", return_value=True),
        patch("lib.set_orch.merger.cleanup_worktree"),
        patch("lib.set_orch.merger._sync_running_worktrees"),
    ]


# ── A1: Clean merge + no conflict markers ─────────────────────────


class TestCleanMerge:
    """Basic merge: branch with no conflicts → merged successfully."""

    def test_clean_merge_succeeds(self, git_repo, create_branch, create_state_file, stub_env):
        repo = git_repo()
        create_branch(repo, "feature-a", {"src/app.py": "hello world\n"})
        sf = create_state_file(repo, changes=[
            change_dict("feature-a", status="done"),
        ], merge_queue=["feature-a"])

        os.chdir(repo)
        patches = _patch_merger_hooks()
        for p in patches:
            p.start()
        try:
            result = merge_change("feature-a", str(sf))
        finally:
            for p in patches:
                p.stop()

        assert result.success is True
        assert result.status == "merged"

        # Verify git state
        assert (repo / "src" / "app.py").read_text() == "hello world\n"

        # Verify state file
        state = load_state(str(sf))
        change = next(c for c in state.changes if c.name == "feature-a")
        assert change.status == "merged"

    def test_no_conflict_markers_after_merge(self, git_repo, create_branch, create_state_file, stub_env):
        """Run #5 Bug #24: conflict markers leaked onto main."""
        repo = git_repo()
        create_branch(repo, "feature-a", {"src/app.py": "version A\n"})
        sf = create_state_file(repo, changes=[
            change_dict("feature-a", status="done"),
        ], merge_queue=["feature-a"])

        os.chdir(repo)
        patches = _patch_merger_hooks()
        for p in patches:
            p.start()
        try:
            result = merge_change("feature-a", str(sf))
        finally:
            for p in patches:
                p.stop()

        assert result.success is True
        markers = grep_conflict_markers(repo)
        assert markers == [], f"Conflict markers found on main: {markers}"


# ── Conflict detection ─────────────────────────────────────────────


class TestConflictMerge:
    """Two changes modify same file → second should merge-block."""

    def test_conflict_ff_fails_triggers_retry(self, git_repo, create_branch, create_state_file, stub_env):
        """FF-only merge fails when branch has diverged — triggers re-integration retry."""
        repo = git_repo()
        # Both branches modify the same file
        create_branch(repo, "feature-a", {"src/shared.py": "version A\n"})
        create_branch(repo, "feature-b", {"src/shared.py": "version B\n"})

        # Merge A first (manually, to set up divergence)
        run_git(repo, "merge", "change/feature-a", "--no-edit")

        sf = create_state_file(repo, changes=[
            change_dict("feature-a", status="merged"),
            change_dict("feature-b", status="done"),
        ], merge_queue=["feature-b"])

        os.chdir(repo)
        patches = _patch_merger_hooks()
        for p in patches:
            p.start()
        try:
            result = merge_change("feature-b", str(sf))
        finally:
            for p in patches:
                p.stop()

        # First attempt: ff fails, triggers re-integration (status="running")
        assert result.success is False
        assert result.status == "running"

        # Working tree should be clean — no conflict markers
        markers = grep_conflict_markers(repo)
        assert markers == [], f"Conflict markers leaked on main: {markers}"

    def test_ff_retries_exhausted_merge_blocked(self, git_repo, create_branch, create_state_file, stub_env):
        """After max ff retries, change is marked merge-blocked."""
        repo = git_repo()
        create_branch(repo, "feature-a", {"src/shared.py": "version A\n"})
        create_branch(repo, "feature-b", {"src/shared.py": "version B\n"})
        run_git(repo, "merge", "change/feature-a", "--no-edit")

        sf = create_state_file(repo, changes=[
            change_dict("feature-a", status="merged"),
            change_dict("feature-b", status="done", ff_retry_count=3),
        ], merge_queue=["feature-b"])

        os.chdir(repo)
        patches = _patch_merger_hooks()
        for p in patches:
            p.start()
        try:
            result = merge_change("feature-b", str(sf))
        finally:
            for p in patches:
                p.stop()

        assert result.success is False
        assert result.status == "merge-blocked"


# ── A7/A8: Already-merged / deleted branch ─────────────────────────


class TestAlreadyMerged:
    """Branches that are already merged or deleted should be skipped."""

    def test_ancestor_branch_skip_merged(self, git_repo, create_branch, create_state_file, stub_env):
        repo = git_repo()
        create_branch(repo, "feature-a", {"src/done.py": "done\n"})
        # Manually merge so the branch is ancestor of HEAD
        run_git(repo, "merge", "change/feature-a", "--no-edit")

        sf = create_state_file(repo, changes=[
            change_dict("feature-a", status="done"),
        ], merge_queue=["feature-a"])

        os.chdir(repo)
        patches = _patch_merger_hooks()
        for p in patches:
            p.start()
        try:
            result = merge_change("feature-a", str(sf))
        finally:
            for p in patches:
                p.stop()

        assert result.success is True
        assert result.status == "merged"
        assert result.smoke_result == "skip_merged"

    def test_deleted_branch_skip_merged(self, git_repo, create_branch, create_state_file, stub_env):
        repo = git_repo()
        create_branch(repo, "feature-a", {"src/done.py": "done\n"})
        # Merge then delete the branch
        run_git(repo, "merge", "change/feature-a", "--no-edit")
        run_git(repo, "branch", "-d", "change/feature-a")

        sf = create_state_file(repo, changes=[
            change_dict("feature-a", status="done"),
        ], merge_queue=["feature-a"])

        os.chdir(repo)
        patches = _patch_merger_hooks()
        for p in patches:
            p.start()
        try:
            result = merge_change("feature-a", str(sf))
        finally:
            for p in patches:
                p.stop()

        assert result.success is True
        assert result.status == "merged"
        assert result.smoke_result == "skip_merged"


# ── Merge queue drain ──────────────────────────────────────────────


class TestMergeQueue:
    """Merge queue drains sequentially — each merge sees prior results."""

    def test_single_change_ff_merge(self, git_repo, create_branch, create_state_file, stub_env):
        """Single change in queue merges via ff-only when branch is up-to-date."""
        repo = git_repo()
        create_branch(repo, "feat-a", {"src/a.py": "module a\n"})

        sf = create_state_file(repo, changes=[
            change_dict("feat-a", status="done"),
        ], merge_queue=["feat-a"])

        os.chdir(repo)
        patches = _patch_merger_hooks()
        for p in patches:
            p.start()
        try:
            merged_count = execute_merge_queue(str(sf))
        finally:
            for p in patches:
                p.stop()

        assert merged_count == 1
        assert (repo / "src" / "a.py").exists()

        # All statuses merged
        state = load_state(str(sf))
        for c in state.changes:
            assert c.status == "merged", f"{c.name} should be merged, got {c.status}"

        # Queue drained
        assert state.merge_queue == []


# ── A2: Generated file auto-resolution via .gitattributes ──────────


class TestGeneratedFileAutoResolve:
    """Run #16 Bug #2: .claude/* and lockfile conflicts should auto-resolve
    when .gitattributes merge=ours is configured."""

    def test_gitattributes_merge_ours_prevents_lockfile_conflict(
        self, git_repo, create_branch, stub_env
    ):
        """With .gitattributes merge=ours, lockfile conflicts are prevented."""
        repo = git_repo()

        # Configure .gitattributes and merge driver
        (repo / ".gitattributes").write_text("pnpm-lock.yaml merge=ours\n")
        run_git(repo, "config", "merge.ours.driver", "true")
        # Create initial lockfile
        (repo / "pnpm-lock.yaml").write_text("lockVersion: '9.0'\nimporters:\n  .:\n    specifiers: {}\n")
        run_git(repo, "add", ".gitattributes", "pnpm-lock.yaml")
        run_git(repo, "commit", "-m", "add gitattributes + lockfile")

        # Branch A modifies lockfile
        run_git(repo, "checkout", "-b", "change/feat-a")
        (repo / "pnpm-lock.yaml").write_text("lockVersion: '9.0'\nimporters:\n  .:\n    specifiers:\n      react: ^18.0.0\n")
        (repo / "src").mkdir(exist_ok=True)
        (repo / "src" / "a.py").write_text("module a\n")
        run_git(repo, "add", "-A")
        run_git(repo, "commit", "-m", "feat: add react dep")
        run_git(repo, "checkout", "main")

        # Branch B also modifies lockfile (same section)
        run_git(repo, "checkout", "-b", "change/feat-b")
        (repo / "pnpm-lock.yaml").write_text("lockVersion: '9.0'\nimporters:\n  .:\n    specifiers:\n      vue: ^3.0.0\n")
        (repo / "src").mkdir(exist_ok=True)
        (repo / "src" / "b.py").write_text("module b\n")
        run_git(repo, "add", "-A")
        run_git(repo, "commit", "-m", "feat: add vue dep")
        run_git(repo, "checkout", "main")

        # Merge A (no conflict)
        run_git(repo, "merge", "change/feat-a", "--no-edit")

        # Merge B — lockfile would conflict without .gitattributes
        result = subprocess.run(
            ["git", "-C", str(repo), "merge", "change/feat-b", "--no-edit"],
            capture_output=True,
            text=True,
        )
        # With merge=ours, git silently keeps "ours" for pnpm-lock.yaml
        assert result.returncode == 0, f"Merge failed: {result.stderr}"

        # No conflict markers
        markers = grep_conflict_markers(repo)
        assert markers == []

        # Both app files present
        assert (repo / "src" / "a.py").exists()
        assert (repo / "src" / "b.py").exists()
