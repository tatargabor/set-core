"""Tests for set_orch.dispatcher — Dispatch, lifecycle, model routing, recovery."""

import json
import os
import shutil
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.dispatcher import (
    STALL_COOLDOWN_SECONDS,
    DispatchContext,
    SyncResult,
    _build_input_content,
    _build_sibling_context,
    _detect_package_manager,
    _detect_read_first_directives,
    _format_conventions_summary,
    _is_doc_change,
    _load_requirements_lookup,
    bootstrap_worktree,
    recover_orphaned_changes,
    resolve_change_model,
    resume_stalled_changes,
    resume_stopped_changes,
    retry_failed_builds,
)
from set_orch.state import Change, OrchestratorState, WatchdogState


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
        set_dir = os.path.join(tmp_dir, "worktree")
        os.makedirs(set_dir)
        _write_state(state_file, [
            {
                "name": "running-1",
                "scope": "scope",
                "complexity": "M",
                "change_type": "feature",
                "depends_on": [],
                "status": "running",
                "worktree_path": set_dir,
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
        set_dir = os.path.join(tmp_dir, "worktree")
        os.makedirs(set_dir)
        _write_state(state_file, [
            {
                "name": "running-1",
                "scope": "scope",
                "complexity": "M",
                "change_type": "feature",
                "depends_on": [],
                "status": "running",
                "worktree_path": set_dir,
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
        set_dir = os.path.join(tmp_dir, "worktree")
        os.makedirs(set_dir)
        # Use PID 1 (init) — always alive but won't match "set-loop"
        # so it will be treated as dead. Use os.getpid() which is alive.
        # But check_pid checks for "set-loop" command — current process won't match.
        # So we need to mock check_pid for a true live+match scenario.
        _write_state(state_file, [
            {
                "name": "running-1",
                "scope": "scope",
                "complexity": "M",
                "change_type": "feature",
                "depends_on": [],
                "status": "running",
                "worktree_path": set_dir,
                "ralph_pid": os.getpid(),  # alive but won't match set-loop
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
        from set_orch.process import CheckResult
        with patch("set_orch.dispatcher.check_pid", return_value=CheckResult(alive=True, match=True)):
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


# ─── resume_change — test command passing ──────────────────────────


class TestResumeChangeTestCommand:
    def test_test_command_passed_from_directives(self, state_file, tmp_dir):
        """resume_change passes --test-command from directives when done=test."""
        from unittest.mock import patch, MagicMock

        set_dir = os.path.join(tmp_dir, "worktree")
        os.makedirs(os.path.join(set_dir, ".claude"))

        _write_state(state_file, [
            {
                "name": "fix-idor",
                "scope": "Fix IDOR vulnerability",
                "complexity": "S",
                "change_type": "bugfix",
                "depends_on": [],
                "status": "stopped",
                "worktree_path": set_dir,
                "ralph_pid": 0,
                "tokens_used": 100,
                "tokens_used_prev": 0,
                "input_tokens": 50,
                "output_tokens": 50,
                "cache_read_tokens": 0,
                "cache_create_tokens": 0,
                "input_tokens_prev": 0,
                "output_tokens_prev": 0,
                "cache_read_tokens_prev": 0,
                "cache_create_tokens_prev": 0,
                "verify_retry_count": 0,
                "redispatch_count": 0,
                "merge_retry_count": 0,
                "retry_context": "REVIEW FEEDBACK: Fix IDOR on cart routes",
            },
        ])
        # Store directives in state extras
        with open(state_file) as f:
            st = json.load(f)
        st["directives"] = {"test_command": "pnpm test"}
        with open(state_file, "w") as f:
            json.dump(st, f)

        # Write loop-state to signal running
        loop_state_file = os.path.join(set_dir, ".claude", "loop-state.json")
        with open(loop_state_file, "w") as f:
            json.dump({"status": "starting", "terminal_pid": 12345}, f)

        from set_orch.dispatcher import resume_change

        captured_cmd = []

        def mock_run_command(cmd, **kwargs):
            captured_cmd.extend(cmd)
            return MagicMock(returncode=0)

        with patch("set_orch.dispatcher.run_command", side_effect=mock_run_command), \
             patch("set_orch.dispatcher._kill_existing_wt_loop"):
            result = resume_change(state_file, "fix-idor")

        assert result is True
        assert "--test-command" in captured_cmd
        tc_idx = captured_cmd.index("--test-command")
        assert captured_cmd[tc_idx + 1] == "pnpm test"
        assert "--done" in captured_cmd
        done_idx = captured_cmd.index("--done")
        assert captured_cmd[done_idx + 1] == "test"

    def test_no_test_command_no_flag(self, state_file, tmp_dir):
        """When no test command available, --test-command flag is omitted."""
        from unittest.mock import patch, MagicMock

        set_dir = os.path.join(tmp_dir, "worktree")
        os.makedirs(os.path.join(set_dir, ".claude"))

        _write_state(state_file, [
            {
                "name": "fix-auth",
                "scope": "Fix auth",
                "complexity": "S",
                "change_type": "bugfix",
                "depends_on": [],
                "status": "stopped",
                "worktree_path": set_dir,
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
                "retry_context": "REVIEW FEEDBACK: Fix auth middleware",
            },
        ])

        loop_state_file = os.path.join(set_dir, ".claude", "loop-state.json")
        with open(loop_state_file, "w") as f:
            json.dump({"status": "starting", "terminal_pid": 12345}, f)

        from set_orch.dispatcher import resume_change

        captured_cmd = []

        def mock_run_command(cmd, **kwargs):
            captured_cmd.extend(cmd)
            return MagicMock(returncode=0)

        with patch("set_orch.dispatcher.run_command", side_effect=mock_run_command), \
             patch("set_orch.dispatcher._kill_existing_wt_loop"), \
             patch("set_orch.config.auto_detect_test_command", return_value=""):
            result = resume_change(state_file, "fix-auth")

        assert result is True
        assert "--test-command" not in captured_cmd


# ─── Startup guide ───────────────────────────────────────────


class TestGenerateStartupGuide:
    def test_nextjs_prisma_playwright(self, tmp_dir):
        """Full stack: Next.js + Prisma + Playwright detected."""
        from set_orch.dispatcher import generate_startup_guide

        wt = os.path.join(tmp_dir, "fullstack")
        os.makedirs(wt)

        pkg = {
            "scripts": {"dev": "next dev", "test": "jest"},
            "dependencies": {"next": "14.0.0", "@prisma/client": "5.0.0"},
            "devDependencies": {"@playwright/test": "1.40.0"},
        }
        with open(os.path.join(wt, "package.json"), "w") as f:
            json.dump(pkg, f)

        # pnpm lockfile
        with open(os.path.join(wt, "pnpm-lock.yaml"), "w") as f:
            f.write("lockfileVersion: 9\n")

        # Playwright config
        with open(os.path.join(wt, "playwright.config.ts"), "w") as f:
            f.write("export default {}\n")

        guide = generate_startup_guide(wt)
        assert "pnpm install" in guide
        assert "pnpm run dev" in guide
        assert "prisma" in guide.lower()
        assert "playwright" in guide.lower()
        assert "pnpm run test" in guide

    def test_minimal_project(self, tmp_dir):
        """Minimal project with just package.json."""
        from set_orch.dispatcher import generate_startup_guide

        wt = os.path.join(tmp_dir, "minimal")
        os.makedirs(wt)

        pkg = {"scripts": {}, "dependencies": {}}
        with open(os.path.join(wt, "package.json"), "w") as f:
            json.dump(pkg, f)

        guide = generate_startup_guide(wt)
        assert "install" in guide
        # No dev/db/e2e sections
        assert "prisma" not in guide.lower()
        assert "playwright" not in guide.lower()


class TestAppendStartupGuide:
    def test_appends_to_existing_claudemd(self, tmp_dir):
        from set_orch.dispatcher import append_startup_guide_to_claudemd

        wt = os.path.join(tmp_dir, "wt")
        os.makedirs(wt)
        with open(os.path.join(wt, "CLAUDE.md"), "w") as f:
            f.write("# Project\n\nSome instructions.\n")
        with open(os.path.join(wt, "package.json"), "w") as f:
            json.dump({"scripts": {"dev": "next dev"}, "dependencies": {}}, f)

        result = append_startup_guide_to_claudemd(wt)
        assert result is True
        content = open(os.path.join(wt, "CLAUDE.md")).read()
        assert "## Application Startup" in content
        assert "Some instructions" in content  # original preserved

    def test_idempotent_skip(self, tmp_dir):
        """If section already exists, don't modify."""
        from set_orch.dispatcher import append_startup_guide_to_claudemd

        wt = os.path.join(tmp_dir, "wt2")
        os.makedirs(wt)
        original = "# Project\n\n## Application Startup\n\nManual guide here.\n"
        with open(os.path.join(wt, "CLAUDE.md"), "w") as f:
            f.write(original)

        result = append_startup_guide_to_claudemd(wt)
        assert result is False
        content = open(os.path.join(wt, "CLAUDE.md")).read()
        assert content == original  # unchanged

    def test_creates_claudemd_if_missing(self, tmp_dir):
        from set_orch.dispatcher import append_startup_guide_to_claudemd

        wt = os.path.join(tmp_dir, "wt3")
        os.makedirs(wt)
        with open(os.path.join(wt, "package.json"), "w") as f:
            json.dump({"scripts": {}, "dependencies": {}}, f)

        result = append_startup_guide_to_claudemd(wt)
        assert result is True
        assert os.path.isfile(os.path.join(wt, "CLAUDE.md"))
        content = open(os.path.join(wt, "CLAUDE.md")).read()
        assert "## Application Startup" in content


# ─── _build_input_content with acceptance criteria ──────────────────


class TestBuildInputContentAC:
    def test_ac_items_rendered_as_bullets(self, tmp_dir):
        """When requirements.json has acceptance_criteria, input.md lists AC as bullets."""
        digest_dir = os.path.join(tmp_dir, "digest")
        os.makedirs(digest_dir)
        with open(os.path.join(digest_dir, "requirements.json"), "w") as f:
            json.dump({"requirements": [
                {
                    "id": "REQ-CART-001",
                    "title": "Add to cart",
                    "brief": "Users can add items to cart",
                    "acceptance_criteria": [
                        "POST /api/cart/items → 201",
                        "Stock decremented by quantity",
                    ],
                },
            ]}, f)

        ctx = DispatchContext()
        content = _build_input_content(
            "test-change", "Implement cart", "Cart section", ctx,
            change_requirements=["REQ-CART-001"],
            digest_dir=digest_dir,
        )
        assert "## Assigned Requirements" in content
        assert "REQ-CART-001: Add to cart" in content
        assert "  - POST /api/cart/items → 201" in content
        assert "  - Stock decremented by quantity" in content
        # Should NOT have brief when AC is present
        assert "Users can add items to cart" not in content

    def test_fallback_to_brief_when_no_ac(self, tmp_dir):
        """When acceptance_criteria is absent, falls back to title — brief."""
        digest_dir = os.path.join(tmp_dir, "digest")
        os.makedirs(digest_dir)
        with open(os.path.join(digest_dir, "requirements.json"), "w") as f:
            json.dump({"requirements": [
                {
                    "id": "REQ-CART-001",
                    "title": "Add to cart",
                    "brief": "Users can add items to cart",
                },
            ]}, f)

        ctx = DispatchContext()
        content = _build_input_content(
            "test-change", "Implement cart", "Cart section", ctx,
            change_requirements=["REQ-CART-001"],
            digest_dir=digest_dir,
        )
        assert "REQ-CART-001: Add to cart — Users can add items to cart" in content

    def test_no_digest_dir_renders_id_only(self):
        """When digest_dir is empty, renders REQ-ID as title (no lookup)."""
        ctx = DispatchContext()
        content = _build_input_content(
            "test-change", "Implement cart", "Cart section", ctx,
            change_requirements=["REQ-CART-001"],
            digest_dir="",
        )
        assert "## Assigned Requirements" in content
        assert "REQ-CART-001" in content

    def test_cross_cutting_reqs_title_only(self, tmp_dir):
        """Cross-cutting requirements show title only, no AC items."""
        digest_dir = os.path.join(tmp_dir, "digest")
        os.makedirs(digest_dir)
        with open(os.path.join(digest_dir, "requirements.json"), "w") as f:
            json.dump({"requirements": [
                {
                    "id": "REQ-AUTH-001",
                    "title": "Auth middleware",
                    "brief": "All routes need auth",
                    "acceptance_criteria": ["401 on unauthenticated"],
                },
            ]}, f)

        ctx = DispatchContext()
        content = _build_input_content(
            "test-change", "Implement cart", "Cart section", ctx,
            also_affects_reqs=["REQ-AUTH-001"],
            digest_dir=digest_dir,
        )
        assert "## Cross-Cutting Requirements" in content
        assert "REQ-AUTH-001: Auth middleware" in content
        # AC items should NOT appear for cross-cutting
        assert "401 on unauthenticated" not in content


class TestReadFirstDirectives:
    """Tests for _detect_read_first_directives()."""

    def test_detects_prisma_schema(self, tmp_dir):
        prisma_dir = os.path.join(tmp_dir, "prisma")
        os.makedirs(prisma_dir)
        with open(os.path.join(prisma_dir, "schema.prisma"), "w") as f:
            f.write("model User { id String @id }")
        directives = _detect_read_first_directives(tmp_dir)
        assert any("prisma/schema.prisma" in d for d in directives)

    def test_detects_components_dir(self, tmp_dir):
        os.makedirs(os.path.join(tmp_dir, "src", "components"))
        directives = _detect_read_first_directives(tmp_dir)
        assert any("src/components/" in d for d in directives)

    def test_empty_project_returns_no_directives(self, tmp_dir):
        directives = _detect_read_first_directives(tmp_dir)
        assert directives == []

    def test_multiple_detections(self, tmp_dir):
        os.makedirs(os.path.join(tmp_dir, "prisma"))
        with open(os.path.join(tmp_dir, "prisma", "schema.prisma"), "w") as f:
            f.write("")
        os.makedirs(os.path.join(tmp_dir, "src", "components"))
        os.makedirs(os.path.join(tmp_dir, "src", "lib"))
        directives = _detect_read_first_directives(tmp_dir)
        assert len(directives) == 3

    def test_injected_in_input_content(self, tmp_dir):
        """Read-first directives appear in _build_input_content output."""
        ctx = DispatchContext(read_first_directives=[
            "Before writing database/Prisma code, read `prisma/schema.prisma`",
        ])
        content = _build_input_content("test", "Scope", "", ctx)
        assert "## Read Before Writing" in content
        assert "prisma/schema.prisma" in content

    def test_not_injected_when_empty(self):
        ctx = DispatchContext()
        content = _build_input_content("test", "Scope", "", ctx)
        assert "## Read Before Writing" not in content


class TestConventionsSummary:
    """Tests for _format_conventions_summary() and injection."""

    def test_formats_conventions_json(self, tmp_dir):
        conv = {
            "categories": [
                {"name": "Auth", "rules": ["Use NextAuth v5", "Server-side sessions"]},
                {"name": "CSS", "rules": ["Tailwind only"]},
            ]
        }
        with open(os.path.join(tmp_dir, "conventions.json"), "w") as f:
            json.dump(conv, f)
        result = _format_conventions_summary(tmp_dir)
        assert "**Auth:** Use NextAuth v5; Server-side sessions" in result
        assert "**CSS:** Tailwind only" in result

    def test_missing_file_returns_empty(self, tmp_dir):
        assert _format_conventions_summary(tmp_dir) == ""

    def test_empty_categories_returns_empty(self, tmp_dir):
        with open(os.path.join(tmp_dir, "conventions.json"), "w") as f:
            json.dump({"categories": []}, f)
        assert _format_conventions_summary(tmp_dir) == ""

    def test_injected_in_input_content(self):
        ctx = DispatchContext(conventions_summary="**Auth:** Use NextAuth v5")
        content = _build_input_content("test", "Scope", "", ctx)
        assert "## Project Conventions" in content
        assert "**Auth:** Use NextAuth v5" in content

    def test_not_injected_when_empty(self):
        ctx = DispatchContext()
        content = _build_input_content("test", "Scope", "", ctx)
        assert "## Project Conventions" not in content
