"""Tests for arch-cleanup-pre-model-config: ProjectType architecture hooks.

Covers:
  - detect_test_framework (vitest/jest/mocha glob detection)
  - detect_schema_provider (prisma/schema.prisma)
  - get_design_globals_path (v0-export/app/globals.css; shadcn/globals.css fallback)
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "modules", "web"))

from set_orch.profile_loader import CoreProfile
from set_project_web.project_type import WebProjectType


# ─── CoreProfile defaults ────────────────────────────────────────


def test_core_profile_detect_test_framework_returns_none(tmp_path):
    assert CoreProfile().detect_test_framework(tmp_path) is None


def test_core_profile_detect_schema_provider_returns_none(tmp_path):
    assert CoreProfile().detect_schema_provider(tmp_path) is None


def test_core_profile_get_design_globals_path_returns_none(tmp_path):
    assert CoreProfile().get_design_globals_path(tmp_path) is None


def test_core_profile_returns_none_even_with_web_files_present(tmp_path):
    """Core profile is stack-agnostic — it doesn't activate even if web
    config files happen to be in the directory."""
    (tmp_path / "vitest.config.ts").write_text("")
    (tmp_path / "prisma").mkdir()
    (tmp_path / "prisma" / "schema.prisma").write_text("")
    (tmp_path / "v0-export" / "app").mkdir(parents=True)
    (tmp_path / "v0-export" / "app" / "globals.css").write_text("")
    p = CoreProfile()
    assert p.detect_test_framework(tmp_path) is None
    assert p.detect_schema_provider(tmp_path) is None
    assert p.get_design_globals_path(tmp_path) is None


# ─── WebProjectType — test framework detection ───────────────────


def test_web_detect_test_framework_vitest_ts(tmp_path):
    (tmp_path / "vitest.config.ts").write_text("")
    assert WebProjectType().detect_test_framework(tmp_path) == "vitest"


def test_web_detect_test_framework_vitest_mts(tmp_path):
    (tmp_path / "vitest.config.mts").write_text("")
    assert WebProjectType().detect_test_framework(tmp_path) == "vitest"


def test_web_detect_test_framework_jest_when_no_vitest(tmp_path):
    (tmp_path / "jest.config.js").write_text("")
    assert WebProjectType().detect_test_framework(tmp_path) == "jest"


def test_web_detect_test_framework_mocha_when_no_vitest_jest(tmp_path):
    (tmp_path / ".mocharc.json").write_text("{}")
    assert WebProjectType().detect_test_framework(tmp_path) == "mocha"


def test_web_detect_test_framework_vitest_wins_over_jest(tmp_path):
    (tmp_path / "vitest.config.ts").write_text("")
    (tmp_path / "jest.config.js").write_text("")
    assert WebProjectType().detect_test_framework(tmp_path) == "vitest"


def test_web_detect_test_framework_returns_none_when_no_config(tmp_path):
    assert WebProjectType().detect_test_framework(tmp_path) is None


# ─── WebProjectType — schema provider detection ──────────────────


def test_web_detect_schema_provider_prisma(tmp_path):
    (tmp_path / "prisma").mkdir()
    (tmp_path / "prisma" / "schema.prisma").write_text(
        "datasource db { provider = \"sqlite\" url = \"file:./dev.db\" }"
    )
    assert WebProjectType().detect_schema_provider(tmp_path) == "prisma"


def test_web_detect_schema_provider_returns_none_without_schema_file(tmp_path):
    (tmp_path / "prisma").mkdir()  # dir exists but no schema.prisma file
    assert WebProjectType().detect_schema_provider(tmp_path) is None


def test_web_detect_schema_provider_returns_none_no_prisma_dir(tmp_path):
    assert WebProjectType().detect_schema_provider(tmp_path) is None


# ─── WebProjectType — design globals path ────────────────────────


def test_web_get_design_globals_path_v0_export(tmp_path):
    target = tmp_path / "v0-export" / "app" / "globals.css"
    target.parent.mkdir(parents=True)
    target.write_text(":root { --background: white; }")
    result = WebProjectType().get_design_globals_path(tmp_path)
    assert result == target
    assert result.is_file()


def test_web_get_design_globals_path_shadcn_legacy(tmp_path):
    target = tmp_path / "shadcn" / "globals.css"
    target.parent.mkdir()
    target.write_text(":root { --background: white; }")
    result = WebProjectType().get_design_globals_path(tmp_path)
    assert result == target


def test_web_get_design_globals_path_v0_wins_over_shadcn(tmp_path):
    v0 = tmp_path / "v0-export" / "app" / "globals.css"
    v0.parent.mkdir(parents=True)
    v0.write_text("v0")
    legacy = tmp_path / "shadcn" / "globals.css"
    legacy.parent.mkdir()
    legacy.write_text("legacy")
    result = WebProjectType().get_design_globals_path(tmp_path)
    assert result == v0


def test_web_get_design_globals_path_returns_none_when_neither_present(tmp_path):
    assert WebProjectType().get_design_globals_path(tmp_path) is None
