"""Tests for set_orch.builder — PM detection, build command detection, caching."""

import json
import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.builder import (
    BuildResult,
    check_base_build,
    reset_build_cache,
    _detect_pm,
    _detect_build_cmd,
    _build_cache,
)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(autouse=True)
def clean_cache():
    """Reset build cache before each test."""
    reset_build_cache()
    yield
    reset_build_cache()


# ─── _detect_pm ──────────────────────────────────────────────────


class TestDetectPM:
    def test_bun_lockb(self, tmp_dir):
        open(os.path.join(tmp_dir, "bun.lockb"), "w").close()
        assert _detect_pm(tmp_dir) == "bun"

    def test_bun_lock(self, tmp_dir):
        open(os.path.join(tmp_dir, "bun.lock"), "w").close()
        assert _detect_pm(tmp_dir) == "bun"

    def test_pnpm(self, tmp_dir):
        open(os.path.join(tmp_dir, "pnpm-lock.yaml"), "w").close()
        assert _detect_pm(tmp_dir) == "pnpm"

    def test_yarn(self, tmp_dir):
        open(os.path.join(tmp_dir, "yarn.lock"), "w").close()
        assert _detect_pm(tmp_dir) == "yarn"

    def test_npm_default(self, tmp_dir):
        assert _detect_pm(tmp_dir) == "npm"

    def test_bun_takes_precedence(self, tmp_dir):
        """bun.lockb wins over yarn.lock."""
        open(os.path.join(tmp_dir, "bun.lockb"), "w").close()
        open(os.path.join(tmp_dir, "yarn.lock"), "w").close()
        assert _detect_pm(tmp_dir) == "bun"


# ─── _detect_build_cmd ──────────────────────────────────────────


class TestDetectBuildCmd:
    def test_no_package_json(self, tmp_dir):
        assert _detect_build_cmd(tmp_dir) == ""

    def test_build_ci_preferred(self, tmp_dir):
        pkg = {"scripts": {"build": "tsc", "build:ci": "tsc --noEmit"}}
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            json.dump(pkg, f)
        assert _detect_build_cmd(tmp_dir) == "build:ci"

    def test_build_fallback(self, tmp_dir):
        pkg = {"scripts": {"build": "tsc", "test": "jest"}}
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            json.dump(pkg, f)
        assert _detect_build_cmd(tmp_dir) == "build"

    def test_no_build_script(self, tmp_dir):
        pkg = {"scripts": {"test": "jest", "lint": "eslint"}}
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            json.dump(pkg, f)
        assert _detect_build_cmd(tmp_dir) == ""

    def test_invalid_json(self, tmp_dir):
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            f.write("not json")
        assert _detect_build_cmd(tmp_dir) == ""

    def test_no_scripts_key(self, tmp_dir):
        pkg = {"name": "my-app", "version": "1.0.0"}
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            json.dump(pkg, f)
        assert _detect_build_cmd(tmp_dir) == ""


# ─── check_base_build caching ───────────────────────────────────


class TestCheckBaseBuildCaching:
    def test_skip_when_no_build_cmd(self, tmp_dir):
        """No package.json → skip."""
        result = check_base_build(tmp_dir)
        assert result.status == "skip"

    def test_cached_pass_returns_immediately(self, tmp_dir):
        """After a pass, subsequent calls return cached pass."""
        _build_cache["status"] = "pass"
        result = check_base_build(tmp_dir)
        assert result.status == "pass"

    def test_cached_fail_returns_with_output(self, tmp_dir):
        _build_cache["status"] = "fail"
        _build_cache["output"] = "some error"
        result = check_base_build(tmp_dir)
        assert result.status == "fail"
        assert result.output == "some error"


# ─── BuildResult dataclass ──────────────────────────────────────


class TestBuildResult:
    def test_defaults(self):
        r = BuildResult(status="pass")
        assert r.output == ""
        assert r.package_manager == ""

    def test_with_values(self):
        r = BuildResult(status="fail", output="error", package_manager="bun")
        assert r.status == "fail"
        assert r.output == "error"
        assert r.package_manager == "bun"


# ─── config.py: detect_package_manager, detect_dev_server ───────
# These were added to config.py as part of the same phase


class TestConfigDetectPackageManager:
    """Tests for config.py:detect_package_manager (migrated from server-detect.sh)."""

    def test_detect_bun(self, tmp_dir):
        from set_orch.config import detect_package_manager

        open(os.path.join(tmp_dir, "bun.lockb"), "w").close()
        assert detect_package_manager(tmp_dir) == "bun"

    def test_detect_pip(self, tmp_dir):
        from set_orch.config import detect_package_manager

        open(os.path.join(tmp_dir, "Pipfile.lock"), "w").close()
        assert detect_package_manager(tmp_dir) == "pip"

    def test_detect_poetry(self, tmp_dir):
        from set_orch.config import detect_package_manager

        open(os.path.join(tmp_dir, "poetry.lock"), "w").close()
        assert detect_package_manager(tmp_dir) == "poetry"

    def test_detect_npm_default(self, tmp_dir):
        from set_orch.config import detect_package_manager

        assert detect_package_manager(tmp_dir) == "npm"


class TestConfigDetectDevServer:
    """Tests for config.py:detect_dev_server cascade."""

    def test_milestone_override(self, tmp_dir):
        from set_orch.config import detect_dev_server

        result = detect_dev_server(
            tmp_dir,
            milestone_dev_server="http://localhost:4000",
        )
        assert result == "http://localhost:4000"

    def test_smoke_command(self, tmp_dir):
        from set_orch.config import detect_dev_server

        result = detect_dev_server(
            tmp_dir,
            smoke_dev_server_command="npm run dev",
        )
        assert result == "npm run dev"

    def test_package_json_dev_script(self, tmp_dir):
        from set_orch.config import detect_dev_server

        pkg = {"scripts": {"dev": "next dev -p 3000"}}
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            json.dump(pkg, f)

        result = detect_dev_server(tmp_dir)
        assert result == "npm run dev"

    def test_no_detection(self, tmp_dir):
        from set_orch.config import detect_dev_server

        result = detect_dev_server(tmp_dir)
        assert result is None
