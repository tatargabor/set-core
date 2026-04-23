"""Unit tests for INVESTIGATION_PROMPT content."""

from __future__ import annotations

from set_orch.issues.investigator import INVESTIGATION_PROMPT


def _rendered() -> str:
    return INVESTIGATION_PROMPT.format(
        issue_id="ISS-001",
        change_name="fix-iss-001-x",
        environment="test-env",
        error_detail="boom",
        affected_change="parent-change",
    )


def test_prompt_includes_corruption_section() -> None:
    text = _rendered()
    assert "Source corruption recognition" in text


def test_prompt_names_duplicate_imports_pattern() -> None:
    text = _rendered()
    assert "duplicate top-level imports" in text or "duplicate imports" in text


def test_prompt_names_repeated_blocks_pattern() -> None:
    text = _rendered()
    assert "repeated blocks of code" in text or "repeated blocks" in text


def test_prompt_names_merge_markers_pattern() -> None:
    text = _rendered()
    assert "<<<<<<<" in text
    assert ">>>>>>>" in text


def test_prompt_prescribes_git_diff_step() -> None:
    text = _rendered()
    assert "git diff HEAD~1" in text


def test_prompt_permits_partial_diagnosis() -> None:
    text = _rendered()
    # The agent must be told it's OK to exit early with a partial diagnosis
    assert "partial diagnosis" in text.lower()


def test_prompt_names_specific_root_cause_phrase() -> None:
    text = _rendered()
    # Agents should anchor on this exact phrase when the corruption pattern is detected
    assert "source corruption" in text.lower()
