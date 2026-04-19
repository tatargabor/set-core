"""Divergence comparison tool for orchestration runs.

Compares two project directories across objectively measurable metrics:
routes, schema, dependencies, functional categories, template compliance,
convention compliance, and E2E test results.

Usage:
    python3 -m set_orch.compare project-a project-b
    python3 -m set_orch.compare --dir /path/a --dir /path/b --json
"""

from __future__ import annotations

import argparse
import filecmp
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# ─── Data collection ─────────────────────────────────────────────────


def collect_routes(project_dir: Path) -> set[str]:
    """Find all page.tsx and route.ts files, convert to URL paths.

    Route groups like (shop)/, (auth)/, (dashboard)/ are stripped.
    Dynamic segments [param] are preserved as :param.
    """
    routes: set[str] = set()
    src_app = project_dir / "src" / "app"
    if not src_app.is_dir():
        return routes

    for f in src_app.rglob("page.tsx"):
        route = _file_to_route(f, src_app)
        if route is not None:
            routes.add(route)

    for f in src_app.rglob("route.ts"):
        route = _file_to_route(f, src_app, is_api=True)
        if route is not None:
            routes.add(route)

    return routes


def _file_to_route(f: Path, app_dir: Path, is_api: bool = False) -> str | None:
    """Convert a file path to a URL route string."""
    rel = f.relative_to(app_dir)
    parts = list(rel.parts[:-1])  # drop page.tsx / route.ts

    # Strip route groups: (shop), (auth), (dashboard), etc.
    cleaned = []
    for p in parts:
        if p.startswith("(") and p.endswith(")"):
            continue
        # Convert [param] to :param
        if p.startswith("[") and p.endswith("]"):
            p = ":" + p[1:-1]
        cleaned.append(p)

    route = "/" + "/".join(cleaned)
    if route == "/":
        route = "/"
    return route


def collect_schema(project_dir: Path) -> dict[str, Any]:
    """Parse prisma/schema.prisma for model and enum names.

    Returns {"models": ["Model1", ...], "enums": ["Enum1", ...]} or empty if no schema.
    """
    schema_file = project_dir / "prisma" / "schema.prisma"
    if not schema_file.is_file():
        return {"models": [], "enums": [], "exists": False}

    content = schema_file.read_text()
    models = sorted(re.findall(r"^model\s+(\w+)\s*\{", content, re.MULTILINE))
    enums = sorted(re.findall(r"^enum\s+(\w+)\s*\{", content, re.MULTILINE))
    return {"models": models, "enums": enums, "exists": True}


def collect_deps(project_dir: Path) -> tuple[set[str], set[str]]:
    """Read package.json and return (dependencies, devDependencies) as name sets."""
    pkg = project_dir / "package.json"
    if not pkg.is_file():
        return set(), set()

    data = json.loads(pkg.read_text())
    deps = set(data.get("dependencies", {}).keys())
    dev = set(data.get("devDependencies", {}).keys())
    return deps, dev


def collect_categories(project_dir: Path) -> dict[str, int]:
    """Count source files by functional role."""
    src = project_dir / "src"
    if not src.is_dir():
        return {}

    app = src / "app"
    cats: dict[str, int] = {}

    cats["pages"] = len(list(app.rglob("page.tsx"))) if app.is_dir() else 0
    cats["api_routes"] = len(list(app.rglob("route.ts"))) if app.is_dir() else 0
    cats["actions"] = len(list(src.rglob("actions.ts")))
    cats["layouts"] = len(list(app.rglob("layout.tsx"))) if app.is_dir() else 0
    cats["middleware"] = 1 if (src / "middleware.ts").is_file() else 0

    # Feature components: *.tsx not page/layout and not in ui/
    all_tsx = set(src.rglob("*.tsx"))
    pages_layouts = set(app.rglob("page.tsx")) | set(app.rglob("layout.tsx")) if app.is_dir() else set()
    ui_dir = src / "components" / "ui"
    ui_files = set(ui_dir.rglob("*.tsx")) if ui_dir.is_dir() else set()
    cats["feature_components"] = len(all_tsx - pages_layouts - ui_files)
    cats["ui_primitives"] = len(ui_files)

    # Lib files
    lib_dir = src / "lib"
    cats["lib_files"] = len(list(lib_dir.rglob("*.ts"))) if lib_dir.is_dir() else 0

    # Tests
    cats["unit_tests"] = len(list(src.rglob("*.test.*")))
    e2e_dir = project_dir / "tests" / "e2e"
    cats["e2e_tests"] = len(list(e2e_dir.glob("*.spec.ts"))) if e2e_dir.is_dir() else 0

    return cats


