"""Unit tests for spec entity-reference parser (`design-binding-completeness`).

The parser extracts `@component:NAME` and `@route:/PATH` markers from spec
text. The validator checks them against a loaded Manifest. Both are used
by the decompose skill to populate per-change `design_components` and to
emit `design_gap` ambiguities for unresolved references.
"""

from __future__ import annotations

from set_orch.design_manifest import Manifest, RouteEntry
from set_orch.spec_parser import (
    EntityRef,
    extract_design_references,
    resolve_component_paths,
    resolve_route_paths,
    validate_references,
)


def test_extract_single_component_marker():
    spec = "Users open @component:search-palette to find products."
    refs = extract_design_references(spec)
    assert len(refs) == 1
    assert refs[0] == EntityRef(
        kind="component",
        name="search-palette",
        line=1,
        raw="@component:search-palette",
    )


def test_extract_single_route_marker():
    spec = "Results page lives at @route:/kereses."
    refs = extract_design_references(spec)
    assert len(refs) == 1
    assert refs[0].kind == "route"
    assert refs[0].name == "/kereses"


def test_extract_multiple_markers_in_doc_order():
    spec = (
        "## REQ-X\n"
        "Users click @component:site-header search icon to open @component:search-palette.\n"
        "Results render at @route:/kereses with @component:product-card grid.\n"
    )
    refs = extract_design_references(spec)
    assert len(refs) == 4
    assert [r.kind for r in refs] == ["component", "component", "route", "component"]
    assert [r.name for r in refs] == [
        "site-header", "search-palette", "/kereses", "product-card",
    ]
    assert [r.line for r in refs] == [2, 2, 3, 3]


def test_extract_strips_trailing_punctuation_from_route():
    spec = "Visit @route:/kereses, then click."
    refs = extract_design_references(spec)
    assert refs[0].name == "/kereses"  # comma stripped


def test_validate_known_component_passes():
    manifest = Manifest(
        shared=["v0-export/components/search-palette.tsx"],
    )
    refs = extract_design_references("@component:search-palette")
    errors = validate_references(refs, manifest)
    assert errors == []


def test_validate_unknown_component_emits_error():
    manifest = Manifest(
        shared=["v0-export/components/search-palette.tsx"],
    )
    refs = extract_design_references("@component:search-foo")
    errors = validate_references(refs, manifest)
    assert len(errors) == 1
    assert errors[0].ref.name == "search-foo"
    assert "search-palette" in errors[0].suggestions


def test_validate_known_route_passes():
    manifest = Manifest(routes=[RouteEntry(path="/kereses")])
    refs = extract_design_references("@route:/kereses")
    errors = validate_references(refs, manifest)
    assert errors == []


def test_validate_unknown_route_emits_error_with_suggestions():
    manifest = Manifest(routes=[
        RouteEntry(path="/kereses"),
        RouteEntry(path="/kavek"),
    ])
    refs = extract_design_references("@route:/searchx")
    errors = validate_references(refs, manifest)
    assert len(errors) == 1
    assert errors[0].ref.name == "/searchx"
    assert "/kereses" in errors[0].suggestions or "/kavek" in errors[0].suggestions


def test_validate_dynamic_route_prefix_match():
    """[slug] manifest entries match concrete sibling URLs."""
    manifest = Manifest(routes=[RouteEntry(path="/kavek/[slug]")])
    # Refs to a concrete URL like /kavek/ethiopia should pass via prefix match
    refs = [EntityRef(kind="route", name="/kavek/[slug]", line=1, raw="@route:/kavek/[slug]")]
    errors = validate_references(refs, manifest)
    assert errors == []


def test_resolve_component_paths():
    manifest = Manifest(shared=[
        "v0-export/components/search-palette.tsx",
        "v0-export/components/site-header.tsx",
    ])
    refs = extract_design_references(
        "Use @component:search-palette and @component:site-header."
    )
    paths = resolve_component_paths(refs, manifest)
    assert paths == [
        "v0-export/components/search-palette.tsx",
        "v0-export/components/site-header.tsx",
    ]


def test_resolve_component_paths_dedupes():
    manifest = Manifest(shared=["v0-export/components/search-palette.tsx"])
    refs = extract_design_references(
        "@component:search-palette here and @component:search-palette there."
    )
    paths = resolve_component_paths(refs, manifest)
    assert paths == ["v0-export/components/search-palette.tsx"]


def test_resolve_route_paths():
    refs = extract_design_references("@route:/kereses and @route:/kavek")
    routes = resolve_route_paths(refs)
    assert routes == ["/kereses", "/kavek"]
