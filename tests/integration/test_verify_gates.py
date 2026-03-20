"""Integration tests for verify gate logic.

Tests dirty worktree handling, framework noise filtering,
verify exception recovery, and post-merge sync ordering.

Bug patterns tested:
- B2: node_modules dirty → verify exhaustion (Run #17 Bug #37)
- B3: Untracked files auto-commit (Run #1 Bug #6)
- B4: Verify stuck in "verifying" (Run #1 Bug #8, Run #3 Bug #14)
- A6: Post-merge sync ordering (Run #17 Bug #38)
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from lib.set_orch.git_utils import git_has_uncommitted_work
from lib.set_orch.merger import merge_change
from lib.set_orch.state import load_state

from tests.integration.helpers import change_dict, run_git


# ── B2: node_modules ignored in dirty check ───────────────────────


class TestFrameworkNoiseDirtyCheck:
    """Run #17 Bug #37: node_modules/ modifications caused ALL 11 changes
    to exhaust verify retries, requiring manual merge for every single one.
    """

    def test_node_modules_ignored(self, git_repo):
        """Modified files in node_modules/ should NOT count as dirty."""
        repo = git_repo()
        # Simulate pnpm install modifying symlinks
        nm = repo / "node_modules" / ".bin"
        nm.mkdir(parents=True)
        (nm / "react-scripts").write_text("#!/bin/bash\n")
        run_git(repo, "add", "-A")
        run_git(repo, "commit", "-m", "add node_modules")
        # Now modify it (as pnpm install would)
        (nm / "react-scripts").write_text("#!/bin/bash\n# updated")

        has_work, summary = git_has_uncommitted_work(str(repo))
        assert has_work is False, f"node_modules should be ignored, got: {summary}"

    def test_coverage_ignored(self, git_repo):
        """coverage/ directory should be ignored in dirty check."""
        repo = git_repo()
        cov = repo / "coverage"
        cov.mkdir()
        (cov / "lcov.info").write_text("TN:\n")
        run_git(repo, "add", "-A")
        run_git(repo, "commit", "-m", "add coverage")
        (cov / "lcov.info").write_text("TN:\nSF:src/app.ts\n")

        has_work, summary = git_has_uncommitted_work(str(repo))
        assert has_work is False, f"coverage/ should be ignored, got: {summary}"

    def test_claude_dir_ignored(self, git_repo):
        """.claude/ runtime files should be ignored."""
        repo = git_repo()
        claude_dir = repo / ".claude"
        claude_dir.mkdir()
        (claude_dir / "activity.json").write_text("{}")
        run_git(repo, "add", "-A")
        run_git(repo, "commit", "-m", "add .claude")
        (claude_dir / "activity.json").write_text('{"last": "now"}')

        has_work, summary = git_has_uncommitted_work(str(repo))
        assert has_work is False, f".claude/ should be ignored, got: {summary}"

    def test_real_app_changes_detected(self, git_repo):
        """Actual application file changes SHOULD be detected."""
        repo = git_repo()
        (repo / "src").mkdir()
        (repo / "src" / "app.py").write_text("v1\n")
        run_git(repo, "add", "-A")
        run_git(repo, "commit", "-m", "add app")
        (repo / "src" / "app.py").write_text("v2\n")

        has_work, summary = git_has_uncommitted_work(str(repo))
        assert has_work is True
        assert "modified" in summary

    def test_untracked_app_files_detected(self, git_repo):
        """Untracked application files SHOULD be detected."""
        repo = git_repo()
        (repo / "src").mkdir()
        (repo / "src" / "new_file.py").write_text("new\n")

        has_work, summary = git_has_uncommitted_work(str(repo))
        assert has_work is True
        assert "untracked" in summary

    def test_mixed_noise_and_real(self, git_repo):
        """Real changes detected even when framework noise is present."""
        repo = git_repo()
        # Framework noise
        (repo / ".claude").mkdir()
        (repo / ".claude" / "loop-state.json").write_text("{}")
        # Real change
        (repo / "src").mkdir()
        (repo / "src" / "app.py").write_text("real change\n")
        run_git(repo, "add", "-A")
        run_git(repo, "commit", "-m", "add files")

        # Modify both
        (repo / ".claude" / "loop-state.json").write_text('{"iter": 5}')
        (repo / "src" / "app.py").write_text("real change v2\n")

        has_work, summary = git_has_uncommitted_work(str(repo))
        assert has_work is True
        assert "1 modified" in summary  # only src/app.py, not .claude/


# ── B3: Untracked files detection ──────────────────────────────────


class TestUntrackedFiles:
    """Run #1 Bug #6: agent creates .eslintignore but doesn't git add.
    Verify gate should detect and report untracked app files.
    """

    def test_untracked_eslintignore_detected(self, git_repo):
        repo = git_repo()
        (repo / ".eslintignore").write_text("node_modules\n")

        has_work, summary = git_has_uncommitted_work(str(repo))
        assert has_work is True
        assert "untracked" in summary

    def test_untracked_openspec_changes_ignored(self, git_repo):
        """openspec/changes/ tracked-then-modified files are framework noise."""
        repo = git_repo()
        oc = repo / "openspec" / "changes" / "test"
        oc.mkdir(parents=True)
        (oc / "proposal.md").write_text("# Proposal\n")
        run_git(repo, "add", "-A")
        run_git(repo, "commit", "-m", "add openspec changes")
        # Now modify (as agent would during apply)
        (oc / "proposal.md").write_text("# Proposal v2\n")

        has_work, summary = git_has_uncommitted_work(str(repo))
        assert has_work is False


# ── A6: Post-merge sync ordering ──────────────────────────────────


class TestPostMergeSyncOrdering:
    """Run #17 Bug #38: _sync_running_worktrees() called BEFORE
    archive_change(), so worktrees synced stale state.
    Verify the correct ordering in merger.py source code.
    """

    def test_sync_called_after_archive_in_source(self):
        """Verify that in merge_change(), archive happens before sync.
        This is a source-level assertion — catches regressions of Bug #38.
        """
        import inspect
        from lib.set_orch import merger

        source = inspect.getsource(merger.merge_change)

        # Find line numbers of key operations
        lines = source.splitlines()
        archive_line = None
        sync_line = None
        for i, line in enumerate(lines):
            if "archive_change(" in line and "import" not in line:
                archive_line = i
            if "_sync_running_worktrees(" in line and "import" not in line:
                sync_line = i

        assert archive_line is not None, "archive_change() call not found in merge_change()"
        assert sync_line is not None, "_sync_running_worktrees() call not found in merge_change()"
        assert archive_line < sync_line, (
            f"archive_change() (line {archive_line}) must be called BEFORE "
            f"_sync_running_worktrees() (line {sync_line}) — Bug #38 regression"
        )

    def test_sync_after_archive_mock_ordering(self, git_repo, create_branch, create_state_file, stub_env):
        """Verify call ordering via mock — archive before sync."""
        import os
        repo = git_repo()
        create_branch(repo, "feat-a", {"src/a.py": "a\n"})
        sf = create_state_file(repo, changes=[
            change_dict("feat-a", status="done"),
        ], merge_queue=["feat-a"])

        os.chdir(repo)
        call_order = []

        def track_archive(*args, **kwargs):
            call_order.append("archive")
            return True

        def track_sync(*args, **kwargs):
            call_order.append("sync")
            return 0

        with patch("lib.set_orch.merger._run_hook", return_value=True), \
             patch("lib.set_orch.merger._run_smoke_pipeline", return_value="pass"), \
             patch("lib.set_orch.merger._post_merge_build_check", return_value=True), \
             patch("lib.set_orch.merger._post_merge_deps_install"), \
             patch("lib.set_orch.merger._post_merge_custom_command"), \
             patch("lib.set_orch.merger.merge_i18n_sidecars", return_value=0), \
             patch("lib.set_orch.merger.archive_change", side_effect=track_archive), \
             patch("lib.set_orch.merger.cleanup_worktree"), \
             patch("lib.set_orch.merger._sync_running_worktrees", side_effect=track_sync):
            result = merge_change("feat-a", str(sf))

        assert result.success is True
        assert call_order.index("archive") < call_order.index("sync"), (
            f"archive must be called before sync, got order: {call_order}"
        )