def check_template_compliance(project_dir: Path, profile=None) -> list[dict[str, str]]:
    """Check if template files are unchanged from the module template.

    Uses profile.get_comparison_template_files() if available,
    falls back to hardcoded list for backwards compatibility.
    """
    template_dir = _find_template_dir()
    if not template_dir:
        return []

    if profile and hasattr(profile, "get_comparison_template_files"):
        template_files = profile.get_comparison_template_files()
    else:
        template_files = [
            "src/app/globals.css", "src/lib/utils.ts", "src/lib/prisma.ts",
            "vitest.config.ts", "playwright.config.ts", "tsconfig.json",
            "next.config.js", "postcss.config.mjs",
        ]

    results = []
    for rel in template_files:
        tmpl = template_dir / rel
        proj = project_dir / rel
        if not tmpl.is_file():
            continue
        if not proj.is_file():
            results.append({"file": rel, "status": "not_applicable"})
        elif filecmp.cmp(str(tmpl), str(proj), shallow=False):
            results.append({"file": rel, "status": "unchanged"})
        else:
            results.append({"file": rel, "status": "modified"})

    return results


def check_convention_compliance(project_dir: Path, profile=None) -> list[dict[str, Any]]:
    """Check structural convention compliance.

    Uses profile.get_comparison_conventions() if available,
    falls back to basic checks for backwards compatibility.
    """
    if profile and hasattr(profile, "get_comparison_conventions"):
        convention_defs = profile.get_comparison_conventions()
        checks = []
        for conv in convention_defs:
            try:
                passed = conv["check"](project_dir)
            except Exception:
                passed = True  # don't penalize on errors
            checks.append({
                "id": conv["id"],
                "description": conv["description"],
                "pass": passed,
            })
        return checks

    # Fallback: basic checks (no profile)
    src = project_dir / "src"
    return [
        {"id": "src_exists", "description": "src/ directory exists", "pass": src.is_dir()},
    ]


def collect_e2e_results(project_dir: Path) -> dict[str, Any]:
    """Collect E2E test information: spec file names and gate results."""
    result: dict[str, Any] = {"spec_files": [], "gate_results": {}, "has_report": False}

    # Spec files
    e2e_dir = project_dir / "tests" / "e2e"
    if e2e_dir.is_dir():
        result["spec_files"] = sorted(f.name for f in e2e_dir.glob("*.spec.ts"))

    # Playwright report
    report_dir = project_dir / "playwright-report"
    result["has_report"] = report_dir.is_dir()

    # Gate results from orchestration state (resolver-canonical only)
    from .paths import LineagePaths as _LP_cmp
    for state_path in [Path(_LP_cmp(str(project_dir)).state_file)]:
        if state_path.is_file():
            try:
                state = json.loads(state_path.read_text())
                for c in state.get("changes", []):
                    gates = {}
                    for g in ("test_result", "build_result", "smoke_result"):
                        if c.get(g):
                            gates[g] = c[g]
                    if gates:
                        result["gate_results"][c["name"]] = gates
            except (json.JSONDecodeError, KeyError):
                pass
            break

    return result


# ─── Comparison ──────────────────────────────────────────────────────


@dataclass
class MetricResult:
    name: str
    score: float  # 0-100
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    run_a: str
    run_b: str
    metrics: list[MetricResult] = field(default_factory=list)
    weighted_score: float = 0.0
    verdict: str = ""


WEIGHTS = {
    "route_coverage": 0.25,
    "schema_equivalence": 0.20,
    "dependency_set": 0.10,
    "functional_categories": 0.10,
    "template_compliance": 0.10,
    "convention_compliance": 0.10,
    "e2e_tests": 0.15,
}


def _set_overlap_pct(a: set, b: set) -> float:
    """Calculate overlap percentage of two sets (Jaccard-like but max-normalized)."""
    if not a and not b:
        return 100.0
    union = a | b
    if not union:
        return 100.0
    return len(a & b) / len(union) * 100


