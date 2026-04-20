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
