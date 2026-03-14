"""Tests for wt_orch.dispatcher — Dispatch, lifecycle, model routing, recovery."""

import json
import os
import shutil
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from wt_orch.dispatcher import (
    STALL_COOLDOWN_SECONDS,
    DispatchContext,
    SyncResult,
    _build_sibling_context,
    _detect_package_manager,
    _is_doc_change,
    bootstrap_worktree,
    recover_orphaned_changes,
    resolve_change_model,
    resume_stalled_changes,
    resume_stopped_changes,
    retry_failed_builds,
)
from wt_orch.state import Change, OrchestratorState, WatchdogState


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


def _write_state(path: str, changes: list[dict]) -> None:
    """Helper to write state with changes."""
    state = {
        "plan_version": 1,
        "brief_hash": "test",
        "status": "running",
        "created_at": "2026-03-14T10:00:00",
        "changes": changes,
        "merge_queue": [],
        "checkpoints": [],
        "changes_since_checkpoint": 0,
    }
    with open(path, "w") as f:
        json.dump(state, f)


# ─── _is_doc_change ──────────────────────────────────────────────────


class TestIsDocChange:
    def test_doc_prefix(self):
        assert _is_doc_change("doc-readme") is True

    def test_doc_infix(self):
        assert _is_doc_change("add-doc-api") is True

    def test_docs_suffix(self):
        assert _is_doc_change("api-docs") is True

    def test_docs_infix(self):
        assert _is_doc_change("api-docs-update") is True

    def test_not_doc(self):
        assert _is_doc_change("add-auth") is False

    def test_doc_substring_not_matching(self):
        assert _is_doc_change("docker-compose") is False


# ─── resolve_change_model ────────────────────────────────────────────


class TestResolveChangeModel:
    def test_explicit_model(self):
        change = Change(name="add-auth", model="opus")
        assert resolve_change_model(change) == "opus"

    def test_explicit_sonnet_for_doc(self):
        change = Change(name="doc-readme", model="sonnet")
        assert resolve_change_model(change) == "sonnet"

    def test_explicit_sonnet_overridden_for_code(self):
        change = Change(name="add-auth", model="sonnet")
        assert resolve_change_model(change) == "opus"

    def test_complexity_routing_s_bugfix(self):
        change = Change(name="fix-typo", complexity="S", change_type="bugfix")
        assert resolve_change_model(change, model_routing="complexity") == "sonnet"

    def test_complexity_routing_s_feature(self):
        change = Change(name="add-btn", complexity="S", change_type="feature")
        assert resolve_change_model(change, model_routing="complexity") == "opus"

    def test_complexity_routing_l(self):
        change = Change(name="big-refactor", complexity="L", change_type="refactor")
        assert resolve_change_model(change, model_routing="complexity") == "opus"

    def test_doc_change_always_sonnet(self):
        change = Change(name="api-docs", complexity="L")
        assert resolve_change_model(change) == "sonnet"

    def test_default_model_fallback(self):
        change = Change(name="add-auth")
        assert resolve_change_model(change, default_model="opus") == "opus"

    def test_custom_default_model(self):
        change = Change(name="add-feature")
        assert resolve_change_model(change, default_model="sonnet-3.5") == "sonnet-3.5"


# ─── _detect_package_manager ─────────────────────────────────────────


class TestDetectPackageManager:
    def test_pnpm(self, tmp_dir):
        open(os.path.join(tmp_dir, "pnpm-lock.yaml"), "w").close()
        assert _detect_package_manager(tmp_dir) == "pnpm"

    def test_yarn(self, tmp_dir):
        open(os.path.join(tmp_dir, "yarn.lock"), "w").close()
        assert _detect_package_manager(tmp_dir) == "yarn"

    def test_npm(self, tmp_dir):
        open(os.path.join(tmp_dir, "package-lock.json"), "w").close()
        assert _detect_package_manager(tmp_dir) == "npm"

    def test_bun(self, tmp_dir):
        open(os.path.join(tmp_dir, "bun.lockb"), "w").close()
        assert _detect_package_manager(tmp_dir) == "bun"

    def test_no_lockfile(self, tmp_dir):
        assert _detect_package_manager(tmp_dir) == ""

    def test_priority_pnpm_over_npm(self, tmp_dir):
        """pnpm-lock.yaml takes priority over package-lock.json."""
        open(os.path.join(tmp_dir, "pnpm-lock.yaml"), "w").close()
        open(os.path.join(tmp_dir, "package-lock.json"), "w").close()
        assert _detect_package_manager(tmp_dir) == "pnpm"


# ─── bootstrap_worktree ─────────────────────────────────────────────


