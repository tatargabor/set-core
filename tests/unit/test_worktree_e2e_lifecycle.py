"""Tests for worktree e2e lifecycle: port isolation + pre/post gate hooks."""

import json
import os
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest


class TestWorktreePort:
    """Test worktree_port() returns deterministic port in range."""

    def test_deterministic(self):
        from set_project_web.project_type import WebProjectType
        profile = WebProjectType()
        port1 = profile.worktree_port("contact-form")
        port2 = profile.worktree_port("contact-form")
        assert port1 == port2

    def test_in_range(self):
        from set_project_web.project_type import WebProjectType
        profile = WebProjectType()
        for name in ["a", "contact-form", "about-and-blog", "database-schema", "auth-user-accounts"]:
            port = profile.worktree_port(name)
            assert 3100 <= port <= 4099, f"port {port} out of range for {name}"

    def test_different_changes_get_different_ports(self):
        from set_project_web.project_type import WebProjectType
        profile = WebProjectType()
        ports = {profile.worktree_port(f"change-{i}") for i in range(20)}
        # With 20 changes in 1000-port range, expect at least 15 unique
        assert len(ports) >= 15

    def test_default_abc_returns_zero(self):
        from set_orch.profile_types import ProjectType, ProjectTypeInfo

        class MinimalProfile(ProjectType):
            @property
            def info(self):
                return ProjectTypeInfo(name="test", version="0.1", description="")
            def get_templates(self):
                return []

        profile = MinimalProfile()
        assert profile.worktree_port("anything") == 0


class TestBootstrapPortInjection:
    """Test bootstrap_worktree writes PORT/PW_PORT to .env."""

    def test_writes_port_to_env(self, tmp_path):
        from set_orch.dispatcher import bootstrap_worktree

        project = tmp_path / "project"
        project.mkdir()
        wt = tmp_path / "wt"
        wt.mkdir()
        (wt / ".set").mkdir()
        (wt / "package.json").write_text('{"name":"test"}')
        (wt / "node_modules").mkdir()

        with patch("set_orch.profile_loader.load_profile") as mock_load, \
             patch("set_orch.paths.SetRuntime.ensure_agent_dir"):
            profile = mock_load.return_value
            profile.worktree_port.return_value = 3247
            profile.e2e_gate_env.return_value = {"PORT": "3247", "PW_PORT": "3247"}
            profile.bootstrap_worktree.return_value = True
            # isinstance(profile, NullProfile) must be False
            profile.__class__ = type("FakeProfile", (), {})

            bootstrap_worktree(str(project), str(wt), change_name="contact-form")

        env_content = (wt / ".env").read_text()
        assert "PORT=3247" in env_content
        assert "PW_PORT=3247" in env_content

    def test_idempotent_on_rerun(self, tmp_path):
        from set_orch.dispatcher import bootstrap_worktree

        project = tmp_path / "project"
        project.mkdir()
        wt = tmp_path / "wt"
        wt.mkdir()
        (wt / ".set").mkdir()
        (wt / "package.json").write_text('{"name":"test"}')
        (wt / "node_modules").mkdir()
        (wt / ".env").write_text("DATABASE_URL=file:./dev.db\nPORT=3247\nPW_PORT=3247\n")

        with patch("set_orch.profile_loader.load_profile") as mock_load, \
             patch("set_orch.paths.SetRuntime.ensure_agent_dir"):
            profile = mock_load.return_value
            profile.worktree_port.return_value = 3247
            profile.e2e_gate_env.return_value = {"PORT": "3247", "PW_PORT": "3247"}
            profile.bootstrap_worktree.return_value = True
            profile.__class__ = type("FakeProfile", (), {})

            bootstrap_worktree(str(project), str(wt), change_name="contact-form")

        env_content = (wt / ".env").read_text()
        assert env_content.count("PORT=") == 2  # PORT and PW_PORT, each once


class TestE2ePreGate:
    """Test e2e_pre_gate runs Prisma when schema exists."""

    def test_noop_without_prisma(self, tmp_path):
        from set_project_web.project_type import WebProjectType
        profile = WebProjectType()
        assert profile.e2e_pre_gate(str(tmp_path), {}) is True

    def test_runs_prisma_push_with_schema(self, tmp_path):
        from set_project_web.project_type import WebProjectType

        prisma_dir = tmp_path / "prisma"
        prisma_dir.mkdir()
        (prisma_dir / "schema.prisma").write_text(
            'datasource db {\n  provider = "sqlite"\n  url = env("DATABASE_URL")\n}\n'
        )
        (tmp_path / ".env").write_text('DATABASE_URL="file:./dev.db"\n')

        profile = WebProjectType()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = profile.e2e_pre_gate(str(tmp_path), {})

        assert result is True
        # Should have called prisma db push
        calls = [c for c in mock_run.call_args_list
                 if "prisma" in str(c) and "push" in str(c)]
        assert len(calls) == 1

    def test_runs_seed_when_seed_file_exists(self, tmp_path):
        from set_project_web.project_type import WebProjectType

        prisma_dir = tmp_path / "prisma"
        prisma_dir.mkdir()
        (prisma_dir / "schema.prisma").write_text(
            'datasource db {\n  provider = "sqlite"\n  url = env("DATABASE_URL")\n}\n'
        )
        (prisma_dir / "seed.ts").write_text("// seed")
        (tmp_path / ".env").write_text('DATABASE_URL="file:./dev.db"\n')

        profile = WebProjectType()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            profile.e2e_pre_gate(str(tmp_path), {})

        seed_calls = [c for c in mock_run.call_args_list
                      if c.args and "seed" in c.args[0]]
        assert len(seed_calls) == 1

    def test_skips_postgres(self, tmp_path):
        from set_project_web.project_type import WebProjectType

        prisma_dir = tmp_path / "prisma"
        prisma_dir.mkdir()
        (prisma_dir / "schema.prisma").write_text(
            'datasource db {\n  provider = "postgresql"\n  url = env("DATABASE_URL")\n}\n'
        )
        (tmp_path / ".env").write_text('DATABASE_URL="postgresql://localhost/mydb"\n')

        profile = WebProjectType()
        with patch("subprocess.run") as mock_run:
            result = profile.e2e_pre_gate(str(tmp_path), {})

        assert result is True
        mock_run.assert_not_called()
