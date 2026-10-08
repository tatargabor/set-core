"""Scope capture from the path: pattern compilation, per-chunk storage, and
the `--scope` filter (design D9)."""

from __future__ import annotations

import pytest
from conftest_kb import index_root, make_repo, write
from set_kb.indexer import IndexOptions
from set_kb.scopes import ScopeRule, capture_scope, check_pattern, compile_scope_rules
from set_kb.search import SearchOpts, search


def test_placeholder_is_required_and_unique():
    with pytest.raises(ValueError, match=r"\{scope\}"):
        check_pattern("docs/clients/**")
    with pytest.raises(ValueError, match="more than one"):
        check_pattern("docs/{scope}/{scope}/**")
    check_pattern("docs/clients/{scope}/**")  # valid, no raise


def test_capture_from_the_path():
    compiled = compile_scope_rules([ScopeRule(name="client", pattern="docs/clients/{scope}/**")])
    assert capture_scope(compiled, "docs/clients/alfa/mail.md") == "client=alfa"
    assert capture_scope(compiled, "docs/clients/alfa/deep/note.md") == "client=alfa"
    assert capture_scope(compiled, "docs/internal/mail.md") is None


def test_first_matching_rule_wins():
    compiled = compile_scope_rules(
        [
            ScopeRule(name="year", pattern="docs/clients/{scope}/2026/**"),
            ScopeRule(name="client", pattern="docs/clients/{scope}/**"),
        ]
    )
    assert capture_scope(compiled, "docs/clients/alfa/2026/plan.md") == "year=alfa"
    assert capture_scope(compiled, "docs/clients/alfa/plan.md") == "client=alfa"


def test_scope_is_stored_per_chunk_and_filters(tmp_path):
    """AC: WHEN a search is restricted to one client scope THEN no other
    client's file appears on the page."""
    root = make_repo(tmp_path)
    body = "\n\n" + "word " * 30 + "\n"
    # distinct bodies, so exact-content dedup does not collapse the two files
    # into one hit — this test is about scope capture, not about dedup.
    write(root / "docs" / "clients" / "alfa" / "brief.md", "# Alfa brief\n\nalfaword alfacontent" + body)
    write(root / "docs" / "clients" / "beta" / "brief.md", "# Beta brief\n\nalfaword betacontent" + body)
    opts = IndexOptions(scopes=[ScopeRule(name="client", pattern="docs/clients/{scope}/**")])
    store = index_root(tmp_path, root, opts)
    hits = search(store, "alfaword", SearchOpts(lane_quota=0))
    assert {h.scope for h in hits} == {"client=alfa", "client=beta"}, "every hit carries its captured scope"
    only_alfa = search(store, "alfaword", SearchOpts(lane_quota=0, scope="client=alfa"))
    assert [h.path for h in only_alfa] == ["docs/clients/alfa/brief.md"], "no other client's file on the page"
    # the total reflects the restriction too, so the footer's "N more" stays true
    from set_kb.search import count_sources

    assert count_sources(store, "alfaword", SearchOpts(lane_quota=0, scope="client=alfa")) == 1
    # the stored form is what a path fetch sees as well
    assert store.get_chunk("", "docs/clients/alfa/brief.md").scope == "client=alfa"
    store.close()


def test_scope_without_rules_leaves_scope_null(tmp_path):
    root = make_repo(tmp_path)
    write(root / "a.md", "# A\n\n" + "word " * 30 + "\n")
    store = index_root(tmp_path, root)
    hits = search(store, "word", SearchOpts(lane_quota=0))
    assert hits and all(h.scope is None for h in hits)
    # a scope nothing carries is an empty page, not an error
    assert search(store, "word", SearchOpts(lane_quota=0, scope="client=alfa")) == []
    store.close()


def test_meta_chunk_carries_the_scope(tmp_path):
    """The synthetic `:meta` chunk (frontmatter title row) belongs to the same
    file, so it must carry the same scope or a scoped page silently loses
    title hits."""
    root = make_repo(tmp_path)
    write(
        root / "docs" / "clients" / "alfa" / "titled.md",
        "---\ntitle: Titled Note\n---\n\n# Body\n\n" + "word " * 30 + "\n",
    )
    opts = IndexOptions(scopes=[ScopeRule(name="client", pattern="docs/clients/{scope}/**")])
    store = index_root(tmp_path, root, opts)
    hits = search(store, "titled note", SearchOpts(lane_quota=0, scope="client=alfa"))
    assert [h.path for h in hits] == ["docs/clients/alfa/titled.md"]
    assert all(h.scope == "client=alfa" for h in hits)
    store.close()
