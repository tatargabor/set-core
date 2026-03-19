"""Tests for set_orch.paths — SetRuntime path resolution and directory creation."""

import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.paths import SetRuntime, resolve_project_name, AGENT_DIR_NAME


class TestWtRuntimePaths:
    """Test that SetRuntime generates correct paths."""

    def setup_method(self):
        self.rt = SetRuntime(project_name="test-project")

    def test_root_path(self):
        assert self.rt.root.endswith("set-core/test-project")

    def test_project_name(self):
        assert self.rt.project_name == "test-project"

    def test_state_file(self):
        assert self.rt.state_file.endswith("orchestration/state.json")
        assert "test-project" in self.rt.state_file

    def test_events_file(self):
        assert self.rt.events_file.endswith("orchestration/events.jsonl")

    def test_plans_dir(self):
        assert self.rt.plans_dir.endswith("orchestration/plans")

    def test_runs_dir(self):
        assert self.rt.runs_dir.endswith("orchestration/runs")

    def test_digest_dir(self):
        assert self.rt.digest_dir.endswith("orchestration/digest")

    def test_spec_coverage_report(self):
        assert self.rt.spec_coverage_report.endswith("orchestration/spec-coverage-report.md")

    def test_report_html(self):
        assert self.rt.report_html.endswith("orchestration/report.html")

    def test_audit_log(self):
        path = self.rt.audit_log(3)
        assert path.endswith("orchestration/audit-cycle-3.log")

    def test_sentinel_dir(self):
        assert self.rt.sentinel_dir.endswith("sentinel")

    def test_sentinel_events_file(self):
        assert self.rt.sentinel_events_file.endswith("sentinel/events.jsonl")

    def test_sentinel_findings_file(self):
        assert self.rt.sentinel_findings_file.endswith("sentinel/findings.json")

    def test_sentinel_status_file(self):
        assert self.rt.sentinel_status_file.endswith("sentinel/status.json")

    def test_sentinel_inbox_file(self):
        assert self.rt.sentinel_inbox_file.endswith("sentinel/inbox.jsonl")

    def test_sentinel_pid_file(self):
        assert self.rt.sentinel_pid_file.endswith("sentinel/sentinel.pid")

    def test_sentinel_archive_dir(self):
        assert self.rt.sentinel_archive_dir.endswith("sentinel/archive")

    def test_logs_dir(self):
        assert self.rt.logs_dir.endswith("logs")

    def test_orchestration_log(self):
        assert self.rt.orchestration_log.endswith("logs/orchestration.log")

    def test_change_logs_dir(self):
        path = self.rt.change_logs_dir("my-change")
        assert path.endswith("logs/changes/my-change")

    def test_screenshots_dir(self):
        assert self.rt.screenshots_dir.endswith("screenshots")

    def test_smoke_screenshots_dir(self):
        path = self.rt.smoke_screenshots_dir("auth-setup")
        assert path.endswith("screenshots/smoke/auth-setup")

    def test_e2e_screenshots_dir(self):
        path = self.rt.e2e_screenshots_dir(2)
        assert path.endswith("screenshots/e2e/cycle-2")

    def test_cache_dir(self):
        assert self.rt.cache_dir.endswith("cache")

    def test_codemaps_cache_dir(self):
        assert self.rt.codemaps_cache_dir.endswith("cache/codemaps")

    def test_designs_cache_dir(self):
        assert self.rt.designs_cache_dir.endswith("cache/designs")

    def test_skill_invocations_dir(self):
        assert self.rt.skill_invocations_dir.endswith("cache/skill-invocations")

    def test_last_memory_commit_file(self):
        assert self.rt.last_memory_commit_file.endswith("cache/last-memory-commit")

    def test_credentials_dir(self):
        assert self.rt.credentials_dir.endswith("cache/credentials")

    def test_design_snapshot(self):
        assert self.rt.design_snapshot.endswith("design-snapshot.md")

    def test_version_file(self):
        assert self.rt.version_file.endswith("version")