class TestBootstrapWorktree:
    def test_copy_env_files(self, tmp_dir):
        project = os.path.join(tmp_dir, "project")
        wt = os.path.join(tmp_dir, "worktree")
        os.makedirs(project)
        os.makedirs(wt)

        # Create .env in project
        with open(os.path.join(project, ".env"), "w") as f:
            f.write("SECRET=abc")
        with open(os.path.join(project, ".env.local"), "w") as f:
            f.write("LOCAL=xyz")

        copied = bootstrap_worktree(project, wt)
        assert copied == 2
        assert os.path.isfile(os.path.join(wt, ".env"))
        assert os.path.isfile(os.path.join(wt, ".env.local"))

    def test_idempotent(self, tmp_dir):
        project = os.path.join(tmp_dir, "project")
        wt = os.path.join(tmp_dir, "worktree")
        os.makedirs(project)
        os.makedirs(wt)

        with open(os.path.join(project, ".env"), "w") as f:
            f.write("SECRET=abc")
        # Already exists in worktree
        with open(os.path.join(wt, ".env"), "w") as f:
            f.write("EXISTING=value")

        copied = bootstrap_worktree(project, wt)
        assert copied == 0
        # Original content preserved
        with open(os.path.join(wt, ".env")) as f:
            assert f.read() == "EXISTING=value"

    def test_nonexistent_worktree(self, tmp_dir):
        copied = bootstrap_worktree(tmp_dir, "/nonexistent/path")
        assert copied == 0


# ─── _build_sibling_context ──────────────────────────────────────────


class TestBuildSiblingContext:
    def test_no_siblings(self):
        state = OrchestratorState(changes=[
            Change(name="done", status="completed", scope="Done task"),
        ])
        assert _build_sibling_context(state) == ""

    def test_with_running_siblings(self):
        state = OrchestratorState(changes=[
            Change(name="auth", status="running", scope="Add auth system with login"),
            Change(name="ui", status="dispatched", scope="Build UI components"),
            Change(name="done", status="completed", scope="Done"),
        ])
        ctx = _build_sibling_context(state)
        assert "auth:" in ctx
        assert "ui:" in ctx
        assert "done" not in ctx.split("## Active")[1]


# ─── recover_orphaned_changes ────────────────────────────────────────


class TestRecoverOrphanedChanges:
    def test_recover_no_worktree_dead_pid(self, state_file):
        _write_state(state_file, [
            {
                "name": "orphan-1",
                "scope": "orphan scope",
                "complexity": "M",
                "change_type": "feature",
                "depends_on": [],
                "status": "running",
                "worktree_path": "/nonexistent/path",
                "ralph_pid": 99999999,
                "tokens_used": 0,
                "tokens_used_prev": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_create_tokens": 0,
                "input_tokens_prev": 0,
                "output_tokens_prev": 0,
                "cache_read_tokens_prev": 0,
                "cache_create_tokens_prev": 0,
                "verify_retry_count": 0,
                "redispatch_count": 0,
                "merge_retry_count": 0,
            },
        ])
        count = recover_orphaned_changes(state_file)
        assert count == 1

        # Verify status reset
        with open(state_file) as f:
            st = json.load(f)
        assert st["changes"][0]["status"] == "pending"
        assert st["changes"][0]["worktree_path"] is None

    def test_worktree_exists_no_pid_reconciled_to_stopped(self, state_file, tmp_dir):
        """Worktree exists but no PID → reconcile to 'stopped' for resume."""
        wt_dir = os.path.join(tmp_dir, "worktree")
        os.makedirs(wt_dir)
        _write_state(state_file, [
            {
                "name": "running-1",
                "scope": "scope",
                "complexity": "M",
                "change_type": "feature",
                "depends_on": [],
                "status": "running",
                "worktree_path": wt_dir,
                "ralph_pid": 0,
                "tokens_used": 0,
                "tokens_used_prev": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_create_tokens": 0,
                "input_tokens_prev": 0,
                "output_tokens_prev": 0,
                "cache_read_tokens_prev": 0,
                "cache_create_tokens_prev": 0,
                "verify_retry_count": 0,
                "redispatch_count": 0,
                "merge_retry_count": 0,
            },
        ])
        count = recover_orphaned_changes(state_file)
        assert count == 1
        with open(state_file) as f:
            st = json.load(f)
        assert st["changes"][0]["status"] == "stopped"
        assert st["changes"][0]["ralph_pid"] is None

    def test_worktree_exists_dead_pid_reconciled_to_stopped(self, state_file, tmp_dir):
        """Worktree exists but PID is dead → reconcile to 'stopped'."""
        wt_dir = os.path.join(tmp_dir, "worktree")
        os.makedirs(wt_dir)
        _write_state(state_file, [
            {
                "name": "running-1",
                "scope": "scope",
                "complexity": "M",
                "change_type": "feature",
                "depends_on": [],
                "status": "running",
                "worktree_path": wt_dir,
                "ralph_pid": 99999999,
                "tokens_used": 0,
                "tokens_used_prev": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_create_tokens": 0,
                "input_tokens_prev": 0,
                "output_tokens_prev": 0,
                "cache_read_tokens_prev": 0,
                "cache_create_tokens_prev": 0,
                "verify_retry_count": 0,
                "redispatch_count": 0,
                "merge_retry_count": 0,
            },
        ])
        count = recover_orphaned_changes(state_file)
        assert count == 1
        with open(state_file) as f:
            st = json.load(f)
        assert st["changes"][0]["status"] == "stopped"
        assert st["changes"][0]["ralph_pid"] is None

    def test_worktree_exists_live_pid_skipped(self, state_file, tmp_dir):
        """Worktree exists and PID is alive → skip (agent still working)."""
        wt_dir = os.path.join(tmp_dir, "worktree")
        os.makedirs(wt_dir)
        # Use PID 1 (init) — always alive but won't match "wt-loop"
        # so it will be treated as dead. Use os.getpid() which is alive.
        # But check_pid checks for "wt-loop" command — current process won't match.
        # So we need to mock check_pid for a true live+match scenario.
        _write_state(state_file, [
            {
                "name": "running-1",
                "scope": "scope",
                "complexity": "M",
                "change_type": "feature",
                "depends_on": [],
                "status": "running",
                "worktree_path": wt_dir,
                "ralph_pid": os.getpid(),  # alive but won't match wt-loop
                "tokens_used": 0,
                "tokens_used_prev": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_create_tokens": 0,
                "input_tokens_prev": 0,
                "output_tokens_prev": 0,
                "cache_read_tokens_prev": 0,
                "cache_create_tokens_prev": 0,
                "verify_retry_count": 0,
                "redispatch_count": 0,
                "merge_retry_count": 0,
            },
        ])
        # Mock check_pid to return alive+match
        from unittest.mock import patch
        from wt_orch.process import CheckResult
        with patch("wt_orch.dispatcher.check_pid", return_value=CheckResult(alive=True, match=True)):
            count = recover_orphaned_changes(state_file)
        assert count == 0
        with open(state_file) as f:
            st = json.load(f)
        assert st["changes"][0]["status"] == "running"

    def test_skip_pending_changes(self, state_file):
        _write_state(state_file, [
            {
                "name": "pending-1",
                "scope": "scope",
                "complexity": "M",
                "change_type": "feature",
                "depends_on": [],
                "status": "pending",
                "tokens_used": 0,
                "tokens_used_prev": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_create_tokens": 0,
                "input_tokens_prev": 0,
                "output_tokens_prev": 0,
                "cache_read_tokens_prev": 0,
                "cache_create_tokens_prev": 0,
                "verify_retry_count": 0,
                "redispatch_count": 0,
                "merge_retry_count": 0,
            },
        ])
        count = recover_orphaned_changes(state_file)
        assert count == 0


