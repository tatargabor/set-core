"""Unit tests for the decomposer's skip_test guard + LOC formula
(section 9 of fix-replan-stuck-gate-and-decomposer).
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.planner import (  # noqa: E402
    _extract_scope_paths,
    _resolve_loc_weight,
    _skip_test_violation,
    estimate_change_loc,
    populate_touched_file_globs,
    validate_plan,
)


def test_skip_test_violation_catches_server():
    assert _skip_test_violation("edit src/server/actions/orders.ts") == "server"
    assert _skip_test_violation("Fix validators/cart.ts logic") == "validators"
    assert _skip_test_violation("Update /api/checkout handler") == "/api"
    assert _skip_test_violation("") == ""
    assert _skip_test_violation("Add scaffolding placeholder") == ""


def test_extract_scope_paths():
    text = "Touches src/app/cart/page.tsx and prisma/schema.prisma"
    paths = _extract_scope_paths(text)
    assert "src/app/cart/page.tsx" in paths
    assert "prisma/schema.prisma" in paths


def test_resolve_loc_weight_longest_glob_wins():
    weights = {
        "src/**": 150,
        "src/app/**/*.tsx": 200,
        "src/app/admin/**/page.tsx": 350,
    }
    # Most specific glob wins
    assert _resolve_loc_weight("src/app/admin/orders/page.tsx", weights) == 350
    # Fallback to next-most-specific
    assert _resolve_loc_weight("src/app/cart/page.tsx", weights) == 200
    # Fallback to broadest
    assert _resolve_loc_weight("src/lib/foo.ts", weights) == 150
    # No match → default 150
    assert _resolve_loc_weight("README.md", weights) == 150


def test_estimate_loc_uses_weights():
    change = {
        "scope": "Create src/app/admin/orders/page.tsx and src/server/orders.ts",
    }
    weights = {
        "src/app/admin/**/page.tsx": 350,
        "src/server/**/*.ts": 200,
    }
    est = estimate_change_loc(change, loc_weights=weights)
    # 350 + 200 + any ambiguity/schema bonuses (none here)
    assert est >= 550


def test_populate_touched_file_globs():
    change = {"scope": "Build src/app/cart/page.tsx"}
    globs = populate_touched_file_globs(change)
    assert "src/app/cart/page.tsx" in globs
    assert "src/app/cart/**" in globs  # wildcard parent added


def test_validate_plan_rejects_skip_test_on_server(tmp_path):
    plan = {
        "plan_version": 1, "brief_hash": "a",
        "changes": [{
            "name": "bad-skip-test",
            "scope": "Add validators/cart.ts with server-side validation",
            "complexity": "S", "depends_on": [],
            "skip_test": True,
        }],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    result = validate_plan(str(plan_path))
    assert any(
        "skip_test=true" in e and "validators" in e for e in result.errors
    ), f"expected skip_test violation, got errors: {result.errors}"


def test_validate_plan_accepts_skip_test_on_scaffolding(tmp_path):
    plan = {
        "plan_version": 1, "brief_hash": "a",
        "changes": [{
            "name": "docs-and-scaffolding",
            "scope": "Update docs/guide.md and public/favicon.ico",
            "complexity": "S", "depends_on": [],
            "skip_test": True,
        }],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    result = validate_plan(str(plan_path))
    skip_test_errors = [e for e in result.errors if "skip_test" in e]
    assert skip_test_errors == []


def test_validate_plan_accepts_skip_test_without_server_paths(tmp_path):
    """Pure UI components without server paths should be OK for skip_test."""
    plan = {
        "plan_version": 1, "brief_hash": "a",
        "changes": [{
            "name": "ui-polish",
            "scope": "Refactor src/components/Button.tsx styling",
            "complexity": "S", "depends_on": [],
            "skip_test": True,
        }],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    result = validate_plan(str(plan_path))
    skip_test_errors = [e for e in result.errors if "skip_test" in e]
    assert skip_test_errors == []


# ─── auto_split_change (section 9.4 / 9.5) ─────────────────────────

from set_orch.planner import auto_split_change, _infer_group_label  # noqa: E402


def test_small_change_passes_through_unchanged():
    change = {
        "name": "stories-and-content",
        "scope": "src/app/stories/page.tsx plus src/components/story-card.tsx",
        "phase": 1,
    }
    out = auto_split_change(change, threshold=1500,
                             loc_weights={"src/**": 150})
    assert out == [change]


def test_admin_operations_splits_into_linked_siblings():
    """E (3760 LOC) splits by admin-page directory prefix into siblings."""
    change = {
        "name": "admin-operations",
        "scope": (
            "Build out admin pages: src/app/admin/orders/page.tsx, "
            "src/app/admin/dashboard/page.tsx, src/app/admin/returns/page.tsx. "
            "Each page has DataTable + filter + CRUD forms."
        ),
        "phase": 2,
        "requirements": ["R1", "R2", "R3"],
    }
    weights = {"src/app/admin/**/page.tsx": 1500}  # force over-threshold

    out = auto_split_change(change, threshold=1500, loc_weights=weights)
    names = [s["name"] for s in out]
    assert len(out) >= 3
    # Phase preserved
    assert all(s["phase"] == 2 for s in out)
    # Sequential depends_on chain
    assert names[0].startswith("admin-operations-")
    for prev, cur in zip(out, out[1:]):
        assert prev["name"] in cur.get("depends_on", [])
    # Pre-split name never appears as a sibling name
    assert "admin-operations" not in names
    # Group labels are inferred (orders, dashboard, returns)
    labels = [n.rsplit("-", 1)[0].replace("admin-operations-", "") for n in names]
    assert "orders" in labels and "dashboard" in labels and "returns" in labels


def test_promotions_engine_splits_server_vs_admin():
    change = {
        "name": "promotions-engine",
        "scope": (
            "Server: src/server/promotions.ts validates codes. "
            "Admin: src/app/admin/promotions/page.tsx lists codes."
        ),
        "phase": 1,
    }
    # Force total > 1500 LOC with heavy weights
    weights = {
        "src/server/**/*.ts": 1200,
        "src/app/admin/**/page.tsx": 1200,
    }
    out = auto_split_change(change, threshold=1500, loc_weights=weights)
    assert len(out) >= 2
    names = [s["name"] for s in out]
    labels = {n.rsplit("-", 1)[0].replace("promotions-engine-", "") for n in names}
    # Server sibling carries "-server" suffix; admin sibling has no suffix
    assert any(lbl.endswith("-server") for lbl in labels)
    # Chain preserved
    assert out[0]["name"] in out[1].get("depends_on", [])


def test_auto_split_on_15_requirement_change():
    """9.9: 15-requirement change produces ≥3 splits with correct depends_on."""
    change = {
        "name": "mega-feature",
        "scope": (
            "Implement src/app/admin/a/page.tsx, src/app/admin/b/page.tsx, "
            "src/app/admin/c/page.tsx with server pieces "
            "src/server/a.ts, src/server/b.ts, src/server/c.ts "
            "and tests tests/e2e/a.spec.ts."
        ),
        "phase": 1,
        "requirements": [f"R{i}" for i in range(15)],
    }
    # Force over-threshold with aggressive weights
    weights = {
        "src/app/admin/**/page.tsx": 600,
        "src/server/**/*.ts": 500,
        "tests/e2e/**/*.spec.ts": 300,
    }
    out = auto_split_change(change, threshold=1500, loc_weights=weights)
    assert len(out) >= 3
    # Chain of depends_on preserved across all siblings
    for prev, cur in zip(out, out[1:]):
        assert prev["name"] in cur.get("depends_on", [])
    # Total requirements preserved across siblings (round-robin)
    total_reqs = sum(len(s.get("requirements") or []) for s in out)
    assert total_reqs == 15


def test_pre_split_name_never_appears_in_output():
    change = {
        "name": "concern-a-and-b",
        "scope": "src/server/foo.ts plus src/app/admin/bar/page.tsx",
        "phase": 1,
    }
    weights = {"src/**": 1500}
    out = auto_split_change(change, threshold=1500, loc_weights=weights)
    names = [s["name"] for s in out]
    if len(out) > 1:
        assert "concern-a-and-b" not in names


def test_infer_group_label_admin():
    assert _infer_group_label([
        "src/app/admin/orders/page.tsx",
        "src/app/admin/orders/new/page.tsx",
    ]) == "orders"


def test_infer_group_label_server_suffix():
    assert _infer_group_label([
        "src/server/promotions/engine.ts",
        "src/server/promotions/validator.ts",
    ]) == "promotions-server"


def test_infer_group_label_tests():
    assert _infer_group_label([
        "tests/e2e/cart.spec.ts",
        "tests/e2e/checkout.spec.ts",
    ]) == "tests"
