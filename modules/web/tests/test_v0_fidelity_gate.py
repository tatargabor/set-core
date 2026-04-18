"""Unit tests for v0 fidelity gate — skeleton check + config + registration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest


@dataclass
class FakeRoute:
    path: str
    files: list = field(default_factory=list)
    component_deps: list = field(default_factory=list)
    scope_keywords: list = field(default_factory=list)
    fidelity_threshold: float = None


@dataclass
class FakeManifest:
    routes: list
    shared: list = field(default_factory=list)
    shared_aliases: dict = field(default_factory=dict)


def _make_agent_tree(root: Path, routes: list[str], shared_files: list[str] = None) -> None:
    """Create a fake agent worktree with Next.js app router."""
    app = root / "app"
    app.mkdir(parents=True, exist_ok=True)
    for rp in routes:
        if rp == "/":
            target = app / "page.tsx"
        else:
            d = app
            for seg in rp.strip("/").split("/"):
                d = d / seg
            d.mkdir(parents=True, exist_ok=True)
            target = d / "page.tsx"
        target.write_text("export default function P(){return null}")
    for sh in shared_files or []:
        target = root / sh
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("export function X(){return null}")


def test_skeleton_check_matching(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    v0.mkdir()

    _make_agent_tree(agent, ["/", "/kavek"], ["components/ui/button.tsx", "components/header.tsx", "app/layout.tsx"])
    manifest = FakeManifest(
        routes=[FakeRoute("/"), FakeRoute("/kavek")],
        shared=[
            "v0-export/components/ui/**",
            "v0-export/components/header.tsx",
            "v0-export/app/layout.tsx",
        ],
    )

    violations = run_skeleton_check(agent, v0, manifest)
    assert violations == []


def test_skeleton_check_missing_route(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    v0.mkdir()
    _make_agent_tree(agent, ["/"], ["components/header.tsx", "app/layout.tsx"])
    manifest = FakeManifest(
        routes=[FakeRoute("/"), FakeRoute("/kavek")],
        shared=["v0-export/components/header.tsx", "v0-export/app/layout.tsx"],
    )
    violations = run_skeleton_check(agent, v0, manifest)
    assert any(v.status == "missing-route" and "/kavek" in v.detail for v in violations)


def test_skeleton_check_extra_route(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    v0.mkdir()
    _make_agent_tree(agent, ["/", "/bonus"], ["components/header.tsx", "app/layout.tsx"])
    manifest = FakeManifest(
        routes=[FakeRoute("/")],
        shared=["v0-export/components/header.tsx", "v0-export/app/layout.tsx"],
    )
    violations = run_skeleton_check(agent, v0, manifest)
    assert any(v.status == "extra-route" and "/bonus" in v.detail for v in violations)


def test_skeleton_check_missing_shared_file(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    v0.mkdir()
    _make_agent_tree(agent, ["/"], ["app/layout.tsx"])  # no header.tsx
    manifest = FakeManifest(
        routes=[FakeRoute("/")],
        shared=["v0-export/components/header.tsx", "v0-export/app/layout.tsx"],
    )
    violations = run_skeleton_check(agent, v0, manifest)
    assert any(v.status == "missing-shared-file" and "header.tsx" in v.detail for v in violations)


def test_skeleton_check_alias_tolerance(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    v0.mkdir()
    _make_agent_tree(agent, ["/"], ["components/site-header.tsx", "app/layout.tsx"])
    manifest = FakeManifest(
        routes=[FakeRoute("/")],
        shared=["v0-export/components/header.tsx", "v0-export/app/layout.tsx"],
        shared_aliases={"header.tsx": "site-header.tsx"},
    )
    violations = run_skeleton_check(agent, v0, manifest)
    # With alias, header.tsx → site-header.tsx should be tolerated
    assert not any("header.tsx" in v.detail for v in violations)


def test_skeleton_check_decomposition_collapsed(tmp_path: Path):
    from set_project_web.v0_fidelity_gate import run_skeleton_check

    agent = tmp_path / "agent"
    v0 = tmp_path / "v0-export"
    v0.mkdir()
    (agent / "components").mkdir(parents=True)
    # File exists but no export → decomposition collapsed
    (agent / "components" / "header.tsx").write_text("// nothing exported")
    (agent / "app").mkdir()
    (agent / "app" / "layout.tsx").write_text("export default function L(){return null}")
    (agent / "app" / "page.tsx").write_text("export default function P(){return null}")
    manifest = FakeManifest(
        routes=[FakeRoute("/")],
        shared=["v0-export/components/header.tsx", "v0-export/app/layout.tsx"],
    )
    violations = run_skeleton_check(agent, v0, manifest)
    assert any(v.status == "decomposition-collapsed" for v in violations)


def test_gate_registered_in_web_profile():
    from set_project_web.project_type import WebProjectType

    wp = WebProjectType()
    names = [g.name for g in wp.register_gates()]
    assert "design-fidelity" in names


def test_warn_only_flag_read(tmp_path: Path):
    import yaml

    from set_project_web.v0_fidelity_gate import _read_warn_only_flag

    cfg = tmp_path / "set" / "orchestration" / "config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(yaml.safe_dump({"gates": {"design-fidelity": {"warn_only": True}}}))
    assert _read_warn_only_flag(tmp_path) is True
    assert _read_warn_only_flag(tmp_path.parent) is False