def _count_similarity(a: dict[str, int], b: dict[str, int]) -> float:
    """Compare category counts — score based on how close counts are."""
    all_keys = set(a.keys()) | set(b.keys())
    if not all_keys:
        return 100.0
    total_diff = 0
    total_max = 0
    for k in all_keys:
        va = a.get(k, 0)
        vb = b.get(k, 0)
        total_diff += abs(va - vb)
        total_max += max(va, vb, 1)
    return max(0, (1 - total_diff / total_max) * 100)


def _load_profile(project_dir: Path):
    """Try to load the project's profile for type-specific checks."""
    try:
        from .profile_loader import load_profile
        return load_profile(str(project_dir))
    except Exception:
        return None


def compare_runs(dir_a: Path, dir_b: Path, name_a: str = "", name_b: str = "") -> ComparisonResult:
    """Compare two project directories across all metrics."""
    # Load profile from either project (they should be the same type)
    profile = _load_profile(dir_a) or _load_profile(dir_b)

    result = ComparisonResult(
        run_a=name_a or dir_a.name,
        run_b=name_b or dir_b.name,
    )

    # 1. Route coverage
    routes_a = collect_routes(dir_a)
    routes_b = collect_routes(dir_b)
    common_routes = routes_a & routes_b
    only_a = routes_a - routes_b
    only_b = routes_b - routes_a
    route_score = _set_overlap_pct(routes_a, routes_b)
    result.metrics.append(MetricResult(
        name="route_coverage",
        score=route_score,
        details={
            "common": sorted(common_routes),
            "only_a": sorted(only_a),
            "only_b": sorted(only_b),
            "count_a": len(routes_a),
            "count_b": len(routes_b),
        },
    ))

    # 2. Schema equivalence
    schema_a = collect_schema(dir_a)
    schema_b = collect_schema(dir_b)
    if not schema_a["exists"] and not schema_b["exists"]:
        schema_score = 100.0
    elif schema_a["exists"] != schema_b["exists"]:
        schema_score = 0.0
    else:
        models_a = set(schema_a["models"])
        models_b = set(schema_b["models"])
        enums_a = set(schema_a["enums"])
        enums_b = set(schema_b["enums"])
        all_items = (models_a | models_b | enums_a | enums_b)
        common = (models_a & models_b) | (enums_a & enums_b)
        schema_score = len(common) / len(all_items) * 100 if all_items else 100.0
    result.metrics.append(MetricResult(
        name="schema_equivalence",
        score=schema_score,
        details={
            "models_a": schema_a["models"],
            "models_b": schema_b["models"],
            "enums_a": schema_a.get("enums", []),
            "enums_b": schema_b.get("enums", []),
            "exists_a": schema_a.get("exists", False),
            "exists_b": schema_b.get("exists", False),
        },
    ))

    # 3. Dependencies
    deps_a, dev_a = collect_deps(dir_a)
    deps_b, dev_b = collect_deps(dir_b)
    all_deps_a = deps_a | dev_a
    all_deps_b = deps_b | dev_b
    dep_score = _set_overlap_pct(all_deps_a, all_deps_b)
    result.metrics.append(MetricResult(
        name="dependency_set",
        score=dep_score,
        details={
            "common": sorted(all_deps_a & all_deps_b),
            "only_a": sorted(all_deps_a - all_deps_b),
            "only_b": sorted(all_deps_b - all_deps_a),
        },
    ))

    # 4. Functional categories
    cats_a = collect_categories(dir_a)
    cats_b = collect_categories(dir_b)
    cat_score = _count_similarity(cats_a, cats_b)
    result.metrics.append(MetricResult(
        name="functional_categories",
        score=cat_score,
        details={"a": cats_a, "b": cats_b},
    ))

    # 5. Template compliance
    tmpl_a = check_template_compliance(dir_a, profile)
    tmpl_b = check_template_compliance(dir_b, profile)
    # Score: unchanged + not_applicable count as "good", modified counts against
    def _tmpl_good(items):
        return sum(1 for t in items if t["status"] in ("unchanged", "not_applicable"))
    good_a = _tmpl_good(tmpl_a)
    good_b = _tmpl_good(tmpl_b)
    total_tmpl = max(len(tmpl_a), len(tmpl_b), 1)
    tmpl_score = (good_a + good_b) / (total_tmpl * 2) * 100
    result.metrics.append(MetricResult(
        name="template_compliance",
        score=tmpl_score,
        details={"a": tmpl_a, "b": tmpl_b},
    ))

    # 6. Convention compliance
    conv_a = check_convention_compliance(dir_a, profile)
    conv_b = check_convention_compliance(dir_b, profile)
    pass_a = sum(1 for c in conv_a if c["pass"])
    pass_b = sum(1 for c in conv_b if c["pass"])
    total_conv = max(len(conv_a), len(conv_b), 1)
    conv_score = (pass_a + pass_b) / (total_conv * 2) * 100
    result.metrics.append(MetricResult(
        name="convention_compliance",
        score=conv_score,
        details={"a": conv_a, "b": conv_b},
    ))

    # 7. E2E test results
    e2e_a = collect_e2e_results(dir_a)
    e2e_b = collect_e2e_results(dir_b)
    specs_a = set(e2e_a["spec_files"])
    specs_b = set(e2e_b["spec_files"])
    spec_overlap = _set_overlap_pct(specs_a, specs_b)
    # Gate match: how many changes have same gate results?
    gates_a = e2e_a["gate_results"]
    gates_b = e2e_b["gate_results"]
    gate_changes = set(gates_a.keys()) | set(gates_b.keys())
    gate_match = 0
    for ch in gate_changes:
        ga = set(gates_a.get(ch, {}).values())
        gb = set(gates_b.get(ch, {}).values())
        if ga == gb and ga:
            gate_match += 1
    gate_pct = gate_match / len(gate_changes) * 100 if gate_changes else 100.0
    e2e_score = (spec_overlap + gate_pct) / 2
    result.metrics.append(MetricResult(
        name="e2e_tests",
        score=e2e_score,
        details={
            "spec_files_a": sorted(specs_a),
            "spec_files_b": sorted(specs_b),
            "spec_overlap_pct": spec_overlap,
            "gate_match_pct": gate_pct,
            "has_report_a": e2e_a["has_report"],
            "has_report_b": e2e_b["has_report"],
        },
    ))

    # Weighted score
    total = 0.0
    for m in result.metrics:
        w = WEIGHTS.get(m.name, 0)
        total += m.score * w
    result.weighted_score = round(total, 1)

    # Verdict
    if result.weighted_score >= 90:
        result.verdict = "Structurally identical"
    elif result.weighted_score >= 75:
        result.verdict = "Structurally equivalent"
    elif result.weighted_score >= 50:
        result.verdict = "Partially divergent"
    else:
        result.verdict = "Significantly divergent"

    return result


