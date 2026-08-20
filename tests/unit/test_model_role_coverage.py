"""A role added to one place and not the others must FAIL, not degrade quietly.

Written when the `pm` role was added, after a review found that "add a role to
model_config" is three edits rather than one, and that the three fail in
different directions:

  DIRECTIVE_DEFAULTS["models"]   missing → `resolve_model` raises. LOUD, safe.
  _ROLE_KEYS_FLAT                missing → the all-opus presets simply skip the
                                 role, so `--model-profile all-opus-4-7` leaves
                                 it on its default and says nothing. SILENT.
  an explicit preset             missing → the preset does not cover it, and
                                 falls through to the default. SILENT.

The two silent ones are the reason this file exists. Nothing about a preset
that quietly omits a role looks wrong: it produces a valid model name from a
lower tier, so every call succeeds and the operator's `--model-profile` simply
did not do what its name says.
"""

from __future__ import annotations

import pytest

from set_orch import model_config
from set_orch.config import DIRECTIVE_DEFAULTS


@pytest.mark.parametrize("role", model_config._ROLE_KEYS_FLAT)
def test_every_enumerated_role_has_a_default(role):
    """Without this, `resolve_model(role)` raises for a role the CLI lists."""
    assert role in DIRECTIVE_DEFAULTS["models"], role


def test_the_enumeration_and_the_defaults_name_the_same_roles():
    """Two copies of one list, in two modules. This is the drift check."""
    declared = set(model_config._ROLE_KEYS_FLAT)
    defaults = set(DIRECTIVE_DEFAULTS["models"]) - {"trigger"}
    assert declared == defaults, {
        "enumerated but not defaulted": sorted(declared - defaults),
        "defaulted but not enumerated": sorted(defaults - declared),
    }


@pytest.mark.parametrize("preset", sorted(model_config.PRESETS))
def test_every_preset_covers_every_role(preset):
    """A preset that skips a role is the silent failure, not an error."""
    covered = set(model_config.PRESETS[preset]) - {"trigger"}
    missing = set(model_config._ROLE_KEYS_FLAT) - covered
    assert not missing, f"preset {preset!r} does not cover: {sorted(missing)}"


@pytest.mark.parametrize("role", model_config._ROLE_KEYS_FLAT)
def test_every_role_resolves(role, tmp_path):
    assert model_config.resolve_model(role, project_dir=str(tmp_path))


def test_the_pm_role_exists_and_defaults_to_sonnet(tmp_path):
    """Named explicitly: the fleet's judgment pass resolves its model through
    the role table and names no model of its own."""
    assert model_config.resolve_model("pm", project_dir=str(tmp_path)) == "sonnet"
