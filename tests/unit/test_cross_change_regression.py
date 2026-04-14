"""Tests: cross-change regression detection at the integration gate.

See OpenSpec change: fix-e2e-infra-systematic (T2.2.7, T2.2.8).

When integration-gate e2e failures include tests owned by an already-merged
change, the orchestrator should:
  1. Classify tests into (own, merged-others, unknown)
  2. Emit a CROSS_CHANGE_REGRESSION event
  3. Prepend a prescriptive framing block to the agent's retry_context

When only own-change tests fail, NO cross-change event should fire.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))


def _make_state(changes: list) -> SimpleNamespace:
    """Build a minimal state-like object with a `.changes` list."""
    return SimpleNamespace(changes=changes)


def _ch(name: str, status: str = "merged", requirements=None, merged_scope_files=None):
    return SimpleNamespace(
        name=name,
        status=status,
        requirements=requirements or [],
        extras={"merged_scope_files": merged_scope_files or []},
    )


def test_resolve_owning_change_by_filename():
    from set_orch.cross_change import resolve_owning_change
    state = _make_state([_ch("add-cart"), _ch("add-checkout")])
    owner = resolve_owning_change("tests/e2e/add-cart.spec.ts", "", state)
    assert owner == "add-cart"


def test_resolve_owning_change_by_req_tag():
    from set_orch.cross_change import resolve_owning_change
    state = _make_state([
        _ch("add-cart", requirements=[{"id": "REQ-CART-001"}, {"id": "REQ-CART-002"}]),
        _ch("add-checkout", requirements=[{"id": "REQ-CHECKOUT-001"}]),
    ])
    owner = resolve_owning_change(
        "tests/e2e/unrelated-file.spec.ts",
        "REQ-CART-002 adds item to cart",
        state,
    )
    assert owner == "add-cart"


def test_resolve_owning_change_by_scope_files():
    from set_orch.cross_change import resolve_owning_change
    state = _make_state([
        _ch("add-cart", merged_scope_files=[
            "tests/e2e/scope-based.spec.ts", "src/app/cart/page.tsx",
        ]),
    ])
    owner = resolve_owning_change(
        "tests/e2e/scope-based.spec.ts", "title", state,
    )
    assert owner == "add-cart"


def test_resolve_returns_none_when_no_merged_changes():
    from set_orch.cross_change import resolve_owning_change
    state = _make_state([_ch("add-cart", status="pending")])  # not merged
    owner = resolve_owning_change("tests/e2e/add-cart.spec.ts", "", state)
    assert owner is None


def test_detect_flags_cross_change_regression():
    from set_orch.cross_change import detect_cross_change_regressions
    state = _make_state([
        _ch("add-cart", requirements=[{"id": "REQ-CART-001"}],
            merged_scope_files=["src/app/cart/page.tsx"]),
        _ch("add-checkout", merged_scope_files=["src/app/checkout/page.tsx"]),
    ])

    failing = [
        ("tests/e2e/add-cart.spec.ts", "REQ-CART-001 cart persists"),
        ("tests/e2e/add-checkout.spec.ts", "basic checkout"),
        ("tests/e2e/current-feature.spec.ts", "my own test"),
    ]
    report = detect_cross_change_regressions(
        "current-feature",
        failing, state,
        current_touched_files=["src/app/cart/page.tsx", "src/app/current/page.tsx"],
    )
    assert report.has_cross_change_regression
    assert "add-cart" in report.by_owning_change
    assert "add-checkout" in report.by_owning_change
    # Current-feature test is unresolved (not in merged state) — bucketed as unknown.
    assert any("current-feature" in t for t in report.unknown_tests)
    # Overlap: touched cart page → add-cart overlap
    assert "add-cart" in report.overlapping_files
    assert "src/app/cart/page.tsx" in report.overlapping_files["add-cart"]


def test_detect_no_regression_when_only_own_fails():
    from set_orch.cross_change import detect_cross_change_regressions
    state = _make_state([
        _ch("add-cart", merged_scope_files=["src/app/cart/page.tsx"]),
    ])
    failing = [
        ("tests/e2e/current-feature.spec.ts", "my only failing test"),
    ]
    report = detect_cross_change_regressions(
        "current-feature", failing, state,
        current_touched_files=["src/app/current/page.tsx"],
    )
    assert not report.has_cross_change_regression
    assert report.regressed_tests == {}
    assert report.by_owning_change == {}


def test_build_retry_context_includes_prescriptive_framing():
    from set_orch.cross_change import (
        build_regression_retry_context,
        detect_cross_change_regressions,
    )
    state = _make_state([
        _ch("add-cart", merged_scope_files=["src/app/cart/page.tsx"]),
    ])
    failing = [("tests/e2e/add-cart.spec.ts", "cart persists")]
    report = detect_cross_change_regressions(
        "current-feature", failing, state,
        current_touched_files=["src/app/cart/page.tsx"],
    )
    ctx = build_regression_retry_context("current-feature", report)

    # Required signals the agent MUST see
    assert "Cross-change regression" in ctx
    assert "`add-cart`" in ctx
    assert "Do NOT modify" in ctx
    assert "cart persists" in ctx or "cart.spec.ts" in ctx
    # Overlap list is rendered
    assert "src/app/cart/page.tsx" in ctx
    # Directive block present
    assert "Directive" in ctx


def test_build_retry_context_empty_when_no_regression():
    from set_orch.cross_change import build_regression_retry_context, RegressionReport
    report = RegressionReport(
        regressed_tests={}, by_owning_change={}, own_failing_tests=[],
        unknown_tests=[], overlapping_files={},
    )
    assert build_regression_retry_context("x", report) == ""


def test_scope_file_overlap_forward_compat_when_legacy_missing():
    """Merged changes without merged_scope_files fall through path (c) — must
    still let paths (a) and (b) work without crashing."""
    from set_orch.cross_change import resolve_owning_change
    state = _make_state([
        _ch("add-cart", merged_scope_files=None),  # legacy — no scope
    ])
    # Filename convention still works
    owner = resolve_owning_change("tests/e2e/add-cart.spec.ts", "", state)
    assert owner == "add-cart"