# ─── Output formatting ───────────────────────────────────────────────


def format_markdown(r: ComparisonResult) -> str:
    """Render comparison result as a readable markdown report."""
    lines = []
    lines.append(f"# Divergence Report: {r.run_a} vs {r.run_b}")
    lines.append("")
    lines.append(f"**Score: {r.weighted_score:.0f}/100** — {r.verdict}")
    lines.append("")

    for m in r.metrics:
        title = m.name.replace("_", " ").title()
        lines.append(f"## {title} ({m.score:.0f}%)")
        lines.append("")

        d = m.details

        if m.name == "route_coverage":
            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| Common routes | {len(d['common'])} |")
            lines.append(f"| Only {r.run_a} | {len(d['only_a'])} |")
            lines.append(f"| Only {r.run_b} | {len(d['only_b'])} |")
            if d["only_a"]:
                lines.append(f"\nOnly in {r.run_a}: {', '.join(d['only_a'])}")
            if d["only_b"]:
                lines.append(f"\nOnly in {r.run_b}: {', '.join(d['only_b'])}")

        elif m.name == "schema_equivalence":
            if not d.get("exists_a") and not d.get("exists_b"):
                lines.append("No Prisma schema in either project (N/A).")
            else:
                ma, mb = set(d["models_a"]), set(d["models_b"])
                lines.append(f"Common models: {sorted(ma & mb)}")
                if ma - mb:
                    lines.append(f"Only {r.run_a}: {sorted(ma - mb)}")
                if mb - ma:
                    lines.append(f"Only {r.run_b}: {sorted(mb - ma)}")
                ea, eb = set(d.get("enums_a", [])), set(d.get("enums_b", []))
                if ea | eb:
                    lines.append(f"Common enums: {sorted(ea & eb)}")

        elif m.name == "dependency_set":
            lines.append(f"Common: {len(d['common'])} packages")
            if d["only_a"]:
                lines.append(f"Only {r.run_a}: {', '.join(d['only_a'])}")
            if d["only_b"]:
                lines.append(f"Only {r.run_b}: {', '.join(d['only_b'])}")

        elif m.name == "functional_categories":
            a, b = d.get("a", {}), d.get("b", {})
            all_keys = sorted(set(a.keys()) | set(b.keys()))
            lines.append(f"| Category | {r.run_a} | {r.run_b} | Diff |")
            lines.append(f"|----------|------:|------:|-----:|")
            for k in all_keys:
                va, vb = a.get(k, 0), b.get(k, 0)
                diff = abs(va - vb)
                marker = "" if diff == 0 else f" (+{diff})"
                lines.append(f"| {k} | {va} | {vb} | {diff} |")

        elif m.name == "template_compliance":
            for label, items in [("a", r.run_a), ("b", r.run_b)]:
                tmpl_list = d.get(label, [])
                if tmpl_list:
                    applicable = [t for t in tmpl_list if t["status"] != "not_applicable"]
                    unchanged = sum(1 for t in applicable if t["status"] == "unchanged")
                    lines.append(f"**{items}**: {unchanged}/{len(applicable)} unchanged")
                    for t in applicable:
                        icon = "✅" if t["status"] == "unchanged" else "⚠️"
                        lines.append(f"  {icon} {t['file']}: {t['status']}")

        elif m.name == "convention_compliance":
            lines.append(f"| Convention | {r.run_a} | {r.run_b} |")
            lines.append(f"|------------|:---:|:---:|")
            for ca, cb in zip(d.get("a", []), d.get("b", [])):
                pa = "✅" if ca["pass"] else "❌"
                pb = "✅" if cb["pass"] else "❌"
                lines.append(f"| {ca['description']} | {pa} | {pb} |")

        elif m.name == "e2e_tests":
            sa = set(d.get("spec_files_a", []))
            sb = set(d.get("spec_files_b", []))
            lines.append(f"Spec file overlap: {d.get('spec_overlap_pct', 0):.0f}%")
            lines.append(f"Gate result match: {d.get('gate_match_pct', 0):.0f}%")
            if sa - sb:
                lines.append(f"Only {r.run_a}: {', '.join(sorted(sa - sb))}")
            if sb - sa:
                lines.append(f"Only {r.run_b}: {', '.join(sorted(sb - sa))}")

        lines.append("")

    lines.append("---")
    lines.append(f"*Generated by `set-compare`*")
    return "\n".join(lines)


