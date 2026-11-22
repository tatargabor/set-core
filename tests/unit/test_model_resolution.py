"""Unit tests for short model name → full Claude model ID resolution.

Two implementations must stay in sync:
- Python: lib/set_orch/providers/defaults.py::DEFAULT_MODEL_IDS
- Bash:   bin/set-common.sh::resolve_model_id

These tests pin the contract:
- `opus`, `sonnet`, `haiku` shorthands resolve to the current release (5.5)
- Explicit `opus-4-6`, `opus-4-7` etc. pins are available for operators who
  want to lock a specific version
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
    """`opus` shorthand resolves to the current release (currently 5.5).
    Update this test together with DEFAULT_MODEL_IDS when the default
    moves — that change is intentional, not accidental."""
    assert resolve_model_id("opus") == "claude-opus-5-5"


def test_opus_1m_default_pins_current_release():
    assert resolve_model_id("opus-1m") == "claude-opus-5-5[1m]"


def test_explicit_opus_4_6_pin():
    assert resolve_model_id("opus-4-6") == "claude-opus-4-6"
    assert resolve_model_id("opus-4-6-1m") == "claude-opus-4-6[1m]"


def test_explicit_opus_4_7_pin_still_available():
    """Operators who want 4.7 explicitly can still get it."""
    assert resolve_model_id("opus-4-7") == "claude-opus-4-7"
    assert resolve_model_id("opus-4-7-1m") == "claude-opus-4-7[1m]"


def test_explicit_opus_5_pin():
    assert resolve_model_id("opus-5") == "claude-opus-5"
    assert resolve_model_id("opus-5-1m") == "claude-opus-5[1m]"


def test_explicit_opus_5_5_pin():
    assert resolve_model_id("opus-5-5") == "claude-opus-5-5"
    assert resolve_model_id("opus-5-5-1m") == "claude-opus-5-5[1m]"


def test_explicit_opus_4_8_pin():
    assert resolve_model_id("opus-4-8") == "claude-opus-4-8"


def test_sonnet_haiku_default_pins_current_release():
    """`sonnet` / `haiku` resolve to 5.5 since 2026-11-22. They sat on 4.6 / 4.5
    for months after newer releases shipped, because the table is bumped by hand
    and only `opus` was ever moved (reported by a peer session, 2026-11-22)."""
    assert resolve_model_id("sonnet") == "claude-sonnet-5-5"
    assert resolve_model_id("sonnet-1m") == "claude-sonnet-5-5[1m]"
    assert resolve_model_id("haiku") == "claude-haiku-5-5"


def test_explicit_sonnet_haiku_pins():
    assert resolve_model_id("sonnet-5-5") == "claude-sonnet-5-5"
    assert resolve_model_id("sonnet-5-5-1m") == "claude-sonnet-5-5[1m]"
    assert resolve_model_id("haiku-5-5") == "claude-haiku-5-5"
    assert resolve_model_id("sonnet-4-6") == "claude-sonnet-4-6"
    assert resolve_model_id("sonnet-4-6-1m") == "claude-sonnet-4-6[1m]"
    assert resolve_model_id("haiku-4-5") == "claude-haiku-4-5-20251001"


def _version(model_id: str) -> tuple:
    """`claude-opus-5-5[1m]` -> (5, 5); `claude-haiku-4-5-20251001` -> (4, 5).

    The numeric parts after the family, the 8-digit snapshot date dropped."""
    parts = model_id.split("[", 1)[0].split("-")[2:]
    return tuple(int(p) for p in parts if p.isdigit() and len(p) < 8)


def test_every_shorthand_resolves_to_the_newest_release_it_ships():
    """The check that would have caught `sonnet` -> 4.6: a family shorthand
    (`opus`, `sonnet`, `haiku`, and their `-1m` forms) must resolve to the newest
    release among the ids this table ships for that family. Adding a newer pin
    without moving the shorthand fails here; `set-providers upstream` (exit 1 on
    `behind`) covers a release the table does not ship at all."""
    families = {}
    for name, model_id in _MODEL_MAP.items():
        family = model_id.split("-")[1]
        families.setdefault(family, []).append(_version(model_id))
    shorthands = [n for n in _MODEL_MAP if n in families or n.removesuffix("-1m") in families]
    assert {"opus", "sonnet", "haiku"} <= set(shorthands)
    for name in shorthands:
        family = name.removesuffix("-1m")
        newest = max(families[family])
        assert _version(_MODEL_MAP[name]) == newest, (
            f"`{name}` resolves to {_MODEL_MAP[name]}, but the table ships a newer "
            f"{family} release {newest}: move the shorthand (defaults.py and set-common.sh)")


def test_full_id_passthrough():
    """Unknown names (full model IDs) pass through unchanged."""
    assert resolve_model_id("claude-opus-4-7") == "claude-opus-4-7"
    assert resolve_model_id("claude-sonnet-4-6") == "claude-sonnet-4-6"
    assert resolve_model_id("claude-opus-5") == "claude-opus-5"


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
    # Every name the Python table maps — a hand-copied list here is a second
    # copy, and it had already fallen behind (no `opus-5-5` in it).
    for name in _MODEL_MAP:
        py = resolve_model_id(name)
        sh = _bash_resolve(name)
        assert py == sh, (
            f"Bash/Python divergence for '{name}': "
            f"python={py!r}, bash={sh!r}"
        )


def test_bash_opus_default():
    """Standalone bash check — `opus` in shell pins the same default
    as Python (currently 5.5)."""
    assert _bash_resolve("opus") == "claude-opus-5-5"


def test_bash_explicit_opus_4_6():
    """The explicit `opus-4-6` pin works in bash."""
    assert _bash_resolve("opus-4-6") == "claude-opus-4-6"


def test_bash_explicit_opus_4_7():
    assert _bash_resolve("opus-4-7") == "claude-opus-4-7"


def test_bash_explicit_opus_5():
    assert _bash_resolve("opus-5") == "claude-opus-5"
    assert _bash_resolve("opus-5-5") == "claude-opus-5-5"


# ─── Config validation regex ────────────────────────────────────────────


def test_config_regex_accepts_new_aliases():
    """`default_model` config entry must validate the new model
    aliases — otherwise users can't pin them via orchestration config."""
    from set_orch.config import _VALIDATORS as DIRECTIVE_VALIDATORS

    pattern = DIRECTIVE_VALIDATORS["default_model"][1]
    regex = re.compile(pattern)
    for name in ("opus", "opus-4-6", "opus-4-7", "opus-4-8", "opus-5",
                 "opus-4-6-1m", "opus-4-7-1m", "opus-5-1m", "opus-5-5", "opus-5-5-1m",
                 "sonnet", "sonnet-1m", "haiku", "sonnet-5-5", "sonnet-5-5-1m",
                 "haiku-5-5", "sonnet-4-6", "sonnet-4-6-1m", "haiku-4-5"):
        assert regex.match(name), f"regex rejects valid alias '{name}'"
    # Negative: random strings rejected
    assert not regex.match("claude-opus-5")  # full IDs not accepted via config


def test_review_summarize_models_use_same_regex():
    """All three model fields share the same alias set — adding one to
    `default_model` without `review_model` would surprise operators."""
    from set_orch.config import _VALIDATORS as DIRECTIVE_VALIDATORS

    p1 = DIRECTIVE_VALIDATORS["default_model"][1]
    p2 = DIRECTIVE_VALIDATORS["review_model"][1]
    p3 = DIRECTIVE_VALIDATORS["summarize_model"][1]
    assert p1 == p2 == p3
