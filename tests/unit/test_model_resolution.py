"""Unit tests for short model name → full Claude model ID resolution.

Two implementations must stay in sync:
- Python: lib/set_orch/subprocess_utils.py::resolve_model_id / _MODEL_MAP
- Bash:   bin/set-common.sh::resolve_model_id

These tests pin the contract:
- `opus` shorthand resolves to the project-wide default (currently 4.7)
- Explicit `opus-4-6` and `opus-4-7` pins are available for operators who
  want to lock a specific version (e.g. `default_model: opus-4-6` in
  orchestration config to opt out of 4.7's token cost)
- Bash and Python resolvers MUST agree on every short name
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from set_orch.subprocess_utils import _MODEL_MAP, resolve_model_id

REPO_ROOT = Path(__file__).resolve().parents[2]
SET_COMMON = REPO_ROOT / "bin" / "set-common.sh"


# ─── Python resolver ────────────────────────────────────────────────────


def test_opus_default_pins_current_release():
    """`opus` shorthand resolves to the project-wide default (currently
    4.6). Update this test together with _MODEL_MAP when the default
    moves — that change is intentional, not accidental."""
    assert resolve_model_id("opus") == "claude-opus-4-6"


def test_opus_1m_default_pins_current_release():
    assert resolve_model_id("opus-1m") == "claude-opus-4-6[1m]"


def test_explicit_opus_4_6_pin():
    assert resolve_model_id("opus-4-6") == "claude-opus-4-6"
    assert resolve_model_id("opus-4-6-1m") == "claude-opus-4-6[1m]"


def test_explicit_opus_4_7_pin_still_available():
    """Operators who want 4.7 explicitly can still get it."""
    assert resolve_model_id("opus-4-7") == "claude-opus-4-7"
    assert resolve_model_id("opus-4-7-1m") == "claude-opus-4-7[1m]"


def test_sonnet_haiku_unchanged():
    assert resolve_model_id("sonnet") == "claude-sonnet-4-6"
    assert resolve_model_id("sonnet-1m") == "claude-sonnet-4-6[1m]"
    assert resolve_model_id("haiku") == "claude-haiku-4-5-20251001"


def test_full_id_passthrough():
    """Unknown names (full model IDs) pass through unchanged."""
    assert resolve_model_id("claude-opus-4-7") == "claude-opus-4-7"
    assert resolve_model_id("claude-sonnet-4-6") == "claude-sonnet-4-6"
    # Future-proof: a hypothetical 5.0 string passes through
    assert resolve_model_id("claude-opus-5-0") == "claude-opus-5-0"


# ─── Bash mirror — verify shell map matches Python ──────────────────────


def _bash_resolve(name: str) -> str:
    """Invoke `resolve_model_id` from set-common.sh and return the result."""
    if not SET_COMMON.is_file():
        pytest.skip(f"set-common.sh not found at {SET_COMMON}")
    # Stub get_model_prefix so the test doesn't need a config file.
    script = (
        f"get_model_prefix() {{ echo ''; }}; "
        f"source {SET_COMMON!s}; "
        f"resolve_model_id '{name}'"
    )
    result = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def test_bash_python_parity():
    """The bash and python resolvers MUST agree on every short name."""
    short_names = [
        "haiku", "sonnet", "opus", "opus-1m", "sonnet-1m",
        "opus-4-6", "opus-4-7", "opus-4-6-1m", "opus-4-7-1m",
    ]
    for name in short_names:
        py = resolve_model_id(name)
        sh = _bash_resolve(name)
        assert py == sh, (
            f"Bash/Python divergence for '{name}': "
            f"python={py!r}, bash={sh!r}"
        )


def test_bash_opus_default():
    """Standalone bash check — `opus` in shell pins the same default
    as Python (currently 4.6)."""
    assert _bash_resolve("opus") == "claude-opus-4-6"


def test_bash_explicit_opus_4_6():
    """The explicit `opus-4-6` pin works in bash (the operator's
    escape hatch for token economy)."""
    assert _bash_resolve("opus-4-6") == "claude-opus-4-6"


def test_bash_explicit_opus_4_7():
    assert _bash_resolve("opus-4-7") == "claude-opus-4-7"


# ─── Config validation regex ────────────────────────────────────────────


def test_config_regex_accepts_new_aliases():
    """`default_model` config entry must validate the new opus-4-6/4-7
    aliases — otherwise users can't pin them via orchestration config."""
    from set_orch.config import _VALIDATORS as DIRECTIVE_VALIDATORS

    pattern = DIRECTIVE_VALIDATORS["default_model"][1]
    regex = re.compile(pattern)
    for name in ("opus", "opus-4-6", "opus-4-7", "opus-4-6-1m", "opus-4-7-1m",
                 "sonnet", "sonnet-1m", "haiku"):
        assert regex.match(name), f"regex rejects valid alias '{name}'"
    # Negative: random strings rejected
    assert not regex.match("opus-5-0")
    assert not regex.match("claude-opus-4-6")  # full IDs not accepted via config


def test_review_summarize_models_use_same_regex():
    """All three model fields share the same alias set — adding one to
    `default_model` without `review_model` would surprise operators."""
    from set_orch.config import _VALIDATORS as DIRECTIVE_VALIDATORS

    p1 = DIRECTIVE_VALIDATORS["default_model"][1]
    p2 = DIRECTIVE_VALIDATORS["review_model"][1]
    p3 = DIRECTIVE_VALIDATORS["summarize_model"][1]
    assert p1 == p2 == p3
