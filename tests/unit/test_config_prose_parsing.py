"""A regex cannot tell an instruction from an example of an instruction.

`parse_directives` and `parse_next_items` read state out of a hand-written markdown
document. A directive shown inside a fenced block to explain the format matches the
pattern exactly as well as a real one — and an orchestration then runs with a
`max_parallel` nobody set, which is a silent, plausible-looking wrong answer rather
than a crash.

This is a recurring class, not an oversight. It was measured on a consumer four times
in one day: a comment supplying a CI test runner's name, a commented-out example read
as a real endpoint, an explanatory sentence read as a variable declaration, and prose
read as a cron expression. Every time, the comment looked exactly like the data.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from set_orch.config import (  # noqa: E402
    iter_prose_lines,
    parse_directives,
    parse_next_items,
)


def _doc(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "brief.md"
    path.write_text(body, encoding="utf-8")
    return path


# ─── directives ──────────────────────────────────────────────────────────────

def test_a_real_directive_is_still_read(tmp_path):
    """The guard must not cost the feature it guards."""
    doc = _doc(tmp_path, "## Orchestrator Directives\n- max_parallel: 3\n")

    assert parse_directives(doc)["max_parallel"] == 3


def test_an_example_inside_a_fence_is_not_a_directive(tmp_path):
    """The documented format is documentation, however well it matches.

    Note this one passed before the fix as well, because the later real line
    overwrote the example. It is a guard against over-cutting, not a regression
    test — the regression is the case below, where the example is all there is.
    """
    doc = _doc(tmp_path, (
        "## Orchestrator Directives\n"
        "Write them like this:\n"
        "```yaml\n"
        "- max_parallel: 9\n"
        "```\n"
        "- max_parallel: 2\n"
    ))

    assert parse_directives(doc)["max_parallel"] == 2


def test_a_directive_that_exists_ONLY_as_an_example_falls_back_to_the_default(tmp_path):
    """Nothing was set, so nothing must be read — not even something plausible."""
    doc = _doc(tmp_path, (
        "## Orchestrator Directives\n"
        "```\n- max_parallel: 9\n```\n"
    ))

    assert parse_directives(doc)["max_parallel"] == 1


def test_a_commented_out_directive_is_disabled_not_hidden_in_plain_sight(tmp_path):
    doc = _doc(tmp_path, (
        "## Orchestrator Directives\n"
        "<!-- max_parallel: 9 -->\n"
        "- max_parallel: 4\n"
    ))

    assert parse_directives(doc)["max_parallel"] == 4


def test_a_multi_line_html_comment_stays_a_comment_to_its_end(tmp_path):
    """The commented value must be a VALID one, or the validator hides the defect.

    An earlier version of this test used an invalid `merge_policy`, so it passed
    before the fix too — the comment WAS parsed, and only the enum check stopped it.
    A test that is green either way proves nothing; it just looks like proof.
    """
    doc = _doc(tmp_path, (
        "## Orchestrator Directives\n"
        "<!--\n- max_parallel: 9\n- merge_policy: checkpoint\n-->\n"
        "- max_parallel: 5\n"
    ))

    result = parse_directives(doc)
    assert result["max_parallel"] == 5
    assert result["merge_policy"] == "eager", "a commented directive must not take effect"


def test_a_header_inside_a_fence_does_not_end_the_section(tmp_path):
    """A `##` in an example block is illustration too, and used to truncate the section."""
    doc = _doc(tmp_path, (
        "## Orchestrator Directives\n"
        "```md\n## Some Other Section\n```\n"
        "- max_parallel: 6\n"
    ))

    assert parse_directives(doc)["max_parallel"] == 6


def test_a_real_following_header_still_ends_the_section(tmp_path):
    doc = _doc(tmp_path, (
        "## Orchestrator Directives\n"
        "- max_parallel: 7\n"
        "## Notes\n"
        "- max_parallel: 9\n"
    ))

    assert parse_directives(doc)["max_parallel"] == 7


# ─── next items ──────────────────────────────────────────────────────────────

def test_bullets_in_an_example_block_are_not_next_items(tmp_path):
    doc = _doc(tmp_path, (
        "### Next\n"
        "- real item\n"
        "```\n- example item\n```\n"
    ))

    assert parse_next_items(doc) == ["real item"]


# ─── the filter itself ───────────────────────────────────────────────────────

def test_only_a_matching_marker_closes_a_fence():
    """A ``` inside a ~~~ block is content; treating it as a close reopens the doc."""
    lines = ["~~~", "```", "- max_parallel: 9", "~~~", "kept"]

    assert list(iter_prose_lines(lines)) == ["kept"]


def test_an_unterminated_fence_swallows_the_rest_rather_than_guessing():
    """Reading past an unclosed fence would mean deciding the author meant to close it."""
    lines = ["kept", "```", "- max_parallel: 9"]

    assert list(iter_prose_lines(lines)) == ["kept"]


def test_a_single_line_html_comment_does_not_open_a_block():
    lines = ["<!-- note -->", "kept"]

    assert list(iter_prose_lines(lines)) == ["kept"]


def test_indented_fences_are_recognised():
    lines = ["  ```", "  - max_parallel: 9", "  ```", "kept"]

    assert list(iter_prose_lines(lines)) == ["kept"]


def test_prose_passes_through_untouched():
    lines = ["- a: 1", "", "text"]

    assert list(iter_prose_lines(lines)) == lines
