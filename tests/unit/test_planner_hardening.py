"""Tests for planner-python-hardening: hard validation, profile planning rules,
cross-cutting files, and core/web rule separation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from set_orch.planner import validate_plan, ValidationResult


# ─── Helpers ────────────────────────────────────────────────────


def _write_plan(tmp_path: Path, changes: list[dict], **extra) -> str:
    """Write a minimal plan JSON and return the path."""
    plan = {
        "plan_version": 1,
        "brief_hash": "abc123",
        "changes": changes,
        **extra,
    }
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(plan), encoding="utf-8")
    return str(p)


def _change(name="test-change", complexity="S", model="opus", scope="x" * 100):
    return {
        "name": name,
        "complexity": complexity,
        "model": model,
        "scope": scope,
        "change_type": "feature",
    }


# ─── 5.1: validate_plan() hard checks ──────────────────────────


class TestValidatePlanHardChecks:
    def test_valid_plan_passes(self, tmp_path):
        path = _write_plan(tmp_path, [_change("a"), _change("b")])
        result = validate_plan(path, max_change_target=6)
        # No hard-check errors (may have warnings about source_items)
        hard_errors = [e for e in result.errors if "complexity" in e or "changes, max" in e or "model" in e or "scope is" in e]
        assert hard_errors == []

    def test_change_count_over_limit(self, tmp_path):
        changes = [_change(f"c-{i}") for i in range(8)]
        path = _write_plan(tmp_path, changes)
        result = validate_plan(path, max_change_target=6)
        assert any("8 changes, max allowed is 6" in e for e in result.errors)

    def test_change_count_within_limit(self, tmp_path):
        changes = [_change(f"c-{i}") for i in range(5)]
        path = _write_plan(tmp_path, changes)
        result = validate_plan(path, max_change_target=6)
        assert not any("changes, max allowed" in e for e in result.errors)

    def test_complexity_l_rejected(self, tmp_path):
        path = _write_plan(tmp_path, [_change("big", complexity="L")])
        result = validate_plan(path)
        assert any("complexity L" in e for e in result.errors)

    def test_complexity_s_m_accepted(self, tmp_path):
        path = _write_plan(tmp_path, [_change("a", complexity="S"), _change("b", complexity="M")])
        result = validate_plan(path)
        assert not any("complexity" in e for e in result.errors)

    def test_model_haiku_rejected(self, tmp_path):
        path = _write_plan(tmp_path, [_change("a", model="haiku")])
        result = validate_plan(path)
        assert any("invalid model 'haiku'" in e for e in result.errors)

    def test_model_opus_sonnet_accepted(self, tmp_path):
        path = _write_plan(tmp_path, [_change("a", model="opus"), _change("b", model="sonnet")])
        result = validate_plan(path)
        assert not any("invalid model" in e for e in result.errors)

    def test_scope_over_2000_rejected(self, tmp_path):
        path = _write_plan(tmp_path, [_change("big", scope="x" * 2500)])
        result = validate_plan(path)
        assert any("2500 chars (max 2000)" in e for e in result.errors)

    def test_scope_within_limit(self, tmp_path):
        path = _write_plan(tmp_path, [_change("ok", scope="x" * 1500)])
        result = validate_plan(path)
        assert not any("scope is" in e for e in result.errors)

    def test_no_max_change_target_skips_check(self, tmp_path):
        """When max_change_target is None, count check is skipped."""
        changes = [_change(f"c-{i}") for i in range(20)]
        path = _write_plan(tmp_path, changes)
        result = validate_plan(path, max_change_target=None)
        assert not any("changes, max allowed" in e for e in result.errors)


# ─── 5.2: WebProjectType.planning_rules() ──────────────────────


class TestWebPlanningRules:
    def test_returns_nonempty(self):
        from set_project_web.project_type import WebProjectType
        profile = WebProjectType()
        rules = profile.planning_rules()
        assert len(rules) > 0

    def test_contains_web_keywords(self):
        from set_project_web.project_type import WebProjectType
        profile = WebProjectType()
        rules = profile.planning_rules().lower()
        # Should contain web-specific patterns
        assert "prisma" in rules or "playwright" in rules or "e2e" in rules


# ─── 5.3: WebProjectType.cross_cutting_files() ─────────────────


class TestWebCrossCuttingFiles:
    def test_returns_expected_files(self):
        from set_project_web.project_type import WebProjectType
        profile = WebProjectType()
        files = profile.cross_cutting_files()
        assert "layout.tsx" in files
        assert "middleware.ts" in files
        assert "tailwind.config.ts" in files
        assert "next.config.mjs" in files
        assert len(files) == 8


# ─── 5.4: CoreProfile defaults ─────────────────────────────────


class TestCoreProfileDefaults:
    def test_planning_rules_empty(self):
        from set_orch.profile_loader import CoreProfile
        profile = CoreProfile()
        assert profile.planning_rules() == ""

    def test_cross_cutting_files_empty(self):
        from set_orch.profile_loader import CoreProfile
        profile = CoreProfile()
        assert profile.cross_cutting_files() == []


# ─── 5.5: render_planning_prompt integration ───────────────────


class TestPlanningPromptIntegration:
    def test_core_profile_no_web_keywords(self):
        """With CoreProfile, prompt should not contain web-specific patterns."""
        from set_orch.templates import _get_planning_rules, _PLANNING_RULES_CORE
        # The core rules should not contain web-specific file names
        core = _PLANNING_RULES_CORE.lower()
        assert "layout.tsx" not in core
        assert "middleware.ts" not in core
        assert "tailwind.config" not in core
        # The test pattern should be generic, not .spec.ts specific
        assert "tests/e2e/<change-name>.spec.ts" not in core
