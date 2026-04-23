"""Verify the i18n agent-prompt pre-submit self-check section is intact."""

from __future__ import annotations

from pathlib import Path


RULES = (
    Path(__file__).resolve().parents[2]
    / "modules" / "web" / "set_project_web"
    / "templates" / "nextjs" / "rules" / "i18n-conventions.md"
)


def _content() -> str:
    return RULES.read_text()


def test_rules_file_exists() -> None:
    assert RULES.is_file()


def test_mandatory_presubmit_section_present() -> None:
    # Heading + MANDATORY marker
    assert "MANDATORY pre-submit self-check" in _content()


def test_presubmit_names_the_exact_script() -> None:
    # The script file must exist at this path (so the command isn't a lie)
    scripts_dir = RULES.parent.parent / "scripts"
    script_path = scripts_dir / "check-i18n-completeness.ts"
    assert script_path.is_file(), f"script missing at {script_path}"
    assert "pnpm tsx scripts/check-i18n-completeness.ts" in _content()


def test_presubmit_mentions_both_locales() -> None:
    # The rule must reference both en and hu message files
    c = _content()
    assert "messages/en.json" in c
    assert "messages/hu.json" in c


def test_presubmit_explains_the_cost_of_skipping() -> None:
    # Motivation: agents respond better when the cost is explicit
    c = _content()
    assert "retry slot" in c
    # Dimension of waste should be quantified (minutes, not vague)
    assert "~3 minutes" in c or "3 minutes" in c


def test_presubmit_section_before_translation_keys_section() -> None:
    c = _content()
    idx_mandatory = c.find("MANDATORY pre-submit")
    idx_keys = c.find("## Translation Keys")
    assert idx_mandatory > 0 and idx_keys > 0
    assert idx_mandatory < idx_keys, "pre-submit section must come before Translation Keys"
