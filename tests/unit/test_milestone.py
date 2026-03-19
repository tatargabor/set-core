"""Tests for set_orch.milestone — Worktree limit, cleanup, email."""

import json
import os
import shutil
import signal
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.milestone import (
    MILESTONE_WORKTREE_DIR,
    _enforce_max_milestone_worktrees,
    cleanup_milestone_servers,
    cleanup_milestone_worktrees,
    _detect_dev_server,
    _install_dependencies,
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
        "phases": {},
    }
    with open(path, "w") as f:
        json.dump(state, f)
    return path


class TestEnforceMaxMilestoneWorktrees:
    def test_no_dir_exists(self, state_file):
        """No-op when milestone dir doesn't exist."""
        _enforce_max_milestone_worktrees(3, state_file)

    def test_under_limit(self, tmp_dir, state_file):
        """No removal when under limit."""
        orig_cwd = os.getcwd()
        try:
            os.chdir(tmp_dir)
            ms_dir = MILESTONE_WORKTREE_DIR
            os.makedirs(os.path.join(ms_dir, "phase-1"))
            _enforce_max_milestone_worktrees(3, state_file)
            assert os.path.isdir(os.path.join(ms_dir, "phase-1"))
        finally:
            os.chdir(orig_cwd)


class TestCleanupMilestoneServers:
    def test_no_state_file(self, tmp_dir):
        """Returns 0 when state file doesn't exist."""
        result = cleanup_milestone_servers(os.path.join(tmp_dir, "nonexistent.json"))
        assert result == 0

    def test_no_phases(self, state_file):
        """Returns 0 when no phases in state."""
        result = cleanup_milestone_servers(state_file)
        assert result == 0

    def test_with_dead_pid(self, state_file, tmp_dir):
        """Handles already-dead PIDs gracefully."""
        with open(state_file, "r") as f:
            state = json.load(f)
        state["phases"] = {"1": {"server_pid": 999999, "server_port": 3101}}
        with open(state_file, "w") as f:
            json.dump(state, f)

        # PID 999999 is almost certainly not alive
        result = cleanup_milestone_servers(state_file)
        assert result == 0


class TestCleanupMilestoneWorktrees:
    def test_no_dir(self):
        """Returns 0 when milestone dir doesn't exist."""
        orig_cwd = os.getcwd()
        d = tempfile.mkdtemp()
        try:
            os.chdir(d)
            result = cleanup_milestone_worktrees()
            assert result == 0
        finally:
            os.chdir(orig_cwd)
            shutil.rmtree(d, ignore_errors=True)


class TestDetectDevServer:
    def test_explicit_command(self, tmp_dir, state_file):
        """Returns explicit command when provided."""
        result = _detect_dev_server(tmp_dir, "npm run dev", state_file)
        assert result == "npm run dev"

    def test_from_state_directives(self, tmp_dir, state_file):
        """Falls back to state directive."""
        with open(state_file, "r") as f:
            state = json.load(f)
        state["directives"] = {"smoke_dev_server_command": "pnpm dev"}
        with open(state_file, "w") as f:
            json.dump(state, f)

        result = _detect_dev_server(tmp_dir, "", state_file)
        assert result == "pnpm dev"

    def test_auto_detect_npm(self, tmp_dir, state_file):
        """Auto-detects npm run dev from package.json."""
        pkg = {"scripts": {"dev": "next dev"}}
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            json.dump(pkg, f)

        result = _detect_dev_server(tmp_dir, "", state_file)
        assert result == "npm run dev"

    def test_auto_detect_pnpm(self, tmp_dir, state_file):
        """Auto-detects pnpm when lock file exists."""
        pkg = {"scripts": {"dev": "next dev"}}
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            json.dump(pkg, f)
        with open(os.path.join(tmp_dir, "pnpm-lock.yaml"), "w") as f:
            f.write("")

        result = _detect_dev_server(tmp_dir, "", state_file)
        assert result == "pnpm run dev"

    def test_no_dev_script(self, tmp_dir, state_file):
        """Returns empty when no dev script in package.json."""
        pkg = {"scripts": {"build": "next build"}}
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            json.dump(pkg, f)

        result = _detect_dev_server(tmp_dir, "", state_file)
        assert result == ""

    def test_no_package_json(self, tmp_dir, state_file):
        """Returns empty when no package.json."""
        result = _detect_dev_server(tmp_dir, "", state_file)
        assert result == ""


class TestConstants:
    def test_milestone_dir(self):
        assert MILESTONE_WORKTREE_DIR == ".claude/milestones"
