"""Tests for model-config-unified: resolution chain, presets, validation."""

import os
import re
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "modules", "web"))

from set_orch.config import DIRECTIVE_DEFAULTS, MODEL_NAME_RE
from set_orch.model_config import (
    resolve_model,
    list_role_keys,
    PRESETS,
    _env_var_name,
)
from set_orch.profile_loader import CoreProfile


# ─── DIRECTIVE_DEFAULTS schema ───────────────────────────────────


def test_directive_defaults_models_block_has_all_keys():
    models = DIRECTIVE_DEFAULTS["models"]
    required_flat = (
        "agent", "agent_small", "digest",
        "decompose_brief", "decompose_domain", "decompose_merge",
        "review", "review_escalation",
        "spec_verify", "spec_verify_escalation",
        "classifier", "supervisor", "canary",
    )
    for key in required_flat:
        assert key in models, f"missing flat role: {key}"
    assert "trigger" in models
    for sub in ("integration_failed", "non_periodic_checkpoint",
                "terminal_state", "default"):
        assert sub in models["trigger"], f"missing trigger sub: {sub}"


def test_every_default_value_is_a_valid_short_name():
    pattern = re.compile(MODEL_NAME_RE)
    models = DIRECTIVE_DEFAULTS["models"]
    for key, val in models.items():
        if isinstance(val, dict):
            for sub_key, sub_val in val.items():
                assert pattern.match(sub_val), (
                    f"trigger.{sub_key} value {sub_val!r} fails regex"
                )
        else:
            assert pattern.match(val), f"{key} value {val!r} fails regex"


def test_agent_default_is_opus_4_6():
    assert resolve_model("agent") == "opus-4-6"
    assert DIRECTIVE_DEFAULTS["models"]["agent"] == "opus-4-6"


def test_opus_4_6_short_name_maps_to_claude_opus_4_6():
    from set_orch.subprocess_utils import _MODEL_MAP
    assert _MODEL_MAP["opus-4-6"] == "claude-opus-4-6"


# ─── Resolution chain ────────────────────────────────────────────


def test_cli_override_beats_env_yaml_defaults(monkeypatch):
    monkeypatch.setenv("SET_ORCH_MODEL_AGENT", "sonnet")
    assert resolve_model("agent", cli_override="haiku") == "haiku"


def test_env_var_beats_yaml_and_defaults(monkeypatch):
    monkeypatch.setenv("SET_ORCH_MODEL_AGENT", "opus-4-7")
    # No yaml override → env wins, returns opus-4-7
    with tempfile.TemporaryDirectory() as td:
        assert resolve_model("agent", project_dir=td) == "opus-4-7"


def test_yaml_beats_profile_and_defaults(tmp_path, monkeypatch):
    # No CLI, no ENV
    monkeypatch.delenv("SET_ORCH_MODEL_AGENT", raising=False)
    # Write yaml
    yaml_path = tmp_path / ".claude" / "orchestration.yaml"
    yaml_path.parent.mkdir()
    yaml_path.write_text("models:\n  agent: sonnet\n")
    assert resolve_model("agent", project_dir=str(tmp_path)) == "sonnet"


def test_defaults_are_last_resort(tmp_path, monkeypatch):
    monkeypatch.delenv("SET_ORCH_MODEL_AGENT", raising=False)
    # tmp_path has no orchestration.yaml
    assert resolve_model("agent", project_dir=str(tmp_path)) == "opus-4-6"


def test_nested_trigger_role_resolves_dotted_path():
    # No overrides — should hit DIRECTIVE_DEFAULTS["models"]["trigger"]["integration_failed"]
    val = resolve_model("trigger.integration_failed")
    assert val == DIRECTIVE_DEFAULTS["models"]["trigger"]["integration_failed"]


def test_env_var_name_maps_dots_to_underscores(monkeypatch):
    assert _env_var_name("agent") == "SET_ORCH_MODEL_AGENT"
    assert _env_var_name("trigger.integration_failed") == "SET_ORCH_MODEL_TRIGGER_INTEGRATION_FAILED"

    monkeypatch.setenv("SET_ORCH_MODEL_TRIGGER_INTEGRATION_FAILED", "opus-4-7")
    assert resolve_model("trigger.integration_failed") == "opus-4-7"


def test_invalid_env_var_value_raises(monkeypatch):
    monkeypatch.setenv("SET_ORCH_MODEL_AGENT", "not-a-real-model")
    with pytest.raises(ValueError) as ei:
        resolve_model("agent")
    assert "ENV" in str(ei.value)
    assert "not-a-real-model" in str(ei.value)


