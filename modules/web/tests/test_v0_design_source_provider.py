"""Tests for WebProjectType design-source provider (Section 3).

The v0 pipeline gives agents full reference access to v0-export/ via a
symlink in the worktree (created by the dispatcher). This suite covers
the `get_design_dispatch_context` markdown output that orients the agent
toward focus files + shared layer + tokens.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest


def _install_v0_project(tmp_path: Path) -> Path:
    """Create a minimal project with a valid v0-export and manifest."""
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "scaffold.yaml").write_text("project_type: web\ntemplate: nextjs\nui_library: shadcn\n")

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


def test_dispatch_context_contains_v0_export_pointer(tmp_path: Path):
    from set_project_web.project_type import WebProjectType

    proj = _install_v0_project(tmp_path)
    wp = WebProjectType()

    md = wp.get_design_dispatch_context("home", "home hero landing page", proj)
    assert "## Design Source" in md
    assert "v0-export/" in md  # agent is pointed at the symlinked tree
    assert "## Focus files" not in md or "### Focus files" in md  # focus section present
    assert "### Always-available shared layer" in md
    assert "### Design Tokens" in md
    assert "--primary" in md


def test_dispatch_context_focus_files_from_scope(tmp_path: Path):
    from set_project_web.project_type import WebProjectType

    proj = _install_v0_project(tmp_path)
    wp = WebProjectType()

    md = wp.get_design_dispatch_context("c1", "implement kavek catalog listing", proj)
    # /kavek route should appear in focus files
    assert "app/kavek/page.tsx" in md
    # product-card component_dep should also appear
    assert "components/product-card.tsx" in md


def test_dispatch_context_no_focus_for_non_ui_scope(tmp_path: Path):
    from set_project_web.project_type import WebProjectType

    proj = _install_v0_project(tmp_path)
    wp = WebProjectType()

    md = wp.get_design_dispatch_context("db", "migrate prisma schema for users", proj)
    # Non-UI scope: no route keyword match → no "Focus files" section,
    # but shared layer and tokens still present (agent reads v0-export/
    # directly if it ever needs design info).
    assert "### Focus files" not in md
    assert "### Always-available shared layer" in md


def test_dispatch_context_no_v0_returns_empty(tmp_path: Path):
    from set_project_web.project_type import WebProjectType

    proj = tmp_path / "empty"
    proj.mkdir()
    wp = WebProjectType()
    assert wp.get_design_dispatch_context("x", "scope", proj) == ""


def test_dispatch_context_under_200_lines(tmp_path: Path):
    from set_project_web.project_type import WebProjectType

    proj = _install_v0_project(tmp_path)
    wp = WebProjectType()

    md = wp.get_design_dispatch_context("home", "home hero landing page", proj)
    assert len(md.splitlines()) <= 200


def test_copy_design_source_slice_removed_from_abc():
    """Per architectural simplification: the slice copy method is gone.

    Agents now get full v0-export/ via a worktree symlink; per-change
    slicing under openspec/changes/<name>/design-source/ is obsolete.
    """
    from set_orch.profile_types import ProjectType

    assert not hasattr(ProjectType, "copy_design_source_slice"), \
        "copy_design_source_slice should be removed in favour of v0-export symlink deploy"


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


def test_deploy_v0_export_to_worktree_symlink(tmp_path: Path):
    """The dispatcher helper creates a symlink <wt>/v0-export → <project>/v0-export."""
    from set_orch.dispatcher import _deploy_v0_export_to_worktree

    proj = _install_v0_project(tmp_path)
    wt = tmp_path / "wt-some-change"
    wt.mkdir()

    assert _deploy_v0_export_to_worktree(str(proj), str(wt)) is True
    link = wt / "v0-export"
    assert link.is_symlink()
    assert (link / "app" / "page.tsx").is_file()  # resolves through symlink

    # Idempotent: second call is a no-op
    assert _deploy_v0_export_to_worktree(str(proj), str(wt)) is True


def test_deploy_v0_export_no_source_returns_false(tmp_path: Path):
    from set_orch.dispatcher import _deploy_v0_export_to_worktree

    proj = tmp_path / "noproj"
    proj.mkdir()
    wt = tmp_path / "wt"
    wt.mkdir()
    assert _deploy_v0_export_to_worktree(str(proj), str(wt)) is False
    assert not (wt / "v0-export").exists()