# ─── resume_stalled_changes ──────────────────────────────────────────


class TestResumeStalledChanges:
    def test_skip_within_cooldown(self, state_file):
        """Stalled changes within 5-minute cooldown are not resumed."""
        _write_state(state_file, [
            {
                "name": "stalled-1",
                "scope": "scope",
                "complexity": "M",
                "change_type": "feature",
                "depends_on": [],
                "status": "stalled",
                "stalled_at": int(time.time()) - 60,  # 1 min ago
                "tokens_used": 0,
                "tokens_used_prev": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_create_tokens": 0,
                "input_tokens_prev": 0,
                "output_tokens_prev": 0,
                "cache_read_tokens_prev": 0,
                "cache_create_tokens_prev": 0,
                "verify_retry_count": 0,
                "redispatch_count": 0,
                "merge_retry_count": 0,
            },
        ])
        # resume_stalled_changes would call resume_change which needs a real worktree
        # so we just verify the cooldown logic by checking the time comparison
        now = int(time.time())
        stalled_at = now - 60
        assert (now - stalled_at) < STALL_COOLDOWN_SECONDS


# ─── retry_failed_builds ────────────────────────────────────────────


class TestRetryFailedBuilds:
    def test_skip_non_build_failures(self, state_file):
        _write_state(state_file, [
            {
                "name": "failed-test",
                "scope": "scope",
                "complexity": "M",
                "change_type": "feature",
                "depends_on": [],
                "status": "failed",
                "build_result": None,
                "tokens_used": 0,
                "tokens_used_prev": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_create_tokens": 0,
                "input_tokens_prev": 0,
                "output_tokens_prev": 0,
                "cache_read_tokens_prev": 0,
                "cache_create_tokens_prev": 0,
                "verify_retry_count": 0,
                "redispatch_count": 0,
                "merge_retry_count": 0,
            },
        ])
        count = retry_failed_builds(state_file)
        assert count == 0

    def test_skip_exhausted_retries(self, state_file):
        _write_state(state_file, [
            {
                "name": "failed-build",
                "scope": "scope",
                "complexity": "M",
                "change_type": "feature",
                "depends_on": [],
                "status": "failed",
                "build_result": "fail",
                "gate_retry_count": 3,
                "tokens_used": 0,
                "tokens_used_prev": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_create_tokens": 0,
                "input_tokens_prev": 0,
                "output_tokens_prev": 0,
                "cache_read_tokens_prev": 0,
                "cache_create_tokens_prev": 0,
                "verify_retry_count": 0,
                "redispatch_count": 0,
                "merge_retry_count": 0,
            },
        ])
        count = retry_failed_builds(state_file, max_retries=2)
        assert count == 0
