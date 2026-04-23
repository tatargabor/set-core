"""Template-content test for the nextjs .gitignore shipped with set-project init."""

from __future__ import annotations

from pathlib import Path


TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "modules"
    / "web"
    / "set_project_web"
    / "templates"
    / "nextjs"
    / ".gitignore"
)


def _lines() -> list[str]:
    return [line.strip() for line in TEMPLATE.read_text().splitlines()]


def test_template_gitignore_exists() -> None:
    assert TEMPLATE.is_file(), f"expected template at {TEMPLATE}"


def test_per_change_journal_dir_gitignored() -> None:
    assert "journals/" in _lines()


def test_rotated_event_log_pattern_gitignored() -> None:
    assert "orchestration-events-*.jsonl" in _lines()


def test_activity_detail_cache_gitignored() -> None:
    assert "set/orchestration/activity-detail-*.jsonl" in _lines()


def test_spec_coverage_history_gitignored() -> None:
    assert "set/orchestration/spec-coverage-history.jsonl" in _lines()


def test_e2e_manifest_history_gitignored() -> None:
    assert "set/orchestration/e2e-manifest-history.jsonl" in _lines()


def test_preexisting_runtime_dir_still_gitignored() -> None:
    """Regression: the `/.set/` entry must remain alongside the new entries."""
    assert "/.set/" in _lines()


def test_set_orchestration_dir_is_not_wholesale_ignored() -> None:
    """We want specific patterns, not the whole dir — protects hand-written files."""
    # No naive "set/orchestration/" entry that would swallow all files
    assert "set/orchestration/" not in _lines()
    assert "set/" not in _lines()
