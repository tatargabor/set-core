"""get-section resolution: exact, leaf, ambiguous, missing."""

from __future__ import annotations

from set_kb.chunker import chunk_markdown
from set_kb.get_section import leaf_of, resolve_section

BIG = "word " * 25


def chunks():
    text = f"# A\n\n{BIG}\n\n## B\n\n{BIG}\n\n# C\n\n{BIG}\n\n## B\n\n{BIG}\n"
    return chunk_markdown("r", "doc.md", text).chunks


def test_exact_full_heading_path_wins():
    res = resolve_section(chunks(), "A > B")
    assert res.kind == "found"
    assert [c.heading_path for c in res.slices] == ["A > B"]


def test_unique_leaf_resolves_to_whole_section():
    res = resolve_section(chunks(), "C")
    assert res.kind == "found"
    assert res.slices[0].heading_path == "C"


def test_ambiguous_leaf_lists_full_paths_and_prints_nothing():
    res = resolve_section(chunks(), "B")
    assert res.kind == "ambiguous"
    assert sorted(res.candidates) == ["A > B", "C > B"]


def test_missing_section():
    assert resolve_section(chunks(), "Nope").kind == "missing"
    assert resolve_section(chunks(), "  ").kind == "missing"


def test_leaf_of():
    assert leaf_of("A > B > C") == "C"
    assert leaf_of("Only") == "Only"


def test_split_section_returns_all_slices():
    para = "word " * 30 + "\n\n"
    text = f"# A\n\n{para * 40}"
    cs = chunk_markdown("r", "doc.md", text).chunks
    assert len(cs) > 1, "the section actually split"
    res = resolve_section(cs, "A")
    assert res.kind == "found"
    assert res.slices == cs, "ALL slices come back — a single-slice limit would truncate"
