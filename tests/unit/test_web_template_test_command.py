"""Regression test: web project template ships test_command uncommented.

See OpenSpec change: fix-retry-context-signal-loss (Bug C).

Commenting out `test_command` silently disabled the unit-test gate on every
consumer that copied this template verbatim via `set-project init`. The
gate is a no-op when no test files exist (vitest config ships with
`passWithNoTests: true` in the same template), so leaving it on has no cost
on empty scaffolds but catches regressions on projects that do have tests.
"""

import os
from pathlib import Path

_TEMPLATE = Path(__file__).resolve().parents[2] / (
    "modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml"
)
_VITEST_CONFIG = Path(__file__).resolve().parents[2] / (
    "modules/web/set_project_web/templates/nextjs/vitest.config.ts"
)


def test_test_command_is_uncommented():
    """AC-4: template config.yaml must ship with an active test_command entry."""
    assert _TEMPLATE.exists(), f"Template missing: {_TEMPLATE}"
    text = _TEMPLATE.read_text()
    active_lines = [
        ln for ln in text.splitlines()
        if not ln.lstrip().startswith("#") and ln.strip()
    ]
    assert any(ln.strip().startswith("test_command:") for ln in active_lines), (
        f"test_command must be uncommented in {_TEMPLATE}. "
        f"Active lines: {active_lines!r}"
    )


def test_vitest_config_has_pass_with_no_tests():
    """AC-5: enabling test_command must not break empty scaffolds — relies on
    vitest's passWithNoTests: true in the shipped vitest.config.ts.
    """
    assert _VITEST_CONFIG.exists(), f"Vitest config missing: {_VITEST_CONFIG}"
    text = _VITEST_CONFIG.read_text()
    assert "passWithNoTests: true" in text, (
        f"vitest.config.ts must keep passWithNoTests: true so the "
        f"unit test gate is a no-op on scaffolds without tests. Got: {text!r}"
    )
