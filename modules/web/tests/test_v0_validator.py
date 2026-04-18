"""Unit tests for v0 quality validator."""

from __future__ import annotations

from pathlib import Path

import pytest


def _make_tree(root: Path, pages: dict, components: dict = None) -> None:
    (root / "app").mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text('{"name":"x"}')
    for rp, body in pages.items():
        if rp == "/":
            target = root / "app" / "page.tsx"
        else:
            d = root / "app"
            for s in rp.strip("/").split("/"):
                d = d / s
            d.mkdir(parents=True, exist_ok=True)
            target = d / "page.tsx"
        target.write_text(body)
    if components:
        cd = root / "components"
        cd.mkdir(parents=True, exist_ok=True)
        for name, body in components.items():
            (cd / name).write_text(body)


def test_broken_link_is_blocking(tmp_path: Path):
    from set_project_web.v0_validator import ValidatorConfig, validate_v0_export

    v0 = tmp_path / "v0"
    _make_tree(v0, {
        "/": '<Link href="/nowhere">Click</Link>',
        "/kavek": "<h1>Coffees</h1>",
    })
    cfg = ValidatorConfig(skip_build=True)
    report = validate_v0_export(v0, cfg)
    assert any(f.severity == "BLOCKING" and "nowhere" in f.message for f in report.findings)


def test_broken_link_ignored_with_flag(tmp_path: Path):
    from set_project_web.v0_validator import ValidatorConfig, validate_v0_export

    v0 = tmp_path / "v0"
    _make_tree(v0, {
        "/": '<Link href="/nowhere">Click</Link>',
    })
    cfg = ValidatorConfig(skip_build=True, ignore_navigation=True)
    report = validate_v0_export(v0, cfg)
    # Should be WARNING, not BLOCKING
    nav_findings = [f for f in report.findings if "nowhere" in f.message]
    assert nav_findings and all(f.severity != "BLOCKING" for f in nav_findings)


def test_dynamic_route_link_valid(tmp_path: Path):
    from set_project_web.v0_validator import ValidatorConfig, validate_v0_export

    v0 = tmp_path / "v0"
    _make_tree(v0, {
        "/": '<Link href="/kavek/arabica">Detail</Link>',
        "/kavek/[slug]": "<h1>Detail</h1>",
    })
    cfg = ValidatorConfig(skip_build=True)
    report = validate_v0_export(v0, cfg)
    # /kavek/arabica should match /kavek/[slug]
    assert not any(f.severity == "BLOCKING" and "arabica" in f.message for f in report.findings)


def test_orphan_route_warning(tmp_path: Path):
    from set_project_web.v0_validator import ValidatorConfig, validate_v0_export

    v0 = tmp_path / "v0"
    _make_tree(v0, {
        "/": "<h1>Home</h1>",
        "/orphan": "<h1>Nothing links here</h1>",
    })
    cfg = ValidatorConfig(skip_build=True)
    report = validate_v0_export(v0, cfg)
    assert any(f.section == "Navigation Integrity" and "orphan" in f.message.lower() for f in report.findings)


def test_naming_inconsistencies(tmp_path: Path):
    from set_project_web.v0_validator import ValidatorConfig, validate_v0_export

    v0 = tmp_path / "v0"
    _make_tree(v0, {"/": "<h1>x</h1>"}, components={
        "product-card.tsx": "export default null",
        "product_card_v2.tsx": "export default null",
    })
    cfg = ValidatorConfig(skip_build=True)
    report = validate_v0_export(v0, cfg)
    assert any(f.section == "Naming Inconsistencies" for f in report.findings)


def test_shadcn_consistency_warning(tmp_path: Path):
    from set_project_web.v0_validator import ValidatorConfig, validate_v0_export

    v0 = tmp_path / "v0"
    _make_tree(v0, {
        "/": "<Button>Go</Button>",
        "/foo": "<button>Raw</button>",
    })
    cfg = ValidatorConfig(skip_build=True)
    report = validate_v0_export(v0, cfg)
    assert any(f.section == "shadcn Consistency" for f in report.findings)


def test_strict_quality_promotes_warnings(tmp_path: Path):
    from set_project_web.v0_validator import ValidatorConfig, validate_v0_export

    v0 = tmp_path / "v0"
    _make_tree(v0, {
        "/": "<h1>Home</h1>",
        "/orphan": "<h1>x</h1>",
    })
    cfg = ValidatorConfig(skip_build=True, strict_quality=True)
    report = validate_v0_export(v0, cfg)
    # The orphan warning should now be blocking
    orphans = [f for f in report.findings if f.section == "Navigation Integrity" and "orphan" in f.message.lower()]
    assert orphans and orphans[0].severity == "BLOCKING"


def test_report_markdown_sections(tmp_path: Path):
    from set_project_web.v0_validator import (
        Finding,
        ValidationReport,
    )

    r = ValidationReport()
    r.add("BLOCKING", "Navigation Integrity", "broken link: /x", file="app/page.tsx")
    r.add("WARNING", "shadcn Consistency", "mixed use")
    md = r.render_markdown()
    assert "## Navigation Integrity" in md
    assert "## shadcn Consistency" in md
    assert "[BLOCKING]" in md
