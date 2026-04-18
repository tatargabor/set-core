"""Tests for WebProjectType design-source provider (Section 3)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
import yaml


def _install_v0_project(tmp_path: Path) -> Path:
    """Create a minimal project with a valid v0-export and manifest."""
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "scaffold.yaml").write_text("project_type: web\ntemplate: nextjs\nui_library: shadcn\n")

    # Build ZIP and import
    zip_path = tmp_path / "v0.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("app/page.tsx", '<h1>Home</h1>\n')
        zf.writestr("app/globals.css", ":root { --primary: #333; --accent: #78350F; }\n")
        zf.writestr("app/layout.tsx", "export default function L(){return null}")
        zf.writestr(
            "app/kavek/page.tsx",
            'import Card from "@/components/product-card"\n<h1>Coffees</h1>',
        )
        zf.writestr("components/product-card.tsx", "export default function Card(){return null}")
        zf.writestr("components/ui/button.tsx", "export const Button = null")
        zf.writestr("components/header.tsx", "export function Header(){return null}")
        zf.writestr("package.json", '{"name":"v0-test"}')
    zip_path.write_bytes(buf.getvalue())

    from set_project_web.v0_importer import import_v0_zip

    import_v0_zip(zip_path, proj)
    return proj


def test_detect_design_source_v0(tmp_path: Path):
    from set_project_web.project_type import WebProjectType

    proj = _install_v0_project(tmp_path)
    wp = WebProjectType()
    assert wp.detect_design_source(proj) == "v0"


def test_detect_design_source_none(tmp_path: Path):
    from set_project_web.project_type import WebProjectType

    proj = tmp_path / "empty"
    proj.mkdir()
    wp = WebProjectType()
    assert wp.detect_design_source(proj) == "none"


def test_copy_design_source_slice_scope_match(tmp_path: Path):
    from set_project_web.project_type import WebProjectType

    proj = _install_v0_project(tmp_path)
    dest = proj / "openspec" / "changes" / "add-kavek" / "design-source"

    wp = WebProjectType()
    copied = wp.copy_design_source_slice("add-kavek", "kavek catalog page", dest)
    assert any("kavek/page.tsx" in str(c) for c in copied)
    assert any("product-card.tsx" in str(c) for c in copied)
    # Shared files always included
    assert any("components/ui/button.tsx" in str(c) for c in copied)
    assert any("app/layout.tsx" in str(c) for c in copied)


def test_copy_design_source_slice_explicit_routes(tmp_path: Path):
    from set_project_web.project_type import WebProjectType

    proj = _install_v0_project(tmp_path)
    dest = proj / "openspec" / "changes" / "home" / "design-source"
    wp = WebProjectType()

    copied = wp.copy_design_source_slice(
        "home", "anything", dest, design_routes=["/"],
    )
    assert any("app/page.tsx" in str(c) for c in copied)
    # /kavek/page.tsx should NOT be in slice when design_routes=["/"]
    assert not any("kavek/page.tsx" in str(c) for c in copied)


def test_explicit_design_route_missing_raises(tmp_path: Path):
    from set_project_web.project_type import WebProjectType
    from set_project_web.v0_manifest import ManifestError

    proj = _install_v0_project(tmp_path)
    dest = proj / "openspec" / "changes" / "bad" / "design-source"
    wp = WebProjectType()
    with pytest.raises(ManifestError):
        wp.copy_design_source_slice(
            "bad", "x", dest, design_routes=["/not-there"],
        )


def test_ui_bound_scope_without_match_raises(tmp_path: Path):
    from set_project_web.project_type import WebProjectType
    from set_project_web.v0_manifest import NoMatchingRouteError

    proj = _install_v0_project(tmp_path)
    dest = proj / "openspec" / "changes" / "nomatch" / "design-source"
    wp = WebProjectType()
    with pytest.raises(NoMatchingRouteError):
        wp.copy_design_source_slice(
            "nomatch", "render onboarding page", dest,
        )


def test_non_ui_scope_without_match_returns_shared_only(tmp_path: Path):
    from set_project_web.project_type import WebProjectType

    proj = _install_v0_project(tmp_path)
    dest = proj / "openspec" / "changes" / "data-only" / "design-source"
    wp = WebProjectType()
    copied = wp.copy_design_source_slice(
        "data-only", "migrate db schema for users", dest,
    )
    # Only shared files are copied; no route pages
    assert not any("/page.tsx" in str(c).replace("\\", "/").split("app")[-1] for c in copied if "app/page.tsx" in str(c))
    # Shared included
    assert any("app/layout.tsx" in str(c) for c in copied)


def test_dispatch_context_contains_pointer_and_tokens(tmp_path: Path):
    from set_project_web.project_type import WebProjectType

    proj = _install_v0_project(tmp_path)
    dest = proj / "openspec" / "changes" / "home" / "design-source"
    wp = WebProjectType()
    wp.copy_design_source_slice("home", "home hero", dest)

    md = wp.get_design_dispatch_context("home", "home hero", proj)
    assert "openspec/changes/home/design-source" in md
    assert "Design Tokens" in md
    assert "--primary" in md
    assert len(md.splitlines()) <= 200


def test_dispatch_context_no_v0_returns_empty(tmp_path: Path):
    from set_project_web.project_type import WebProjectType

    proj = tmp_path / "empty"
    proj.mkdir()
    wp = WebProjectType()
    assert wp.get_design_dispatch_context("x", "scope", proj) == ""


def test_validate_plan_design_coverage_opt_in(tmp_path: Path):
    from set_project_web.project_type import WebProjectType

    proj = _install_v0_project(tmp_path)
    wp = WebProjectType()

    # Legacy plan (no design_routes anywhere) → skipped, returns []
    legacy = {"changes": [{"name": "c1", "scope": "foo"}]}
    assert wp.validate_plan_design_coverage(legacy, proj) == []

    # Design-aware plan: missing route
    incomplete = {
        "changes": [{"name": "c1", "design_routes": ["/"]}],
        # /kavek is unassigned, will fail
    }
    vs = wp.validate_plan_design_coverage(incomplete, proj)
    assert any("/kavek" in v and "not assigned" in v for v in vs)

    # Complete with deferred
    complete = {
        "changes": [{"name": "c1", "design_routes": ["/"]}],
        "deferred_design_routes": [{"route": "/kavek", "reason": "phase-2"}],
    }
    vs = wp.validate_plan_design_coverage(complete, proj)
    assert vs == []

    # Double-assignment error
    dup = {
        "changes": [
            {"name": "c1", "design_routes": ["/"]},
            {"name": "c2", "design_routes": ["/"]},
        ],
        "deferred_design_routes": [{"route": "/kavek", "reason": "later"}],
    }
    vs = wp.validate_plan_design_coverage(dup, proj)
    assert any("multiple changes" in v for v in vs)
