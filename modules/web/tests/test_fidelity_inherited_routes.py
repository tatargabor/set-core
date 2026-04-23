"""Test that extra-route violations respect routes inherited from main."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import pytest

from set_project_web.v0_fidelity_gate import (
    run_skeleton_check,
    _enumerate_routes_at_ref,
)


def _make_manifest(route_paths: list[str]) -> SimpleNamespace:
    routes = [SimpleNamespace(path=p) for p in route_paths]
    return SimpleNamespace(
        routes=routes,
        shared=[],
        shared_aliases={},
        deferred_design_routes=[],
    )


@pytest.fixture
def agent_worktree(tmp_path: Path) -> Path:
    """Scaffold a minimal Next.js app tree with several page.tsx files."""
    app = tmp_path / "src" / "app"
    for route in ["admin", "admin/login", "admin/403", "bundles", "coffees", "stories"]:
        p = app / route / "page.tsx"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("export default function P() { return <div/> }")
    # Root page
    (app / "page.tsx").write_text("export default function P() { return <div/> }")
    return tmp_path


def test_extra_route_without_base_routes_flags_everything_not_in_manifest(
    agent_worktree: Path, tmp_path: Path,
) -> None:
    """Baseline: when base_routes is not supplied, existing behaviour."""
    manifest = _make_manifest(["/stories"])  # only /stories is authorised
    v0 = tmp_path / "v0-export"
    v0.mkdir()

    violations = run_skeleton_check(agent_worktree, v0, manifest)
    extras = [v for v in violations if v.status == "extra-route"]
    extra_paths = {v.detail.split()[1] for v in extras}
    # Everything except the root and /stories is flagged
    assert "/admin" in extra_paths
    assert "/admin/login" in extra_paths
    assert "/bundles" in extra_paths


def test_extra_route_with_base_routes_excludes_inherited(
    agent_worktree: Path, tmp_path: Path,
) -> None:
    """When base_routes includes inherited pages, don't flag them."""
    manifest = _make_manifest(["/stories"])
    v0 = tmp_path / "v0-export"
    v0.mkdir()

    inherited = {"/admin", "/admin/login", "/admin/403", "/bundles", "/coffees"}
    violations = run_skeleton_check(
        agent_worktree, v0, manifest, base_routes=inherited,
    )
    extras = [v for v in violations if v.status == "extra-route"]
    extra_paths = {v.detail.split()[1] for v in extras}
    # The inherited routes must NOT be in the violation list
    for p in inherited:
        assert p not in extra_paths, f"{p} should not be flagged (inherited)"


def test_agent_added_route_still_flagged_when_inherited_provided(
    agent_worktree: Path, tmp_path: Path,
) -> None:
    """Guard: a NEW route the agent added that's not in manifest OR base still fires."""
    # Agent adds a brand-new /zoltan-debug page
    (agent_worktree / "src" / "app" / "zoltan-debug" / "page.tsx").parent.mkdir(parents=True)
    (agent_worktree / "src" / "app" / "zoltan-debug" / "page.tsx").write_text(
        "export default function P() { return <div/> }",
    )
    manifest = _make_manifest(["/stories"])
    v0 = tmp_path / "v0-export"
    v0.mkdir()

    inherited = {"/admin", "/admin/login", "/bundles"}  # /zoltan-debug NOT in here
    violations = run_skeleton_check(
        agent_worktree, v0, manifest, base_routes=inherited,
    )
    extras = [v for v in violations if v.status == "extra-route"]
    extra_paths = {v.detail.split()[1] for v in extras}
    assert "/zoltan-debug" in extra_paths


def test_empty_base_routes_no_op(agent_worktree: Path, tmp_path: Path) -> None:
    """base_routes=set() should behave identically to None."""
    manifest = _make_manifest(["/stories"])
    v0 = tmp_path / "v0-export"
    v0.mkdir()

    v1 = run_skeleton_check(agent_worktree, v0, manifest, base_routes=None)
    v2 = run_skeleton_check(agent_worktree, v0, manifest, base_routes=set())
    # Both should produce the same extra-route set
    e1 = {v.detail for v in v1 if v.status == "extra-route"}
    e2 = {v.detail for v in v2 if v.status == "extra-route"}
    assert e1 == e2


def test_enumerate_routes_at_ref_parses_ls_tree_output(tmp_path: Path) -> None:
    """The git ls-tree helper correctly extracts route segments from paths."""
    import subprocess
    ls_tree_stdout = "\n".join([
        "README.md",
        "src/app/page.tsx",
        "src/app/admin/page.tsx",
        "src/app/admin/login/page.tsx",
        "src/app/[locale]/about/page.tsx",       # [locale] stripped
        "src/app/(marketing)/pricing/page.tsx",  # (group) stripped
        "src/app/api/webhook/route.ts",          # not page.tsx
        "tests/foo.spec.ts",                     # not under app/
    ])
    mock_result = SimpleNamespace(returncode=0, stdout=ls_tree_stdout, stderr="")
    with patch("subprocess.run", return_value=mock_result):
        routes = _enumerate_routes_at_ref(tmp_path, "deadbeef")
    assert routes == {"/", "/admin", "/admin/login", "/about", "/pricing"}


def test_enumerate_routes_at_ref_graceful_on_git_failure(tmp_path: Path) -> None:
    """Git failure returns empty set, does not raise."""
    import subprocess
    mock_result = SimpleNamespace(returncode=128, stdout="", stderr="not a repo")
    with patch("subprocess.run", return_value=mock_result):
        routes = _enumerate_routes_at_ref(tmp_path, "deadbeef")
    assert routes == set()


def test_enumerate_routes_at_ref_handles_subprocess_exception(
    tmp_path: Path,
) -> None:
    """OSError from subprocess.run returns empty set."""
    with patch("subprocess.run", side_effect=OSError("no git")):
        routes = _enumerate_routes_at_ref(tmp_path, "deadbeef")
    assert routes == set()
