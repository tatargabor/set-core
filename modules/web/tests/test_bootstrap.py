"""Tests for WebProjectType.bootstrap_worktree() post-install hooks."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, call

import pytest

from set_project_web.project_type import WebProjectType


@pytest.fixture
def wt(tmp_path):
    """Create a minimal worktree directory with package.json and lockfile."""
    pkg = {"name": "test", "version": "1.0.0", "devDependencies": {}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    (tmp_path / "pnpm-lock.yaml").touch()
    return tmp_path


@pytest.fixture
def web():
    return WebProjectType()


class TestPrismaGenerate:
    def test_runs_when_schema_exists(self, web, wt):
        (wt / "prisma").mkdir()
        (wt / "prisma" / "schema.prisma").write_text("model User { id Int @id }")

        with patch("set_project_web.project_type.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0)
            web.bootstrap_worktree(str(wt), str(wt))

        prisma_calls = [c for c in mock_run.call_args_list if "prisma" in str(c)]
        assert len(prisma_calls) == 1
        args = prisma_calls[0]
        assert args[0][0] == ["npx", "prisma", "generate"]
        assert args[1]["timeout"] == 60

    def test_skipped_when_no_schema(self, web, wt):
        with patch("set_project_web.project_type.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0)
            web.bootstrap_worktree(str(wt), str(wt))

        prisma_calls = [c for c in mock_run.call_args_list if "prisma" in str(c)]
        assert len(prisma_calls) == 0

    def test_failure_is_non_fatal(self, web, wt):
        (wt / "prisma").mkdir()
        (wt / "prisma" / "schema.prisma").write_text("model User { id Int @id }")

        with patch("set_project_web.project_type.subprocess.run") as mock_run:
            def side_effect(*args, **kwargs):
                if "prisma" in str(args):
                    raise subprocess.TimeoutExpired(cmd="prisma", timeout=60)
                return subprocess.CompletedProcess([], 0)

            mock_run.side_effect = side_effect
            result = web.bootstrap_worktree(str(wt), str(wt))

        assert result is True  # non-fatal


class TestPlaywrightInstall:
    def test_runs_when_in_devdeps(self, web, wt):
        pkg = json.loads((wt / "package.json").read_text())
        pkg["devDependencies"]["@playwright/test"] = "^1.40.0"
        (wt / "package.json").write_text(json.dumps(pkg))

        with patch("set_project_web.project_type.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0)
            web.bootstrap_worktree(str(wt), str(wt))

        pw_calls = [c for c in mock_run.call_args_list if "playwright" in str(c)]
        assert len(pw_calls) == 1
        args = pw_calls[0]
        assert args[0][0] == ["npx", "playwright", "install", "chromium"]
        assert args[1]["timeout"] == 120

    def test_skipped_when_not_in_devdeps(self, web, wt):
        with patch("set_project_web.project_type.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0)
            web.bootstrap_worktree(str(wt), str(wt))

        pw_calls = [c for c in mock_run.call_args_list if "playwright" in str(c)]
        assert len(pw_calls) == 0

    def test_failure_is_non_fatal(self, web, wt):
        pkg = json.loads((wt / "package.json").read_text())
        pkg["devDependencies"]["@playwright/test"] = "^1.40.0"
        (wt / "package.json").write_text(json.dumps(pkg))

        with patch("set_project_web.project_type.subprocess.run") as mock_run:
            def side_effect(*args, **kwargs):
                if "playwright" in str(args):
                    raise OSError("playwright not found")
                return subprocess.CompletedProcess([], 0)

            mock_run.side_effect = side_effect
            result = web.bootstrap_worktree(str(wt), str(wt))

        assert result is True  # non-fatal


class TestBootstrapOrder:
    def test_install_then_prisma_then_playwright(self, web, wt):
        (wt / "prisma").mkdir()
        (wt / "prisma" / "schema.prisma").write_text("model User { id Int @id }")
        pkg = json.loads((wt / "package.json").read_text())
        pkg["devDependencies"]["@playwright/test"] = "^1.40.0"
        (wt / "package.json").write_text(json.dumps(pkg))

        with patch("set_project_web.project_type.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0)
            web.bootstrap_worktree(str(wt), str(wt))

        # Match by first arg of the command list
        cmds = [c[0][0] for c in mock_run.call_args_list]
        install_idx = next(i for i, cmd in enumerate(cmds) if cmd[0] == "pnpm")
        prisma_idx = next(i for i, cmd in enumerate(cmds) if cmd[0] == "npx" and "prisma" in cmd)
        pw_idx = next(i for i, cmd in enumerate(cmds) if cmd[0] == "npx" and "playwright" in cmd)
        assert install_idx < prisma_idx < pw_idx