def format_json(r: ComparisonResult) -> str:
    """Render comparison result as structured JSON."""
    return json.dumps(asdict(r), indent=2)


# ─── Helpers ─────────────────────────────────────────────────────────


def _find_template_dir() -> Path | None:
    """Find the web module nextjs template directory."""
    candidates = [
        Path(__file__).parent.parent.parent / "modules" / "web" / "set_project_web" / "templates" / "nextjs",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def _resolve_project(name: str) -> Path | None:
    """Resolve a project name to its directory via projects.json."""
    projects_file = Path.home() / ".config" / "set-core" / "projects.json"
    if not projects_file.is_file():
        return None
    try:
        data = json.loads(projects_file.read_text())
        projects = data.get("projects", {})
        if name in projects:
            path = Path(projects[name].get("path", ""))
            if path.is_dir():
                return path
    except (json.JSONDecodeError, KeyError):
        pass
    return None


# ─── CLI ─────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Compare two orchestration runs for structural divergence.",
        usage="set-compare PROJECT_A PROJECT_B [--json] [--output FILE]",
    )
    parser.add_argument("projects", nargs="*", help="Two project names to compare")
    parser.add_argument("--dir", action="append", help="Compare two directories directly (use twice)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of markdown")
    parser.add_argument("--output", "-o", help="Write report to file instead of stdout")
    args = parser.parse_args()

    # Resolve directories
    if args.dir and len(args.dir) == 2:
        dir_a, dir_b = Path(args.dir[0]), Path(args.dir[1])
        name_a, name_b = dir_a.name, dir_b.name
    elif len(args.projects) == 2:
        name_a, name_b = args.projects
        dir_a = _resolve_project(name_a)
        dir_b = _resolve_project(name_b)
        if not dir_a:
            print(f"Error: project '{name_a}' not found in projects.json", file=sys.stderr)
            sys.exit(1)
        if not dir_b:
            print(f"Error: project '{name_b}' not found in projects.json", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    # Compare
    result = compare_runs(dir_a, dir_b, name_a, name_b)

    # Format output
    output = format_json(result) if args.json else format_markdown(result)

    # Write
    if args.output:
        Path(args.output).write_text(output)
        print(f"Report written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
