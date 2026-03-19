"""Tests for merge-generated-file-regen: lockfile conflict handling in merger and dispatcher."""

import json
import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from unittest.mock import MagicMock, patch

from set_orch.merger import _post_merge_deps_install
from set_orch.dispatcher import SyncResult
from set_orch.profile_loader import reset_cache as reset_profile_cache


@pytest.fixture(autouse=True)
def _reset_profile():
    """Reset profile cache before each test."""
    reset_profile_cache()
    yield
    reset_profile_cache()


# ─── _post_merge_deps_install with lockfile_conflicted ─────────────


class TestPostMergeDepsInstallLockfileConflicted:
    """Task 5.3: verify install runs unconditionally when lockfile_conflicted=True."""

    @patch("set_orch.merger.run_command")
    @patch("set_orch.profile_loader.load_profile")
    def test_lockfile_conflicted_skips_diff_check(self, mock_load_profile, mock_run):
        """When lockfile_conflicted=True, install runs without checking package.json diff."""
        from set_orch.profile_loader import NullProfile

        mock_load_profile.return_value = NullProfile()

        # Create a temp dir with a lockfile so the legacy fallback detects a PM
        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile = os.path.join(tmpdir, "pnpm-lock.yaml")
            open(lockfile, "w").close()

            orig_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                mock_run.return_value = MagicMock(exit_code=0, stdout="")

                _post_merge_deps_install(lockfile_conflicted=True)

                # Should NOT have called git diff (the package.json check)
                diff_calls = [
                    c for c in mock_run.call_args_list
                    if any("diff" in str(a) for a in c.args[0]) if c.args
                ]
                assert len(diff_calls) == 0, "Should skip git diff check when lockfile_conflicted=True"

                # Should have called install
                install_calls = [
                    c for c in mock_run.call_args_list
                    if c.args and "install" in str(c.args[0])
                ]
                assert len(install_calls) > 0, "Should run install when lockfile_conflicted=True"
            finally:
                os.chdir(orig_cwd)

    @patch("set_orch.merger.run_command")
    @patch("set_orch.profile_loader.load_profile")
    def test_no_lockfile_conflict_checks_diff(self, mock_load_profile, mock_run):
        """When lockfile_conflicted=False (default), check package.json in diff."""
        from set_orch.profile_loader import NullProfile

        mock_load_profile.return_value = NullProfile()

        # Simulate no package.json change
        mock_run.return_value = MagicMock(exit_code=0, stdout="src/index.ts\n")

        _post_merge_deps_install(lockfile_conflicted=False)

        # Should have called git diff
        diff_calls = [
            c for c in mock_run.call_args_list
            if c.args and any("diff" in str(a) for a in c.args[0])
        ]
        assert len(diff_calls) == 1, "Should check git diff when lockfile_conflicted=False"

        # Should NOT have called install (package.json not in diff)
        install_calls = [
            c for c in mock_run.call_args_list
            if c.args and c.args[0][0] in ("pnpm", "yarn", "npm")
        ]
        assert len(install_calls) == 0, "Should not install when package.json not changed"

    @patch("set_orch.merger.run_command")
    @patch("set_orch.profile_loader.load_profile")
    def test_lockfile_conflicted_with_profile(self, mock_load_profile, mock_run):
        """When lockfile_conflicted=True and profile is loaded, use profile.post_merge_install()."""
        mock_profile_inst = MagicMock()

        mock_load_profile.return_value = mock_profile_inst

        _post_merge_deps_install(lockfile_conflicted=True)

        mock_profile_inst.post_merge_install.assert_called_once_with(".")


# ─── SyncResult lockfile_regenerated field ───────────────────────────


class TestSyncResultLockfileRegenerated:
    """Task 4.3: SyncResult includes lockfile_regenerated field."""

    def test_default_false(self):
        r = SyncResult(ok=True, message="merged")
        assert r.lockfile_regenerated is False

    def test_set_true(self):
        r = SyncResult(ok=True, message="auto-resolved", auto_resolved=True, lockfile_regenerated=True)
        assert r.lockfile_regenerated is True
        assert r.auto_resolved is True


# ─── sync_worktree_with_main lock file regeneration ──────────────────


