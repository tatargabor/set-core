"""Chunker: structural sections, breadcrumbs, fences, merge/split, parent link."""

from __future__ import annotations

import hashlib

from set_kb.chunker import MAX_CHUNK_CHARS, MIN_CHUNK_CHARS, chunk_markdown


def sha8(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


BIG = "word " * 25  # a section body below MIN_CHUNK_CHARS merges into its host


def test_sections_and_breadcrumbs():
    res = chunk_markdown("r", "doc.md", f"# Top\n\n{BIG}\n\n## Sub\n\n{BIG}\n")
    assert [c.heading_path for c in res.chunks] == ["Top", "Top > Sub"]
    assert [c.level for c in res.chunks] == [1, 2]
    assert [c.chunk_id for c in res.chunks] == [f"{sha8('doc.md')}:0", f"{sha8('doc.md')}:1"]


def test_preamble_chunk_uses_file_title():
    res = chunk_markdown("r", "notes/readme.md", "preamble before any heading, long enough to stand alone as its own section content.")
    assert res.chunks[0].heading_path == "readme"
    assert res.chunks[0].level == 0


def test_heading_inside_code_fence_is_not_a_heading():
    text = "# Real\n\nbody of the real section, long enough to remain its own chunk in the output.\n\n```python\n# Not a heading, just a comment\nx = 1\n```\n\nmore real body text after the fence to keep the section alive.\n"
    res = chunk_markdown("r", "doc.md", text)
    assert [c.heading for c in res.chunks] == ["Real"]
    assert "Not a heading" in res.chunks[0].body


def test_tiny_section_merges_into_previous():
    big = "x" * (MIN_CHUNK_CHARS + 10)
    text = f"# A\n\n{big}\n\n## B\n\ntiny\n"
    res = chunk_markdown("r", "doc.md", text)
    assert [c.heading_path for c in res.chunks] == ["A"], "the tiny B section merges into A"
    assert "\nB\n" in res.chunks[0].body, "the merged section keeps its heading text in the host body"


def test_oversized_section_splits_by_paragraph():
    para = "word " * 30 + "\n\n"  # ~150 chars per paragraph
    body = para * 40  # ~6000 chars > MAX
    res = chunk_markdown("r", "doc.md", f"# A\n\n{body}")
    assert len(res.chunks) > 1
    assert all(len(c.body) <= MAX_CHUNK_CHARS for c in res.chunks)
    assert all(c.heading_path == "A" for c in res.chunks), "slices share one headingPath"


def test_parent_link_resolves_past_merged_section():
    # `## Tiny` merges into A; Deep's parent must resolve THROUGH the
    # merged-away section to the chunk its text actually ended up in.
    text = f"# A\n\n{BIG}\n\n## Tiny\n\nsmall\n\n### Deep\n\n{BIG}\n"
    res = chunk_markdown("r", "doc.md", text)
    by_heading = {c.heading_path: c for c in res.chunks}
    assert by_heading["A > Tiny > Deep"].parent_chunk_id == by_heading["A"].chunk_id


def test_parent_of_child_of_dropped_heading_is_an_honest_none():
    # `# Empty` has no body → dropped by flush; its child's ancestor chain
    # dead-ends there, so the parent link is null — an honest absence beats a
    # wrong link. (The breadcrumb keeps the dropped heading's title, as the
    # reference does.)
    text = f"# A\n\n{BIG}\n\n# Empty\n\n## B\n\n{BIG}\n"
    res = chunk_markdown("r", "doc.md", text)
    by_heading = {c.heading_path: c for c in res.chunks}
    assert "Empty > B" in by_heading
    assert by_heading["Empty > B"].parent_chunk_id is None


def test_chunk_is_never_its_own_parent():
    # A split section's second slice must not point at itself; the first slice
    # of the SAME section is also not a valid parent.
    para = "word " * 30 + "\n\n"
    body = para * 40
    text = f"# A\n\n{body}\n\n## B\n\n{BIG}\n"
    res = chunk_markdown("r", "doc.md", text)
    a_slices = [c for c in res.chunks if c.heading_path == "A"]
    b = next(c for c in res.chunks if c.heading_path == "A > B")
    assert len(a_slices) > 1, "the oversized section actually split"
    assert all(c.parent_chunk_id != c.chunk_id for c in res.chunks)
    assert b.parent_chunk_id == a_slices[0].chunk_id


def test_body_hash_is_sha256_of_trimmed_body():
    res = chunk_markdown("r", "doc.md", "# A\n\nhello world\n")
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert res.chunks[0].body_hash == expected
    # the body keeps the section's LEADING newline (trimEnd, not trim) — the
    # reference engine's recorded snippets start with the same "\n".
    assert res.chunks[0].body == "\nhello world"


def test_wikilinks_and_md_links():
    text = "see [[Target Name]] and [label](docs/other.md) and [x](../up.md).\n"
    res = chunk_markdown("r", "doc.md", text)
    assert res.wikilinks == ["Target Name"]
    assert sorted(res.md_links) == ["../up.md", "docs/other.md"]


def test_frontmatter_is_stripped_from_chunk_bodies():
    text = '---\ntitle: T\n---\n\n# A\n\nbody\n'
    res = chunk_markdown("r", "doc.md", text)
    assert res.frontmatter == {"title": "T"}
    assert "title" not in res.chunks[0].body


def test_crlf_input_is_normalised():
    res = chunk_markdown("r", "doc.md", "# A\r\n\r\nbody text\r\n")
    assert res.chunks[0].body == "\nbody text"
