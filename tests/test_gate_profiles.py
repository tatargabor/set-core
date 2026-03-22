"""Tests for gate_profiles — per-change-type verification gate configuration."""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from set_orch.gate_profiles import (
    UNIVERSAL_DEFAULTS,
    GateConfig,
    resolve_gate_config,
)


# ── GateConfig helpers ──────────────────────────────────────────────


class TestGateConfigHelpers:
    def test_should_run_true_for_run(self):
        gc = GateConfig(gates={"build": "run"})
        assert gc.should_run("build") is True

    def test_should_run_true_for_warn(self):
        gc = GateConfig(gates={"build": "warn"})
        assert gc.should_run("build") is True

    def test_should_run_true_for_soft(self):
        gc = GateConfig(gates={"build": "soft"})
        assert gc.should_run("build") is True

    def test_should_run_false_for_skip(self):
        gc = GateConfig(gates={"build": "skip"})
        assert gc.should_run("build") is False

    def test_is_blocking_only_for_run(self):
        assert GateConfig(gates={"test": "run"}).is_blocking("test") is True
        assert GateConfig(gates={"test": "warn"}).is_blocking("test") is False
        assert GateConfig(gates={"test": "soft"}).is_blocking("test") is False
        assert GateConfig(gates={"test": "skip"}).is_blocking("test") is False

    def test_is_warn_only(self):
        assert GateConfig(gates={"review": "warn"}).is_warn_only("review") is True
        assert GateConfig(gates={"review": "soft"}).is_warn_only("review") is True
        assert GateConfig(gates={"review": "run"}).is_warn_only("review") is False
        assert GateConfig(gates={"review": "skip"}).is_warn_only("review") is False

    def test_unknown_gate_defaults_to_run(self):
        gc = GateConfig()
        assert gc.should_run("nonexistent") is True
        assert gc.is_blocking("nonexistent") is True

    def test_test_files_required_is_bool(self):
        gc = GateConfig(test_files_required=False)
        assert gc.test_files_required is False

    def test_get_and_set(self):
        gc = GateConfig(gates={"build": "run"})
        assert gc.get("build") == "run"
        gc.set("build", "skip")
        assert gc.get("build") == "skip"
        assert gc.should_run("build") is False

    def test_gate_names(self):
        gc = GateConfig(gates={"build": "run", "test": "warn", "e2e": "skip"})
        names = gc.gate_names()
        assert set(names) == {"build", "test", "e2e"}


# ── Universal defaults ──────────────────────────────────────────────


