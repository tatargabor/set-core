"""Tests for gate_profiles — per-change-type verification gate configuration."""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from set_orch.gate_profiles import (
    BUILTIN_GATE_PROFILES,
    DEFAULT_GATE_PROFILE,
    GateConfig,
    resolve_gate_config,
)


# ── GateConfig helpers ──────────────────────────────────────────────


class TestGateConfigHelpers:
    def test_should_run_true_for_run(self):
        gc = GateConfig(build="run")
        assert gc.should_run("build") is True

    def test_should_run_true_for_warn(self):
        gc = GateConfig(build="warn")
        assert gc.should_run("build") is True

    def test_should_run_true_for_soft(self):
        gc = GateConfig(build="soft")
        assert gc.should_run("build") is True

    def test_should_run_false_for_skip(self):
        gc = GateConfig(build="skip")
        assert gc.should_run("build") is False

    def test_is_blocking_only_for_run(self):
        assert GateConfig(test="run").is_blocking("test") is True
        assert GateConfig(test="warn").is_blocking("test") is False
        assert GateConfig(test="soft").is_blocking("test") is False
        assert GateConfig(test="skip").is_blocking("test") is False

    def test_is_warn_only(self):
        assert GateConfig(review="warn").is_warn_only("review") is True
        assert GateConfig(review="soft").is_warn_only("review") is True
        assert GateConfig(review="run").is_warn_only("review") is False
        assert GateConfig(review="skip").is_warn_only("review") is False

    def test_unknown_gate_defaults_to_run(self):
        gc = GateConfig()
        assert gc.should_run("nonexistent") is True
        assert gc.is_blocking("nonexistent") is True

    def test_test_files_required_is_bool(self):
        gc = GateConfig(test_files_required=False)
        assert gc.test_files_required is False


# ── Built-in profiles ───────────────────────────────────────────────


class TestBuiltinProfiles:
    def test_all_six_types_exist(self):
        expected = {
            "infrastructure", "schema", "foundational",
            "feature", "cleanup-before", "cleanup-after",
        }
        assert set(BUILTIN_GATE_PROFILES.keys()) == expected

    def test_infrastructure_skips_build_test_e2e_smoke(self):
        gc = BUILTIN_GATE_PROFILES["infrastructure"]
        assert gc.build == "skip"
        assert gc.test == "skip"
        assert gc.e2e == "skip"
        assert gc.smoke == "skip"
        assert gc.test_files_required is False
        assert gc.review == "run"
        assert gc.scope_check == "run"

    def test_schema_warns_test_skips_e2e_smoke(self):
        gc = BUILTIN_GATE_PROFILES["schema"]
        assert gc.build == "run"
        assert gc.test == "warn"
        assert gc.e2e == "skip"
        assert gc.smoke == "skip"
        assert gc.test_files_required is False

    def test_foundational_runs_build_test_no_e2e(self):
        gc = BUILTIN_GATE_PROFILES["foundational"]
        assert gc.build == "run"
        assert gc.test == "run"
        assert gc.e2e == "skip"
        assert gc.test_files_required is True

    def test_feature_runs_everything(self):
        gc = BUILTIN_GATE_PROFILES["feature"]
        for gate in ("build", "test", "e2e", "scope_check", "review",
                     "spec_verify", "rules", "smoke"):
            assert getattr(gc, gate) == "run", f"{gate} should be 'run'"
        assert gc.test_files_required is True

    def test_cleanup_before_warns_test(self):
        gc = BUILTIN_GATE_PROFILES["cleanup-before"]
        assert gc.test == "warn"
        assert gc.e2e == "skip"
        assert gc.smoke == "skip"
        assert gc.test_files_required is False

    def test_cleanup_after_lightest(self):
        gc = BUILTIN_GATE_PROFILES["cleanup-after"]
        assert gc.review == "skip"
        assert gc.rules == "skip"
        assert gc.e2e == "skip"
        assert gc.smoke == "skip"
        assert gc.test == "warn"

    def test_default_profile_matches_feature(self):
        for gate in ("build", "test", "e2e", "scope_check", "review",
                     "spec_verify", "rules", "smoke"):
            assert getattr(DEFAULT_GATE_PROFILE, gate) == "run"
        assert DEFAULT_GATE_PROFILE.test_files_required is True


# ── Resolution chain ────────────────────────────────────────────────


