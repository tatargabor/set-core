"""Regression tests for supervisor prompt CLI syntax correctness.

The supervisor agent is prompted with documentation of the allowed CLI.
If the documented syntax drifts from the actual `set-sentinel-finding`
CLI, the agent wastes retries on exit-code-2 usage errors. Observed in
craftbrew-run-20260421-0025: 3+ supervisor sessions tried
`--severity low --message "..."` before falling back to the correct
`--severity observation --summary "..."` form.

These tests lock in the prompt text against the CLI's actual flag names
and severity choices.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.supervisor.prompts import (  # noqa: E402
    STABLE_HEADER,
    build_trigger_prompt,
)

ALLOWED_ACTIONS_HEADER = STABLE_HEADER


# Actual CLI choices (see bin/set-sentinel-finding argparse setup).
_CLI_SEVERITIES = {"bug", "observation", "pattern", "regression"}
# Severity values that used to appear in the prompt but are rejected by the CLI.
_DEPRECATED_SEVERITIES = {"low", "med", "high", "critical"}


def _all_prompt_bodies() -> list[str]:
    """Build every trigger prompt variant so we can scan them all."""
    bodies = [ALLOWED_ACTIONS_HEADER]
    triggers = [
        "process_crash", "integration_failed", "state_stall", "token_stall",
        "non_periodic_checkpoint", "rapid_restart", "log_silence",
        "log_severity_spike", "no_progress", "canary", "_run",
    ]
    for t in triggers:
        try:
            bodies.append(build_trigger_prompt(
                trigger=t, reason="test reason",
                change="test-change",
                context={"tokens": 0, "stall_seconds": 0, "warns": 0, "errors": 0},
                project_path="/tmp/p", spec="docs/spec.md",
            ).full)
        except Exception:
            # Unknown trigger falls back to generic — safe to skip.
            continue
    return bodies


def test_header_uses_cli_flag_names():
    """The `set-sentinel-finding add` invocation must use `--summary`, not `--message`."""
    assert "--summary" in ALLOWED_ACTIONS_HEADER, \
        "prompt header must use --summary (the actual CLI flag)"
    assert "--message" not in ALLOWED_ACTIONS_HEADER, \
        "prompt header must NOT reference --message (pre-existing drift from the CLI)"


def test_header_uses_cli_severity_choices():
    """The documented `--severity` choices must match the CLI's actual enum."""
    for s in _CLI_SEVERITIES:
        assert s in ALLOWED_ACTIONS_HEADER, \
            f"prompt header must list severity={s!r} as an allowed choice"
    for bad in _DEPRECATED_SEVERITIES:
        assert f"<{bad}" not in ALLOWED_ACTIONS_HEADER and f"|{bad}|" not in ALLOWED_ACTIONS_HEADER and f"|{bad}>" not in ALLOWED_ACTIONS_HEADER, \
            f"prompt header must not advertise deprecated severity={bad!r} (CLI rejects it)"


def test_no_deprecated_severity_hints_in_trigger_bodies():
    """Individual trigger bodies must not recommend deprecated severity values."""
    bad_patterns = [f"severity={s}" for s in _DEPRECATED_SEVERITIES]
    for body in _all_prompt_bodies():
        for pat in bad_patterns:
            assert pat not in body, (
                f"prompt body contains deprecated guidance {pat!r}; use one of "
                f"{_CLI_SEVERITIES} instead"
            )
