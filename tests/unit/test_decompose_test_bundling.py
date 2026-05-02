"""Tests for decompose-tests-bundled-with-features."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "modules", "web"))

from set_orch.templates import (
    render_brief_prompt,
    render_domain_decompose_prompt,
    render_merge_prompt,
)
from set_orch.planner import _assert_no_standalone_test_changes
from set_orch.profile_types import ProjectType
from set_orch.profile_loader import CoreProfile


# Helper: an in-memory test profile derived from CoreProfile so it has the
# full planner/templates API. We override only the 4 hooks introduced in
# this change.
class _StubProfile(CoreProfile):
    def __init__(self, forbidden=None, prefixes=None, infra="test-infrastructure-setup", hint=""):
        super().__init__()
        self._forbidden = forbidden if forbidden is not None else ["testing", "tests", "qa", "validation"]
        self._prefixes = prefixes if prefixes is not None else []
        self._infra = infra
        self._hint = hint

    def forbidden_test_domain_tokens(self):
        return list(self._forbidden)

    def standalone_test_change_prefixes(self):
        return list(self._prefixes)

    def singleton_test_infrastructure_change_name(self):
        return self._infra

    def feature_e2e_spec_hint(self):
        return self._hint


def _web_stub():
    return _StubProfile(
        forbidden=["testing", "tests", "qa", "validation", "e2e", "playwright", "vitest"],
        prefixes=["playwright-", "vitest-", "e2e-"],
        hint="tests/e2e/<feature>.spec.ts",
    )


def _core_stub():
    """Profile with no stack-specific prefixes (Layer 1 baseline)."""
    return _StubProfile(prefixes=[], hint="")


# ─── Phase 1 brief prompt ─────────────────────────────────────────


def test_brief_prompt_contains_domain_enumeration_rules():
    with patch("set_orch.templates.load_profile", return_value=_web_stub(), create=True):
        # load_profile is imported lazily inside the helper; use module-level patch
        with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
            out = render_brief_prompt(
                domain_summaries="navigation: header\ncontent: pages",
                dependencies="none",
                conventions="kebab-case",
                max_parallel=3,
            )
    assert "DOMAIN ENUMERATION RULES" in out


def test_brief_prompt_includes_web_forbidden_tokens_via_profile():
    with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
        out = render_brief_prompt(
            domain_summaries="x", dependencies="y", conventions="z", max_parallel=3,
        )
    for token in ["testing", "tests", "qa", "validation", "e2e", "playwright", "vitest"]:
        assert f"`{token}`" in out, f"Phase 1 prompt missing forbidden token: {token}"


def test_brief_prompt_uses_core_only_tokens_when_profile_has_no_overrides():
    with patch("set_orch.profile_loader.load_profile", return_value=_core_stub()):
        out = render_brief_prompt(
            domain_summaries="x", dependencies="y", conventions="z", max_parallel=3,
        )
    # Core-only profile lists generic tokens, NOT framework-specific ones
    for token in ["testing", "tests", "qa", "validation"]:
        assert f"`{token}`" in out
    for token in ["playwright", "vitest"]:
        assert f"`{token}`" not in out, f"Core-only profile leaked web token: {token}"


def test_brief_prompt_names_singleton_infra_change():
    with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
        out = render_brief_prompt(
            domain_summaries="x", dependencies="y", conventions="z", max_parallel=3,
        )
    assert "test-infrastructure-setup" in out


def test_brief_prompt_states_feature_domain_test_ownership():
    with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
        out = render_brief_prompt(
            domain_summaries="x", dependencies="y", conventions="z", max_parallel=3,
        )
    assert "feature" in out.lower()
    assert "domain that owns" in out.lower() or "feature domain" in out.lower()


# ─── Phase 2 per-domain decompose prompt ──────────────────────────


def test_domain_decompose_prompt_includes_e2e_hint_from_profile():
    with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
        out = render_domain_decompose_prompt(
            domain_name="content",
            domain_summary="Pages and routes",
            domain_requirements="REQ-001",
            planning_brief='{"domain_priorities":["content"]}',
            conventions="kebab-case",
            max_parallel=3,
        )
    # Web profile supplies tests/e2e/<feature>.spec.ts hint
    assert "tests/e2e/<feature>.spec.ts" in out


def test_domain_decompose_prompt_falls_back_to_generic_when_profile_has_no_hint():
    with patch("set_orch.profile_loader.load_profile", return_value=_core_stub()):
        out = render_domain_decompose_prompt(
            domain_name="content",
            domain_summary="x",
            domain_requirements="REQ-001",
            planning_brief="{}",
            conventions="z",
            max_parallel=3,
        )
    # Generic clause kicks in — no concrete path mentioned
    assert "tests/e2e/" not in out
    assert "spec_files" in out


def test_domain_decompose_prompt_forbids_standalone_test_changes():
    with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
        out = render_domain_decompose_prompt(
            domain_name="content",
            domain_summary="x",
            domain_requirements="REQ-001",
            planning_brief="{}",
            conventions="z",
            max_parallel=3,
        )
    assert "standalone" in out.lower() or "do not emit" in out.lower() or "do NOT emit" in out


# ─── Phase 3 merge prompt ─────────────────────────────────────────


def test_merge_prompt_names_refold_rule_with_web_prefixes():
    with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
        out = render_merge_prompt(
            domain_plans="{}", planning_brief="{}", dependencies="none",
        )
    assert "TEST CHANGE FOLDING" in out
    # Web prefixes appear in the refold instruction
    for prefix in ["playwright-", "vitest-", "e2e-"]:
        assert prefix in out


def test_merge_prompt_uses_generic_clause_when_profile_has_no_prefixes():
    with patch("set_orch.profile_loader.load_profile", return_value=_core_stub()):
        out = render_merge_prompt(
            domain_plans="{}", planning_brief="{}", dependencies="none",
        )
    assert "TEST CHANGE FOLDING" in out
    assert "playwright-" not in out
    assert "standalone test-only change" in out.lower()


def test_merge_prompt_names_singleton_exception():
    with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
        out = render_merge_prompt(
            domain_plans="{}", planning_brief="{}", dependencies="none",
        )
    assert "test-infrastructure-setup" in out


# ─── Post-Phase-3 fail-fast guard ─────────────────────────────────


def test_guard_raises_on_standalone_playwright_change():
    plan = {"changes": [{"name": "playwright-smoke-tests"}]}
    with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
        with pytest.raises(RuntimeError) as ei:
            _assert_no_standalone_test_changes(plan)
    msg = str(ei.value)
    assert "playwright-smoke-tests" in msg
    assert "decompose-test-bundling" in msg


def test_guard_allows_singleton_test_infrastructure_setup():
    plan = {"changes": [{"name": "test-infrastructure-setup"}]}
    with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
        _assert_no_standalone_test_changes(plan)  # no raise


def test_guard_allows_feature_changes_with_no_test_prefix():
    plan = {"changes": [
        {"name": "content-home-page"},
        {"name": "command-palette"},
        {"name": "auth-login"},
    ]}
    with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
        _assert_no_standalone_test_changes(plan)


def test_guard_raises_on_vitest_prefix_in_mixed_plan():
    plan = {"changes": [
        {"name": "auth-login"},
        {"name": "vitest-validation-suite"},
        {"name": "content-home-page"},
    ]}
    with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
        with pytest.raises(RuntimeError) as ei:
            _assert_no_standalone_test_changes(plan)
    assert "vitest-validation-suite" in str(ei.value)


def test_guard_raises_on_extra_playwright_alongside_infra():
    plan = {"changes": [
        {"name": "test-infrastructure-setup"},
        {"name": "playwright-extra-suite"},
    ]}
    with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
        with pytest.raises(RuntimeError) as ei:
            _assert_no_standalone_test_changes(plan)
    assert "playwright-extra-suite" in str(ei.value)


def test_guard_raises_on_e2e_prefix():
    plan = {"changes": [{"name": "e2e-coverage-suite"}]}
    with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
        with pytest.raises(RuntimeError) as ei:
            _assert_no_standalone_test_changes(plan)
    assert "e2e-coverage-suite" in str(ei.value)


def test_guard_skips_when_profile_has_no_prefixes():
    """Layer 1 (core profile) supplies no prefixes → guard is a no-op."""
    plan = {"changes": [{"name": "playwright-anything"}]}
    with patch("set_orch.profile_loader.load_profile", return_value=_core_stub()):
        _assert_no_standalone_test_changes(plan)  # no raise — core has no prefixes


def test_guard_handles_empty_plan():
    with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
        _assert_no_standalone_test_changes({"changes": []})
        _assert_no_standalone_test_changes({})


def test_guard_handles_malformed_change_entries():
    plan = {"changes": [
        {"name": ""},
        {"description": "no name"},
        "not-a-dict",
        None,
        {"name": "auth-login"},
    ]}
    with patch("set_orch.profile_loader.load_profile", return_value=_web_stub()):
        _assert_no_standalone_test_changes(plan)


# ─── Layer separation verification ────────────────────────────────


def test_core_profile_does_not_leak_web_tokens():
    """CoreProfile (Layer 1 baseline) must NOT include framework-specific tokens."""
    cp = CoreProfile()
    forbidden = cp.forbidden_test_domain_tokens()
    assert "playwright" not in forbidden
    assert "vitest" not in forbidden
    assert "e2e" not in forbidden
    assert "testing" in forbidden
    # Empty prefix list — no stack assumptions in core
    assert cp.standalone_test_change_prefixes() == []
    # No e2e path hint in core
    assert cp.feature_e2e_spec_hint() == ""
    # Default infra change name is the canonical one
    assert cp.singleton_test_infrastructure_change_name() == "test-infrastructure-setup"


def test_web_profile_supplies_stack_specific_overrides():
    from set_project_web.project_type import WebProjectType
    p = WebProjectType()
    forbidden = p.forbidden_test_domain_tokens()
    assert "playwright" in forbidden
    assert "vitest" in forbidden
    assert "e2e" in forbidden
    assert "testing" in forbidden  # core baseline carried through
    prefixes = p.standalone_test_change_prefixes()
    assert prefixes == ["playwright-", "vitest-", "e2e-"]
    assert p.feature_e2e_spec_hint() == "tests/e2e/<feature>.spec.ts"
