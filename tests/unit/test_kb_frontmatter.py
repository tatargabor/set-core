"""Frontmatter parser: bounded YAML subset, total and pure."""

from __future__ import annotations

from set_kb.frontmatter import (
    DEFAULT_FACET_KEYS,
    DEFAULT_SEARCHABLE_KEYS,
    build_meta,
    build_properties,
    parse_frontmatter,
)


def test_no_frontmatter():
    r = parse_frontmatter("just text\n")
    assert r.fm is None and r.parse_failed is False and r.body == "just text\n"


def test_unclosed_fence_is_not_frontmatter():
    r = parse_frontmatter("---\ntitle: T\nno closer\n")
    assert r.fm is None and r.parse_failed is False


def test_scalars():
    r = parse_frontmatter("---\na: 1\nb: 1.5\nc: true\nd: false\ne: plain\n---\nbody")
    assert r.fm == {"a": 1, "b": 1.5, "c": True, "d": False, "e": "plain"}
    assert r.body == "body"


def test_quoted_value_with_escaped_quote_is_not_truncated():
    r = parse_frontmatter('---\ntitle: "A \\"quoted\\" tail" # comment\n---\nbody\n')
    assert r.fm["title"] == 'A "quoted" tail'


def test_single_quoted_doubling():
    r = parse_frontmatter("---\ntitle: 'it''s here'\n---\n")
    assert r.fm["title"] == "it's here"


def test_inline_array_and_block_list():
    r = parse_frontmatter('---\ntags: [one, "two", three]\nothers:\n  - a\n  - b\n---\n')
    assert r.fm["tags"] == ["one", "two", "three"]
    assert r.fm["others"] == ["a", "b"]


def test_block_scalars_pipe_and_fold():
    r = parse_frontmatter("---\nnote: |\n  line one\n  line two\nfolded: >\n  a b\n  c\n---\n")
    assert r.fm["note"] == "line one\nline two"
    assert r.fm["folded"] == "a b c"


def test_nested_map_is_skipped_silently():
    r = parse_frontmatter("---\nmeta:\n  inner: x\n  more: y\nafter: 1\n---\n")
    assert "meta" not in r.fm
    assert r.fm["after"] == 1
    assert r.parse_failed is False


def test_kb_key_subtree_is_discarded():
    r = parse_frontmatter("---\nkb:\n  secret: x\n  nested:\n    deep: y\ntitle: T\n---\n")
    assert "kb" not in r.fm
    assert r.fm["title"] == "T"


def test_parse_failed_is_loud_for_an_unparsable_line():
    r = parse_frontmatter("---\ntitle: T\n: no key here\n---\n")
    assert r.fm["title"] == "T"
    assert r.parse_failed is True


def test_crlf_and_bom():
    r = parse_frontmatter("﻿---\r\ntitle: T\r\n---\r\nbody\r\n")
    assert r.fm == {"title": "T"}
    assert r.body == "body\n" or r.body == "body"


def test_unicode_key():
    r = parse_frontmatter("---\ngenerálva: 2026-01-01\n---\n")
    assert r.fm["generálva"] == "2026-01-01"


def test_build_meta_routes_title_and_rest():
    fm = {"title": "The Title", "description": "desc words", "tags": ["t"]}
    meta = build_meta(fm, DEFAULT_SEARCHABLE_KEYS)
    assert meta["title"] == "The Title"
    assert meta["body"] == "desc words"
    assert "t" not in meta["body"]


def test_build_properties_dedups_and_types():
    fm = {"tags": ["Alpha", "alpha", "beta"], "date": "2026-02-30", "when": "2026-02-28"}
    keys = [{"key": "tags"}, {"key": "date", "type": "date"}, {"key": "when", "type": "date"}]
    rows = build_properties(fm, keys)
    by = {(r["key"], r["value"]): r for r in rows}
    assert ("tags", "alpha") in by and ("tags", "beta") in by, "duplicates collapse"
    assert by[("date", "2026-02-30")]["value_date"] is None, "impossible calendar date coerces to no date"
    assert by[("when", "2026-02-28")]["value_date"] == "2026-02-28"


def test_build_properties_numbers():
    fm = {"n": "42.5", "bad": "1e999"}
    rows = build_properties(fm, [{"key": "n", "type": "number"}, {"key": "bad", "type": "number"}])
    by_key = {r["key"]: r for r in rows}
    assert by_key["n"]["value_num"] == 42.5
    assert by_key["bad"]["value_num"] is None  # not a clean finite number