class TestUniversalDefaults:
    def test_all_six_types_exist(self):
        expected = {
            "infrastructure", "schema", "foundational",
            "feature", "cleanup-before", "cleanup-after",
        }
        assert set(UNIVERSAL_DEFAULTS.keys()) == expected

    def test_infrastructure_skips_build_test(self):
        d = UNIVERSAL_DEFAULTS["infrastructure"]
        assert d["build"] == "skip"
        assert d["test"] == "skip"
        assert d["review"] == "run"
        assert d["scope_check"] == "run"

    def test_schema_warns_test(self):
        d = UNIVERSAL_DEFAULTS["schema"]
        assert d["build"] == "run"
        assert d["test"] == "warn"

    def test_feature_runs_everything(self):
        d = UNIVERSAL_DEFAULTS["feature"]
        for gate in ("build", "test", "scope_check", "review", "spec_verify"):
            assert d[gate] == "run", f"{gate} should be 'run'"
        assert d["rules"] == "warn", "rules should be 'warn' (non-blocking)"


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
        assert gc.get("build") == "skip"
        assert gc.get("test") == "skip"

    def test_unknown_type_uses_default(self):
        change = _make_change(change_type="unknown-type")
        gc = resolve_gate_config(change)
        assert gc.get("build") == "run"
        assert gc.get("test") == "run"

    def test_missing_change_type_defaults_to_feature(self):
        change = SimpleNamespace(name="no-type")
        gc = resolve_gate_config(change)
        assert gc.get("build") == "run"

    def test_skip_test_flag_overrides(self):
        change = _make_change(change_type="feature", skip_test=True)
        gc = resolve_gate_config(change)
        assert gc.get("test") == "skip"
        assert gc.test_files_required is False

    def test_skip_review_flag_overrides(self):
        change = _make_change(change_type="feature", skip_review=True)
        gc = resolve_gate_config(change)
        assert gc.get("review") == "skip"

    def test_gate_hints_override(self):
        change = _make_change(
            change_type="feature",
            gate_hints={"e2e": "skip", "lint": "warn"},
        )
        gc = resolve_gate_config(change)
        assert gc.get("e2e") == "skip"
        assert gc.get("lint") == "warn"
        assert gc.get("build") == "run"

    def test_gate_hints_none_is_safe(self):
        change = _make_change(change_type="feature", gate_hints=None)
        gc = resolve_gate_config(change)
        assert gc.get("build") == "run"

    def test_profile_plugin_overrides(self):
        change = _make_change(change_type="foundational")
        profile = SimpleNamespace(
            gate_overrides=lambda ct: {"e2e": "run"} if ct == "foundational" else {}
        )
        gc = resolve_gate_config(change, profile=profile)
        assert gc.get("e2e") == "run"

    def test_directive_overrides(self):
        change = _make_change(change_type="schema")
        directives = {
            "gate_overrides": {
                "schema": {"test": "run", "e2e": "run"},
            }
        }
        gc = resolve_gate_config(change, directives=directives)
        assert gc.get("test") == "run"
        assert gc.get("e2e") == "run"

    def test_resolution_priority_order(self):
        """Later layers override earlier: directive > gate_hints > skip_flags > profile > builtin."""
        change = _make_change(
            change_type="feature",
            gate_hints={"review": "warn"},
        )
        profile = SimpleNamespace(
            gate_overrides=lambda ct: {"review": "skip"}
        )
        gc = resolve_gate_config(change, profile=profile)
        assert gc.get("review") == "warn"

    def test_directive_overrides_gate_hints(self):
        """Directive (layer 6) overrides gate_hints (layer 5)."""
        change = _make_change(
            change_type="feature",
            gate_hints={"lint": "skip"},
        )
        directives = {
            "gate_overrides": {
                "feature": {"lint": "run"},
            }
        }
        gc = resolve_gate_config(change, directives=directives)
        assert gc.get("lint") == "run"

    def test_max_retries_from_profile(self):
        change = _make_change(change_type="infrastructure")
        gc = resolve_gate_config(change)
        assert gc.max_retries is None

    def test_review_model_from_gate_hints(self):
        change = _make_change(
            change_type="feature",
            gate_hints={"review_model": "sonnet"},
        )
        gc = resolve_gate_config(change)
        assert gc.review_model == "sonnet"

    def test_invalid_directive_types_ignored(self):
        change = _make_change(change_type="feature")
        directives = {"gate_overrides": "not-a-dict"}
        gc = resolve_gate_config(change, directives=directives)
        assert gc.get("build") == "run"

    def test_invalid_type_overrides_ignored(self):
        change = _make_change(change_type="feature")
        directives = {"gate_overrides": {"feature": "not-a-dict"}}
        gc = resolve_gate_config(change, directives=directives)
        assert gc.get("build") == "run"

    def test_unknown_gate_in_hints_accepted(self):
        """Dynamic config accepts arbitrary gate names from hints."""
        change = _make_change(
            change_type="feature",
            gate_hints={"mypy": "run"},
        )
        gc = resolve_gate_config(change)
        assert gc.get("mypy") == "run"
        assert gc.get("build") == "run"

    def test_profile_register_gates_adds_defaults(self):
        """Profile.register_gates() defaults are included in resolved config."""
        from set_orch.gate_runner import GateDefinition

        def _noop(**kw):
            pass

        change = _make_change(change_type="feature")
        profile = SimpleNamespace(
            register_gates=lambda: [
                GateDefinition("e2e", _noop, defaults={"feature": "run", "infrastructure": "skip"}),
                GateDefinition("lint", _noop, defaults={"feature": "run"}),
            ],
            gate_overrides=lambda ct: {},
        )
        gc = resolve_gate_config(change, profile=profile)
        assert gc.get("e2e") == "run"
        assert gc.get("lint") == "run"
        assert gc.get("build") == "run"  # universal still there

    def test_nullprofile_has_only_universal_gates(self):
        """Without profile, only universal gates exist."""
        change = _make_change(change_type="feature")
        gc = resolve_gate_config(change)
        names = gc.gate_names()
        assert "build" in names
        assert "test" in names
        assert "e2e" not in names  # no profile → no e2e
        assert "lint" not in names


# ── GateDefinition ──────────────────────────────────────────────────


class TestGateDefinition:
    def test_create_with_defaults(self):
        from set_orch.gate_runner import GateDefinition, GateResult

        def _dummy(**kw):
            return GateResult("test", "pass")

        gd = GateDefinition("test", _dummy)
        assert gd.name == "test"
        assert gd.position == "end"
        assert gd.phase == "pre-merge"
        assert gd.defaults == {}
        assert gd.run_on_integration is False
        assert gd.result_fields is None

    def test_create_with_all_fields(self):
        from set_orch.gate_runner import GateDefinition, GateResult

        def _dummy(**kw):
            return GateResult("build", "pass")

        gd = GateDefinition(
            "build", _dummy,
            position="start",
            phase="pre-merge",
            defaults={"infrastructure": "skip"},
            own_retry_counter="build_fix_attempt_count",
            extra_retries=2,
            result_fields=("build_result", "gate_build_ms"),
            run_on_integration=True,
        )
        assert gd.name == "build"
        assert gd.position == "start"
        assert gd.defaults["infrastructure"] == "skip"
        assert gd.run_on_integration is True
        assert gd.result_fields == ("build_result", "gate_build_ms")


# ── _resolve_gate_order ─────────────────────────────────────────────


class TestResolveGateOrder:
    def test_position_hints_produce_correct_order(self):
        from set_orch.gate_runner import GateDefinition, _resolve_gate_order, GateResult

        def _noop(**kw):
            return GateResult("x", "pass")

        gates = [
            GateDefinition("build", _noop, position="start"),
            GateDefinition("test", _noop, position="after:build"),
            GateDefinition("scope_check", _noop, position="after:test"),
            GateDefinition("test_files", _noop, position="after:scope_check"),
            GateDefinition("review", _noop, position="before:end"),
            GateDefinition("rules", _noop, position="after:review"),
            GateDefinition("spec_verify", _noop, position="end"),
            # Profile gates:
            GateDefinition("e2e", _noop, position="after:test"),
            GateDefinition("lint", _noop, position="after:test_files"),
        ]
        ordered = _resolve_gate_order(gates)
        names = [g.name for g in ordered]
        # Universal gates (defined first) get priority at same position hint
        # scope_check and e2e are both after:test — scope_check first (input order)
        assert names == [
            "build", "test", "scope_check", "e2e", "test_files", "lint",
            "rules", "review", "spec_verify",
        ]