class TestWtRuntimeAgentPaths:
    """Test per-worktree agent ephemeral paths."""

    def test_agent_dir(self):
        path = SetRuntime.agent_dir("/tmp/my-worktree")
        assert path == "/tmp/my-worktree/.wt"

    def test_agent_loop_state(self):
        path = SetRuntime.agent_loop_state("/tmp/wt")
        assert path == "/tmp/wt/.set/loop-state.json"

    def test_agent_activity(self):
        path = SetRuntime.agent_activity("/tmp/wt")
        assert path == "/tmp/wt/.set/activity.json"

    def test_agent_pid_file(self):
        path = SetRuntime.agent_pid_file("/tmp/wt")
        assert path == "/tmp/wt/.set/ralph-terminal.pid"

    def test_agent_lock_file(self):
        path = SetRuntime.agent_lock_file("/tmp/wt")
        assert path == "/tmp/wt/.set/scheduled_tasks.lock"

    def test_agent_reflection(self):
        path = SetRuntime.agent_reflection("/tmp/wt")
        assert path == "/tmp/wt/.set/reflection.md"

    def test_agent_logs_dir(self):
        path = SetRuntime.agent_logs_dir("/tmp/wt")
        assert path == "/tmp/wt/.set/logs"


class TestXDGOverride:
    """Test that XDG_DATA_HOME is respected."""

    def test_custom_xdg_data_home(self, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", "/custom/data")
        # Re-import to pick up env change
        from importlib import reload
        import set_orch.paths as paths_mod
        reload(paths_mod)

        rt = paths_mod.SetRuntime(project_name="proj")
        assert rt.root == "/custom/data/set-core/proj"

        # Restore
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        reload(paths_mod)


class TestEnsureDirs:
    """Test directory creation."""

    def test_ensure_dirs_creates_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rt = SetRuntime(project_name="test-proj")
            # Override root to temp
            rt.root = os.path.join(tmpdir, "set-core", "test-proj")
            # Patch the properties that derive from root
            rt.ensure_dirs()

            assert os.path.isdir(os.path.join(rt.root, "orchestration"))
            assert os.path.isdir(os.path.join(rt.root, "orchestration", "plans"))
            assert os.path.isdir(os.path.join(rt.root, "orchestration", "runs"))
            assert os.path.isdir(os.path.join(rt.root, "orchestration", "digest"))
            assert os.path.isdir(os.path.join(rt.root, "sentinel"))
            assert os.path.isdir(os.path.join(rt.root, "sentinel", "archive"))
            assert os.path.isdir(os.path.join(rt.root, "logs"))
            assert os.path.isdir(os.path.join(rt.root, "screenshots"))
            assert os.path.isdir(os.path.join(rt.root, "cache"))
            assert os.path.isdir(os.path.join(rt.root, "cache", "codemaps"))
            assert os.path.isdir(os.path.join(rt.root, "cache", "designs"))
            assert os.path.isdir(os.path.join(rt.root, "cache", "skill-invocations"))
            assert os.path.isdir(os.path.join(rt.root, "cache", "credentials"))

    def test_ensure_dirs_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rt = SetRuntime(project_name="test-proj")
            rt.root = os.path.join(tmpdir, "set-core", "test-proj")
            rt.ensure_dirs()
            rt.ensure_dirs()  # Second call should not fail
            assert os.path.isdir(rt.orchestration_dir)

    def test_ensure_agent_dir_creates_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_path = SetRuntime.ensure_agent_dir(tmpdir)
            assert os.path.isdir(agent_path)
            assert os.path.isdir(os.path.join(agent_path, "logs"))
            # Check .gitignore was updated
            gitignore = os.path.join(tmpdir, ".gitignore")
            assert os.path.exists(gitignore)
            with open(gitignore) as f:
                assert "/.set/" in f.read()

    def test_ensure_agent_dir_gitignore_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            SetRuntime.ensure_agent_dir(tmpdir)
            SetRuntime.ensure_agent_dir(tmpdir)
            gitignore = os.path.join(tmpdir, ".gitignore")
            with open(gitignore) as f:
                content = f.read()
            assert content.count("/.set/") == 1


class TestResolveProjectName:
    """Test project name resolution from git."""

    def test_resolve_from_current_repo(self):
        # We're in a git repo (set-core), so this should return "set-core"
        name = resolve_project_name()
        assert name == "set-core"

    def test_resolve_with_explicit_path(self):
        # Pass the repo path explicitly
        name = resolve_project_name("/home/tg/code2/set-core")
        assert name == "set-core"

    def test_resolve_non_git_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            name = resolve_project_name(tmpdir)
            assert name == "_global"