class TestSyncWorktreeLockfileRegen:
    """Task 5.4: unit test for sync_worktree_with_main() lock file regeneration path."""

    @patch("set_orch.dispatcher.run_command")
    @patch("set_orch.dispatcher.run_git")
    def test_lockfile_conflict_triggers_regeneration(self, mock_run_git, mock_run_cmd):
        """When sync encounters a lockfile conflict, it should regenerate via install."""
        from set_orch.dispatcher import sync_worktree_with_main
        from set_orch.profile_loader import NullProfile

        wt_path = "/fake/worktree"

        # Setup mock responses for the sync flow:
        # 1. show-ref main -> success
        # 2. show-ref master -> not needed (main found)
        # 3. rev-parse HEAD -> wt branch
        # 4. rev-parse main -> main sha
        # 5. merge-base -> merge_base sha
        # 6. rev-list --count -> behind count
        # 7. merge main -> conflict (exit 1)
        # 8. diff --name-only --diff-filter=U -> conflicted files
        # 9-10. checkout --ours + add for each file
        # 11. install command
        # 12. add regenerated file
        # 13. commit

        call_count = {"n": 0}

        def git_side_effect(*args, **kwargs):
            call_count["n"] += 1
            cmd = args[0] if args else kwargs.get("args", [""])[0]

            result = MagicMock()
            result.exit_code = 0
            result.stdout = ""

            # Map based on first git arg
            if cmd == "show-ref":
                # First call for "main" branch
                result.exit_code = 0
            elif cmd == "rev-parse":
                if "--abbrev-ref" in args:
                    result.stdout = "change/test-feature"
                else:
                    result.stdout = "abc123"
            elif cmd == "merge-base":
                result.stdout = "base123"
            elif cmd == "rev-list":
                result.stdout = "3"
            elif cmd == "merge":
                if "--abort" not in args:
                    result.exit_code = 1  # merge conflict
            elif cmd == "diff":
                result.stdout = "pnpm-lock.yaml\n"
            elif cmd == "checkout":
                pass  # success
            elif cmd == "add":
                pass  # success
            elif cmd == "commit":
                pass  # success

            return result

        mock_run_git.side_effect = git_side_effect

        # Mock install command
        mock_run_cmd.return_value = MagicMock(exit_code=0)

        with patch("set_orch.profile_loader.load_profile", return_value=NullProfile()):
            result = sync_worktree_with_main(wt_path, "test-feature")

        assert result.ok is True
        assert result.auto_resolved is True
        assert result.lockfile_regenerated is True

        # Verify install was called
        install_calls = [
            c for c in mock_run_cmd.call_args_list
            if c.args and "install" in str(c.args[0])
        ]
        assert len(install_calls) > 0, "Should have called install command for lock file"

    @patch("set_orch.dispatcher.run_command")
    @patch("set_orch.dispatcher.run_git")
    def test_non_lockfile_conflict_no_regeneration(self, mock_run_git, mock_run_cmd):
        """When sync encounters only non-lockfile generated conflicts, no regeneration."""
        from set_orch.dispatcher import sync_worktree_with_main
        from set_orch.profile_loader import NullProfile

        wt_path = "/fake/worktree"

        def git_side_effect(*args, **kwargs):
            result = MagicMock()
            result.exit_code = 0
            result.stdout = ""

            cmd = args[0] if args else ""
            if cmd == "rev-parse":
                if "--abbrev-ref" in args:
                    result.stdout = "change/test-feature"
                else:
                    result.stdout = "abc123"
            elif cmd == "merge-base":
                result.stdout = "base123"
            elif cmd == "rev-list":
                result.stdout = "2"
            elif cmd == "merge":
                if "--abort" not in args:
                    result.exit_code = 1
            elif cmd == "diff":
                result.stdout = ".tsbuildinfo\n"  # generated but not a lockfile

            return result

        mock_run_git.side_effect = git_side_effect

        with patch("set_orch.profile_loader.load_profile", return_value=NullProfile()):
            result = sync_worktree_with_main(wt_path, "test-feature")

        assert result.ok is True
        assert result.auto_resolved is True
        assert result.lockfile_regenerated is False

        # Verify no install was called
        assert mock_run_cmd.call_count == 0, "Should not call install for non-lockfile conflicts"


# ─── Integration test: LOCKFILE_CONFLICTED marker parsing ───────────


class TestLockfileConflictedMarkerParsing:
    """Task 5.5: verify LOCKFILE_CONFLICTED markers are parsed from set-merge output."""

    def test_parse_single_marker(self):
        """Parse a single LOCKFILE_CONFLICTED marker from merge output."""
        stdout = (
            "INFO: Pre-merge: cleaned runtime files\n"
            "LOCKFILE_CONFLICTED=pnpm-lock.yaml\n"
            "INFO: Auto-resolved generated file conflicts\n"
            "INFO: Merge completed successfully\n"
        )

        lockfile_conflicted = False
        conflicted_files = []
        for line in stdout.splitlines():
            if line.startswith("LOCKFILE_CONFLICTED="):
                lockfile_conflicted = True
                conflicted_files.append(line.split("=", 1)[1])

        assert lockfile_conflicted is True
        assert conflicted_files == ["pnpm-lock.yaml"]

    def test_parse_multiple_markers(self):
        """Parse multiple LOCKFILE_CONFLICTED markers (monorepo scenario)."""
        stdout = (
            "LOCKFILE_CONFLICTED=pnpm-lock.yaml\n"
            "LOCKFILE_CONFLICTED=packages/api/yarn.lock\n"
            "INFO: Merge completed successfully\n"
        )

        conflicted_files = []
        for line in stdout.splitlines():
            if line.startswith("LOCKFILE_CONFLICTED="):
                conflicted_files.append(line.split("=", 1)[1])

        assert len(conflicted_files) == 2
        assert "pnpm-lock.yaml" in conflicted_files
        assert "packages/api/yarn.lock" in conflicted_files

    def test_no_markers_when_no_lockfile_conflict(self):
        """No LOCKFILE_CONFLICTED markers when only non-lockfile conflicts resolved."""
        stdout = (
            "INFO: Auto-resolved generated file conflicts: tsconfig.tsbuildinfo\n"
            "INFO: Merge completed successfully\n"
        )

        lockfile_conflicted = False
        for line in stdout.splitlines():
            if line.startswith("LOCKFILE_CONFLICTED="):
                lockfile_conflicted = True

        assert lockfile_conflicted is False
