"""Unit tests for IssuesPolicyConfig field defaults and from_dict plumbing."""

from __future__ import annotations

import pytest

from set_orch.issues.policy import (
    InvestigationConfig,
    IssuesPolicyConfig,
)


# --- max_turns -----------------------------------------------------------


def test_investigation_config_max_turns_default_40() -> None:
    assert InvestigationConfig().max_turns == 40


def test_from_dict_loads_max_turns_30() -> None:
    cfg = IssuesPolicyConfig.from_dict({"investigation": {"max_turns": 30}})
    assert cfg.investigation.max_turns == 30


def test_from_dict_missing_max_turns_defaults_to_40() -> None:
    cfg = IssuesPolicyConfig.from_dict({"investigation": {"token_budget": 9000}})
    assert cfg.investigation.max_turns == 40


def test_from_dict_empty_investigation_defaults_to_40() -> None:
    cfg = IssuesPolicyConfig.from_dict({"investigation": {}})
    assert cfg.investigation.max_turns == 40


# --- diagnosed_stall_hours -----------------------------------------------


def test_diagnosed_stall_hours_default_2() -> None:
    assert IssuesPolicyConfig().diagnosed_stall_hours == 2


def test_from_dict_loads_diagnosed_stall_hours_1() -> None:
    cfg = IssuesPolicyConfig.from_dict({"diagnosed_stall_hours": 1})
    assert cfg.diagnosed_stall_hours == 1


def test_from_dict_missing_diagnosed_stall_hours_preserves_default() -> None:
    cfg = IssuesPolicyConfig.from_dict({"enabled": True})
    assert cfg.diagnosed_stall_hours == 2


# --- auto_fix_conditions.low_confidence_after_hours ----------------------


def test_default_auto_fix_conditions_has_no_low_confidence_escape() -> None:
    cfg = IssuesPolicyConfig()
    assert cfg.auto_fix_conditions.get("low_confidence_after_hours") is None


def test_from_dict_stores_low_confidence_escape() -> None:
    cfg = IssuesPolicyConfig.from_dict({
        "auto_fix_conditions": {"low_confidence_after_hours": 1},
    })
    assert cfg.auto_fix_conditions["low_confidence_after_hours"] == 1


def test_from_dict_preserves_existing_auto_fix_keys_when_adding_escape() -> None:
    cfg = IssuesPolicyConfig.from_dict({
        "auto_fix_conditions": {"low_confidence_after_hours": 2},
    })
    assert "min_confidence" in cfg.auto_fix_conditions
    assert cfg.auto_fix_conditions["min_confidence"] == 0.85


# --- Combined ------------------------------------------------------------


def test_combined_yaml_structure() -> None:
    cfg = IssuesPolicyConfig.from_dict({
        "enabled": True,
        "diagnosed_stall_hours": 3,
        "investigation": {"max_turns": 50, "token_budget": 75000},
        "auto_fix_conditions": {
            "min_confidence": 0.7,
            "low_confidence_after_hours": 1,
        },
    })
    assert cfg.enabled is True
    assert cfg.diagnosed_stall_hours == 3
    assert cfg.investigation.max_turns == 50
    assert cfg.investigation.token_budget == 75000
    assert cfg.auto_fix_conditions["min_confidence"] == 0.7
    assert cfg.auto_fix_conditions["low_confidence_after_hours"] == 1