def _make_change(**kwargs):
    """Create a minimal change-like object."""
    defaults = {"name": "test-change", "change_type": "feature"}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestResolveGateConfig:
    def test_basic_resolution_by_change_type(self):
        change = _make_change(change_type="infrastructure")
        gc = resolve_gate_config(change)
        assert gc.build == "skip"
        assert gc.test == "skip"

    def test_unknown_type_uses_default(self):
        change = _make_change(change_type="unknown-type")
        gc = resolve_gate_config(change)
        # Default = feature = all "run"
        assert gc.build == "run"
        assert gc.test == "run"

    def test_missing_change_type_defaults_to_feature(self):
        change = SimpleNamespace(name="no-type")
        gc = resolve_gate_config(change)
        assert gc.build == "run"

    def test_skip_test_flag_overrides(self):
        change = _make_change(change_type="feature", skip_test=True)
        gc = resolve_gate_config(change)
        assert gc.test == "skip"
        assert gc.test_files_required is False

    def test_skip_review_flag_overrides(self):
        change = _make_change(change_type="feature", skip_review=True)
        gc = resolve_gate_config(change)
        assert gc.review == "skip"

    def test_gate_hints_override(self):
        change = _make_change(
            change_type="feature",
            gate_hints={"e2e": "skip", "smoke": "warn"},
        )
        gc = resolve_gate_config(change)
        assert gc.e2e == "skip"
        assert gc.smoke == "warn"
        # Other gates unchanged
        assert gc.build == "run"

    def test_gate_hints_none_is_safe(self):
        change = _make_change(change_type="feature", gate_hints=None)
        gc = resolve_gate_config(change)
        assert gc.build == "run"

    def test_profile_plugin_overrides(self):
        change = _make_change(change_type="foundational")
        profile = SimpleNamespace(
            gate_overrides=lambda ct: {"e2e": "run", "smoke": "warn"} if ct == "foundational" else {}
        )
        gc = resolve_gate_config(change, profile=profile)
        assert gc.e2e == "run"
        assert gc.smoke == "warn"

    def test_directive_overrides(self):
        change = _make_change(change_type="schema")
        directives = {
            "gate_overrides": {
                "schema": {"test": "run", "e2e": "run"},
            }
        }
        gc = resolve_gate_config(change, directives=directives)
        # Directive should override the builtin "warn" for test
        assert gc.test == "run"
        assert gc.e2e == "run"

    def test_resolution_priority_order(self):
        """Later layers override earlier: directive > gate_hints > skip_flags > profile > builtin."""
        change = _make_change(
            change_type="feature",
            gate_hints={"review": "warn"},
        )
        profile = SimpleNamespace(
            gate_overrides=lambda ct: {"review": "skip"}
        )
        # gate_hints (layer 3) should override profile (layer 2)
        gc = resolve_gate_config(change, profile=profile)
        assert gc.review == "warn"

    def test_directive_overrides_gate_hints(self):
        """Directive (layer 4) overrides gate_hints (layer 3)."""
        change = _make_change(
            change_type="feature",
            gate_hints={"smoke": "skip"},
        )
        directives = {
            "gate_overrides": {
                "feature": {"smoke": "run"},
            }
        }
        gc = resolve_gate_config(change, directives=directives)
        assert gc.smoke == "run"

    def test_max_retries_from_profile(self):
        change = _make_change(change_type="infrastructure")
        gc = resolve_gate_config(change)
        assert gc.max_retries is None  # builtin doesn't set it

    def test_review_model_from_gate_hints(self):
        change = _make_change(
            change_type="feature",
            gate_hints={"review_model": "sonnet"},
        )
        gc = resolve_gate_config(change)
        assert gc.review_model == "sonnet"

    def test_invalid_directive_types_ignored(self):
        change = _make_change(change_type="feature")
        directives = {
            "gate_overrides": "not-a-dict",
        }
        gc = resolve_gate_config(change, directives=directives)
        # Should not crash, all gates remain at feature defaults
        assert gc.build == "run"

    def test_invalid_type_overrides_ignored(self):
        change = _make_change(change_type="feature")
        directives = {
            "gate_overrides": {
                "feature": "not-a-dict",
            }
        }
        gc = resolve_gate_config(change, directives=directives)
        assert gc.build == "run"

    def test_unknown_gate_in_hints_ignored(self):
        change = _make_change(
            change_type="feature",
            gate_hints={"nonexistent_gate": "skip"},
        )
        gc = resolve_gate_config(change)
        # Should not crash; unknown fields just don't match hasattr
        assert gc.build == "run"
