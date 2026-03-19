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
        """No wt/plugins/project-type.yaml → NullProfile."""
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
            from wt_project_web.project_type import WebProjectType
        except ImportError:
            pytest.skip("set-project-web not installed")

        p = load_profile(str(tmp_path))
        assert type(p).__name__ == "WebProjectType"
        assert p.info.name == "web"

    def test_default_path_resolves_cwd(self):
        """Default project_path='.' resolves to absolute path."""
        p = load_profile()  # uses "."
        assert isinstance(p, NullProfile)  # no project-type.yaml in set-core root
