"""Tests for Python design bridge functions in set_orch.planner."""

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.planner import _fetch_design_context


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory and chdir into it."""
    orig = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(orig)


# ─── _fetch_design_context ──────────────────────────────────────


class TestFetchDesignContext:
    def test_snapshot_in_cwd(self, tmp_project):
        """Snapshot in CWD is found."""
        (tmp_project / "design-snapshot.md").write_text(
            "## Design Tokens\n\nColors:\n- primary: #3b82f6\n"
        )
        result = _fetch_design_context()
        assert "## Design Tokens" in result
        assert "primary: #3b82f6" in result

    def test_snapshot_nested_in_docs(self, tmp_project):
        """Snapshot nested in docs/figma-raw/ is found recursively."""
        nested = tmp_project / "docs" / "figma-raw" / "ABC123"
        nested.mkdir(parents=True)
        (nested / "design-snapshot.md").write_text(
            "## Design Tokens\n\nColors:\n- accent: #10b981\n"
        )
        result = _fetch_design_context()
        assert "accent: #10b981" in result

    def test_no_snapshot_returns_empty(self, tmp_project):
        """No snapshot anywhere → empty string."""
        result = _fetch_design_context()
        assert result == ""

    def test_empty_snapshot_skipped(self, tmp_project):
        """Empty snapshot file is skipped."""
        (tmp_project / "design-snapshot.md").write_text("   \n\n  ")
        result = _fetch_design_context()
        assert result == ""

    def test_truncated_at_5000_chars(self, tmp_project):
        """Large snapshot is truncated to 5000 chars."""
        (tmp_project / "design-snapshot.md").write_text("X" * 10000)
        result = _fetch_design_context()
        assert len(result) == 5000

    def test_force_param_ignored(self, tmp_project):
        """force param is accepted but ignored (signature compat)."""
        (tmp_project / "design-snapshot.md").write_text("## Tokens\n")
        result = _fetch_design_context(force=True)
        assert "## Tokens" in result


# ─── dispatch_ready_changes threading ────────────────────────────


class TestDispatchDesignSnapshotDir:
    def test_design_snapshot_dir_passed_to_dispatch_change(self, tmp_path):
        """dispatch_ready_changes passes design_snapshot_dir to dispatch_change."""
        from set_orch.state import OrchestratorState, Change

        state_file = str(tmp_path / "state.json")
        state = OrchestratorState(
            status="running",
            changes=[Change(name="test-change", status="pending", scope="test", complexity="S")],
        )
        with open(state_file, "w") as f:
            json.dump(state.to_dict(), f)

        with patch("set_orch.dispatcher.dispatch_change") as mock_dispatch:
            from set_orch.dispatcher import dispatch_ready_changes
            dispatch_ready_changes(
                state_file, max_parallel=5,
                design_snapshot_dir="/my/project",
            )
            if mock_dispatch.called:
                _, kwargs = mock_dispatch.call_args
                assert kwargs.get("design_snapshot_dir") == "/my/project"


# ─── verifier design compliance ──────────────────────────────────


class TestVerifierDesignCompliance:
    def test_review_change_calls_bridge(self, tmp_path):
        """review_change calls build_design_review_section when design_snapshot_dir set."""
        from set_orch.verifier import review_change

        # Create a minimal worktree with a git repo
        wt_path = str(tmp_path / "wt")
        os.makedirs(wt_path)

        design_output = "## Design Compliance Check\n\nColors:\n- primary: #3b82f6\n"

        with patch("set_orch.verifier.run_git") as mock_git, \
             patch("set_orch.verifier.run_command") as mock_cmd, \
             patch("set_orch.verifier.run_claude") as mock_claude:

            # Mock merge-base
            mock_git.return_value = MagicMock(exit_code=0, stdout="abc123\n")

            # We need to handle both the template render and bridge calls
            def cmd_side_effect(cmd, **kwargs):
                cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
                if "build_design_review_section" in cmd_str:
                    return MagicMock(exit_code=0, stdout=design_output, stderr="")
                # Template render
                return MagicMock(exit_code=0, stdout="Review prompt rendered", stderr="")

            mock_cmd.side_effect = cmd_side_effect
            mock_claude.return_value = MagicMock(
                exit_code=0, stdout="PASS: All checks passed", stderr=""
            )

            rr = review_change(
                "test-change", wt_path, "Add login page",
                design_snapshot_dir="/my/project",
            )

            # Verify build_design_review_section was called
            bridge_calls = [
                c for c in mock_cmd.call_args_list
                if any("build_design_review_section" in str(a) for a in c.args)
            ]
            assert len(bridge_calls) == 1