def test_invalid_cli_override_raises():
    with pytest.raises(ValueError) as ei:
        resolve_model("agent", cli_override="not-a-real-model")
    assert "CLI" in str(ei.value)


def test_unknown_role_raises():
    with pytest.raises(ValueError) as ei:
        resolve_model("not-a-real-role")
    assert "not-a-real-role" in str(ei.value)


# ─── ProjectType.model_for hook ──────────────────────────────────


def test_core_profile_model_for_returns_none_for_any_role():
    cp = CoreProfile()
    for role in ("agent", "review", "trigger.integration_failed"):
        assert cp.model_for(role) is None


def test_plugin_override_fires_when_nothing_higher_in_chain_wins(tmp_path, monkeypatch):
    """Custom profile.model_for fires only when CLI/ENV/yaml don't override."""
    monkeypatch.delenv("SET_ORCH_MODEL_REVIEW_ESCALATION", raising=False)
    # No yaml override.
    class _StubProfile(CoreProfile):
        def model_for(self, role):
            if role == "review_escalation":
                return "opus-4-7"
            return None

    with patch("set_orch.profile_loader.load_profile", return_value=_StubProfile()):
        result = resolve_model("review_escalation", project_dir=str(tmp_path))
    assert result == "opus-4-7"


# ─── Presets ────────────────────────────────────────────────────


def test_preset_default_matches_directive_defaults():
    # default preset values mirror DIRECTIVE_DEFAULTS["models"]
    assert PRESETS["default"]["agent"] == DIRECTIVE_DEFAULTS["models"]["agent"]


def test_preset_all_opus_4_6_sets_every_role():
    p = PRESETS["all-opus-4-6"]
    for role in (
        "agent", "agent_small", "digest", "decompose_brief",
        "decompose_domain", "decompose_merge", "review",
        "review_escalation", "spec_verify", "spec_verify_escalation",
        "classifier", "supervisor", "canary",
    ):
        assert p[role] == "opus-4-6", f"all-opus-4-6 preset has {role}={p[role]!r}"
    for sub in ("integration_failed", "non_periodic_checkpoint",
                "terminal_state", "default"):
        assert p["trigger"][sub] == "opus-4-6"


def test_preset_all_opus_4_7_sets_every_role():
    p = PRESETS["all-opus-4-7"]
    assert p["agent"] == "opus-4-7"
    assert p["review"] == "opus-4-7"
    assert p["trigger"]["default"] == "opus-4-7"


def test_preset_cost_optimized_uses_haiku_for_classifier_and_review():
    p = PRESETS["cost-optimized"]
    assert p["classifier"] == "haiku"
    assert p["review"] == "haiku"
    assert p["spec_verify"] == "haiku"
    assert p["agent"] == "sonnet"  # downgraded from default opus-4-6
    assert p["agent_small"] == "haiku"


def test_list_role_keys_covers_flat_and_trigger():
    keys = list_role_keys()
    assert "agent" in keys
    assert "trigger.integration_failed" in keys
    assert "trigger.default" in keys
    assert len(keys) == 13 + 4  # 13 flat roles + 4 trigger sub-keys


# ─── Legacy directive backwards-compat ──────────────────────────


def test_legacy_default_model_directive_honored_with_warning(tmp_path, monkeypatch, caplog):
    import logging
    monkeypatch.delenv("SET_ORCH_MODEL_AGENT", raising=False)

    yaml_path = tmp_path / ".claude" / "orchestration.yaml"
    yaml_path.parent.mkdir()
    # Legacy `default_model` (no models: block)
    yaml_path.write_text("default_model: opus-4-7\n")

    # Reset the deprecation tracker for this test (process-global)
    from set_orch.model_config import _legacy_warned
    _legacy_warned.clear()

    caplog.set_level(logging.WARNING, logger="set_orch.model_config")
    result = resolve_model("agent", project_dir=str(tmp_path))
    assert result == "opus-4-7"
    # WARNING must mention default_model is deprecated
    msgs = " | ".join(r.getMessage() for r in caplog.records)
    assert "default_model" in msgs and "DEPRECATED" in msgs


def test_explicit_models_agent_overrides_legacy_default_model(tmp_path, monkeypatch):
    monkeypatch.delenv("SET_ORCH_MODEL_AGENT", raising=False)
    yaml_path = tmp_path / ".claude" / "orchestration.yaml"
    yaml_path.parent.mkdir()
    yaml_path.write_text(
        "default_model: opus-4-7\n"
        "models:\n"
        "  agent: opus-4-6\n"
    )
    # Reset deprecation tracker
    from set_orch.model_config import _legacy_warned
    _legacy_warned.clear()
    assert resolve_model("agent", project_dir=str(tmp_path)) == "opus-4-6"
