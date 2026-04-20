"""Unit tests for the per-gate retry-policy profile declaration
(section 12 of fix-replan-stuck-gate-and-decomposer — profile surface).

Only the profile-declared shape is exercised here; the actual cache
reuse + scoped-dispatch logic in GatePipeline lands in a follow-up.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "modules", "web"))


def test_core_profile_returns_empty_policy():
    from set_orch.profile_loader import CoreProfile
    assert CoreProfile().gate_retry_policy() == {}
    assert CoreProfile().gate_cache_scope("review") == []
    assert CoreProfile().gate_scope_filter("e2e", []) is None


def test_web_profile_declares_expected_policy_modes():
    from set_project_web.project_type import WebProjectType
    policy = WebProjectType().gate_retry_policy()
    assert policy["build"] == "always"
    assert policy["test"] == "always"
    assert policy["review"] == "cached"
    assert policy["spec_verify"] == "cached"
    assert policy["design-fidelity"] == "cached"
    assert policy["e2e"] == "scoped"


def test_web_profile_cache_scopes_match_spec():
    from set_project_web.project_type import WebProjectType
    w = WebProjectType()
    assert "src/**" in w.gate_cache_scope("review")
    assert "openspec/specs/**" in w.gate_cache_scope("spec_verify")
    df = w.gate_cache_scope("design-fidelity")
    assert "src/**/*.tsx" in df
    assert "tailwind.config.ts" in df
