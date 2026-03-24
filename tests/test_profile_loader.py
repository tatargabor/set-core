"""Tests for profile_loader — the bridge between project-type plugins and engine."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from set_orch.profile_loader import NullProfile, load_profile, reset_cache


@pytest.fixture(autouse=True)
def _clean_cache():
    """Reset profile cache before and after each test."""
    reset_cache()
    yield
    reset_cache()


class TestNullProfile:
    """NullProfile returns empty/no-op for all 12 methods."""

    def test_planning_rules(self):
        p = NullProfile()
        assert p.planning_rules() == ""

    def test_security_rules_paths(self):
        p = NullProfile()
        assert p.security_rules_paths(".") == []

    def test_security_checklist(self):
        p = NullProfile()
        assert p.security_checklist() == ""

    def test_generated_file_patterns(self):
        p = NullProfile()
        assert p.generated_file_patterns() == []

    def test_lockfile_pm_map(self):
        p = NullProfile()
        assert p.lockfile_pm_map() == []

    def test_detect_package_manager(self):
        p = NullProfile()
        assert p.detect_package_manager(".") is None

    def test_detect_test_command(self):
        p = NullProfile()
        assert p.detect_test_command(".") is None

    def test_detect_build_command(self):
        p = NullProfile()
        assert p.detect_build_command(".") is None

    def test_detect_dev_server(self):
        p = NullProfile()
        assert p.detect_dev_server(".") is None

    def test_bootstrap_worktree(self):
        p = NullProfile()
        assert p.bootstrap_worktree(".", ".") is True

    def test_post_merge_install(self):
        p = NullProfile()
        assert p.post_merge_install(".") is True

    def test_ignore_patterns(self):
        p = NullProfile()
        assert p.ignore_patterns() == []

    def test_info(self):
        p = NullProfile()
        assert p.info.name == "null"
        assert p.info.version == "0.0.0"


class TestLoadProfile:
    """load_profile() resolution and caching."""

    def test_no_project_type_yaml_returns_null(self, tmp_path):
        """No set/plugins/project-type.yaml → NullProfile."""
        p = load_profile(str(tmp_path))
        assert isinstance(p, NullProfile)

    def test_invalid_yaml_returns_null(self, tmp_path):
        """Invalid YAML → NullProfile (graceful)."""
        pt_dir = tmp_path / "wt" / "plugins"
        pt_dir.mkdir(parents=True)
        (pt_dir / "project-type.yaml").write_text(": : : bad yaml {{{}}")
        p = load_profile(str(tmp_path))
        assert isinstance(p, NullProfile)

    def test_empty_type_returns_null(self, tmp_path):
        """YAML with empty type → NullProfile."""
        pt_dir = tmp_path / "wt" / "plugins"
        pt_dir.mkdir(parents=True)
        (pt_dir / "project-type.yaml").write_text("type: ''\n")
        p = load_profile(str(tmp_path))
        assert isinstance(p, NullProfile)

    def test_missing_plugin_returns_null(self, tmp_path):
        """Valid YAML but plugin not installed → NullProfile."""
        pt_dir = tmp_path / "wt" / "plugins"
        pt_dir.mkdir(parents=True)
        (pt_dir / "project-type.yaml").write_text("type: nonexistent-plugin\n")
        p = load_profile(str(tmp_path))
        assert isinstance(p, NullProfile)

    def test_singleton_cache(self, tmp_path):
        """load_profile() returns same object on second call."""
        p1 = load_profile(str(tmp_path))
        p2 = load_profile(str(tmp_path))
        assert p1 is p2

    def test_reset_cache_clears(self, tmp_path):
        """reset_cache() forces reload on next call."""
        p1 = load_profile(str(tmp_path))
        reset_cache()
        p2 = load_profile(str(tmp_path))
        assert p1 is not p2
        assert isinstance(p2, NullProfile)

    def test_loads_web_profile_via_entry_points(self, tmp_path):
        """Valid yaml + installed entry_point → loads real profile."""
        pt_dir = tmp_path / "wt" / "plugins"
        pt_dir.mkdir(parents=True)
        (pt_dir / "project-type.yaml").write_text("type: web\n")

        # Only works if set-project-web is installed
        try:
            from set_project_web.project_type import WebProjectType
        except ImportError:
            pytest.skip("set-project-web not installed")

        p = load_profile(str(tmp_path))
        assert type(p).__name__ == "WebProjectType"
        assert p.info.name == "web"

    def test_default_path_resolves_cwd(self):
        """Default project_path='.' resolves to absolute path."""
        p = load_profile()  # uses "."
        assert isinstance(p, NullProfile)  # no project-type.yaml in set-core root

    def test_direct_import_fallback_when_entry_points_empty(self, tmp_path):
        """entry_points returns empty but module is importable → loads via direct import."""
        import types

        pt_dir = tmp_path / "wt" / "plugins"
        pt_dir.mkdir(parents=True)
        (pt_dir / "project-type.yaml").write_text("type: testfake\n")

        # Create a fake module with a FakeProjectType class
        fake_mod = types.ModuleType("set_project_testfake")

        class FakeProjectType:
            @property
            def info(self):
                from dataclasses import dataclass

                @dataclass
                class _Info:
                    name: str = "testfake"
                    version: str = "0.1.0"
                    description: str = "Test"

                return _Info()

        fake_mod.FakeProjectType = FakeProjectType

        with patch("importlib.metadata.entry_points", return_value=[]):
            with patch("importlib.import_module", return_value=fake_mod):
                p = load_profile(str(tmp_path))
                assert type(p).__name__ == "FakeProjectType"
                assert p.info.name == "testfake"

    def test_direct_import_fallback_import_error(self, tmp_path):
        """entry_points empty + module not importable → NullProfile."""
        pt_dir = tmp_path / "wt" / "plugins"
        pt_dir.mkdir(parents=True)
        (pt_dir / "project-type.yaml").write_text("type: nonexistent\n")

        with patch("importlib.metadata.entry_points", return_value=[]):
            with patch("importlib.import_module", side_effect=ImportError("nope")):
                p = load_profile(str(tmp_path))
                assert isinstance(p, NullProfile)


class TestNullProfileE2eDetect:
    """NullProfile.detect_e2e_command returns None."""

    def test_detect_e2e_command_returns_none(self):
        p = NullProfile()
        assert p.detect_e2e_command(".") is None


class TestNullProfileHooks:
    """NullProfile hook methods are no-ops."""

    def test_pre_dispatch_checks_returns_empty(self):
        p = NullProfile()
        assert p.pre_dispatch_checks("feature", "/any/path") == []

    def test_post_verify_hooks_returns_none(self):
        p = NullProfile()
        result = p.post_verify_hooks("change", "/any/path", [])
        assert result is None
