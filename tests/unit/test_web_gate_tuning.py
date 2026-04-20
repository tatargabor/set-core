"""Unit tests for web gate tuning (section 8 of
fix-replan-stuck-gate-and-decomposer):
- i18n_check is a blocking (run) gate for foundational + feature changes
- parallel_gate_groups() declares spec_verify + review as parallel-safe
- CoreProfile still returns no parallel groups (web plugin opt-in)
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "modules", "web"))


def test_core_profile_has_no_parallel_groups():
    from set_orch.profile_loader import CoreProfile
    assert CoreProfile().parallel_gate_groups() == []


def test_web_profile_declares_spec_verify_and_review_parallel():
    from set_project_web.project_type import WebProjectType
    groups = WebProjectType().parallel_gate_groups()
    assert len(groups) == 1
    assert groups[0] == {"spec_verify", "review"}


def test_i18n_check_is_blocking_for_features():
    """Registered defaults: foundational=run, feature=run → blocking."""
    from set_project_web.project_type import WebProjectType
    gates = WebProjectType().register_gates()
    i18n = next(g for g in gates if g.name == "i18n_check")
    assert i18n.defaults["foundational"] == "run"
    assert i18n.defaults["feature"] == "run"
    # infrastructure/schema/cleanup remain skipped — no UI content
    assert i18n.defaults["infrastructure"] == "skip"


def test_resolve_gate_config_i18n_blocking_on_feature():
    """Integration: resolve_gate_config on a feature change with UI
    content ends up with i18n_check == "run" (blocking).
    """
    from set_orch.gate_profiles import resolve_gate_config
    from set_orch.state import Change
    from set_project_web.project_type import WebProjectType

    change = Change(
        name="cart-feature",
        change_type="feature",
        touched_file_globs=["src/app/cart/page.tsx"],
    )
    gc = resolve_gate_config(change, profile=WebProjectType())
    assert gc.is_blocking("i18n_check"), "i18n_check must be blocking on feature changes"
