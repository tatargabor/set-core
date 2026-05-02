"""Tests for model-config-unified: planner prompt foundational→opus fix."""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.templates import (
    render_planning_prompt,
    render_brief_prompt,
    render_domain_decompose_prompt,
)


def _baseline_planning_prompt():
    """Render the spec-mode planning prompt with minimal kwargs."""
    return render_planning_prompt(
        input_content="example spec content",
        specs="",
        memory="",
        replan_ctx=None,
        mode="spec",
        phase_instruction="",
        input_mode="",
        test_infra_context="",
        pk_context="",
        req_context="",
        active_changes="",
        coverage_info="",
        design_context="",
        team_mode=False,
        max_parallel=3,
    )


def test_planning_prompt_groups_foundational_with_opus():
    out = _baseline_planning_prompt()
    body = out.lower()
    # Phrase tying foundational to opus
    assert "foundational" in body
    # Must NOT downgrade foundational to sonnet
    # Look for the explicit instruction; the precise phrasing may vary
    assert ('"opus" for `feature` and `foundational`' in out or
            'opus" for `feature` AND `foundational`' in out or
            ('foundational' in out and 'do NOT downgrade them to sonnet' in out))


def test_planning_prompt_does_not_say_foundational_uses_sonnet():
    out = _baseline_planning_prompt()
    body = out.lower()
    # Reject text patterns that would route foundational → sonnet
    # The actual prompt now lists which change_types may use sonnet — and
    # foundational is explicitly NOT in that list. Verify by absence:
    bad_phrases = [
        '"sonnet" for infrastructure, foundational',
        '"sonnet" for foundational',
        "sonnet for foundational",
    ]
    for bad in bad_phrases:
        assert bad.lower() not in body, f"prompt still routes foundational → sonnet: {bad!r}"


def test_planning_prompt_names_sonnet_allowed_change_types():
    out = _baseline_planning_prompt()
    # The four change_types where sonnet is acceptable
    for ct in ("infrastructure", "schema", "cleanup-before", "cleanup-after"):
        assert ct in out, f"missing sonnet-allowed change_type: {ct}"


def test_planning_prompt_advises_opus_when_unsure():
    out = _baseline_planning_prompt().lower()
    # The prompt advises opus as the safer default for ambiguous cases.
    assert ("when in doubt" in out or "when unsure" in out
            or "in doubt, use" in out or "doubt, use \"opus\"" in out)
