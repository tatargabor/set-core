"""Tests: worktree port allocation is deterministic and persists to change.extras.

See OpenSpec change: fix-e2e-infra-systematic (T1.5.3).

Port allocation must be:
  (1) deterministic per change name (same name → same port across runs)
  (2) collision-free across typical change-name sets (<20 names, common suite)
  (3) persisted in change.extras.assigned_e2e_port at dispatch so the gate
      runner reads a stable value without recomputing.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))
sys.path.insert(0, str(_ROOT / "modules" / "web"))


def test_same_name_same_port():
    from set_project_web.project_type import WebProjectType

    p = WebProjectType()
    first = p.worktree_port("add-checkout-flow")
    second = p.worktree_port("add-checkout-flow")
    third = p.worktree_port("add-checkout-flow")
    assert first == second == third
    # Port base is 3100
    assert 3100 <= first < 4100


def test_different_names_different_ports():
    from set_project_web.project_type import WebProjectType

    p = WebProjectType()
    assert p.worktree_port("foo") != p.worktree_port("bar")


def test_no_pairwise_collision_on_typical_suite():
    """20 realistic change names must not collide under the current hash % 1000 range."""
    from set_project_web.project_type import WebProjectType

    names = [
        "add-auth-nextauth",
        "add-catalog-browse",
        "add-checkout-flow",
        "add-customer-reviews",
        "add-product-search",
        "add-wishlist",
        "add-order-history",
        "add-shipping-addresses",
        "add-gift-cards",
        "add-discount-codes",
        "add-seo-sitemap",
        "add-robots-txt",
        "add-admin-dashboard",
        "add-admin-products",
        "add-i18n-hu-en",
        "add-cart-persistence",
        "add-stock-alerts",
        "add-email-receipts",
        "add-payment-stripe",
        "add-inventory-cron",
    ]
    p = WebProjectType()
    ports = [p.worktree_port(n) for n in names]
    assert len(set(ports)) == len(ports), (
        f"Port collision detected — not all unique: "
        f"{sorted((n, p.worktree_port(n)) for n in names)}"
    )


def test_gate_reads_assigned_port_from_extras_first(monkeypatch, tmp_path: Path):
    """The e2e gate must prefer change.extras.assigned_e2e_port over
    profile.worktree_port — this is the persistence contract that decouples
    dispatch-time port assignment from gate-time execution.
    """
    from unittest.mock import MagicMock

    from set_orch.state import Change
    from set_project_web.gates import execute_e2e_gate

    # Minimal worktree — no playwright.config.ts so gate short-circuits
    # after building env. We only care whether the env would have contained
    # our assigned port. We can't easily introspect env without executing,
    # so instead we inject a profile whose e2e_gate_env records the port.
    wt = tmp_path / "wt"
    wt.mkdir()
    # Playwright config + 1 fake spec, to let the gate proceed past early returns
    (wt / "playwright.config.ts").write_text(
        "export default { webServer: {}, testDir: './tests/e2e' }"
    )
    tests_e2e = wt / "tests" / "e2e"
    tests_e2e.mkdir(parents=True)
    (tests_e2e / "fake.spec.ts").write_text("// fake")

    captured = {}

    class _FakeProfile:
        def detect_e2e_command(self, _): return "true"
        def worktree_port(self, _name): return 9999  # would-be fallback
        def e2e_gate_env(self, port, **kwargs):
            captured["port"] = port
            return {"PW_PORT": str(port)}
        def e2e_pre_gate(self, _wt, _env): return False  # short-circuit after env built

    change = Change(name="add-catalog-browse", scope="", extras={"assigned_e2e_port": 3142})
    # e2e_command needed
    result = execute_e2e_gate(
        "add-catalog-browse", change, str(wt),
        e2e_command="echo ok", e2e_timeout=600, e2e_health_timeout=30,
        profile=_FakeProfile(),
    )
    assert captured.get("port") == 3142, (
        f"Gate must use assigned_e2e_port (3142) not fallback (9999) "
        f"— captured: {captured}"
    )
    # result.status is likely "skipped" because e2e_pre_gate returned False —
    # that's fine, we only care about env assembly.
    assert result.status in ("skipped", "pass", "fail")


def test_gate_falls_back_to_worktree_port_when_extras_empty(tmp_path: Path):
    """Legacy changes without assigned_e2e_port fall through to profile.worktree_port."""
    from set_orch.state import Change
    from set_project_web.gates import execute_e2e_gate

    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / "playwright.config.ts").write_text(
        "export default { webServer: {}, testDir: './tests/e2e' }"
    )
    tests_e2e = wt / "tests" / "e2e"
    tests_e2e.mkdir(parents=True)
    (tests_e2e / "fake.spec.ts").write_text("// fake")

    captured = {}

    class _FakeProfile:
        def detect_e2e_command(self, _): return "true"
        def worktree_port(self, _name): return 7777
        def e2e_gate_env(self, port, **kwargs):
            captured["port"] = port
            return {"PW_PORT": str(port)}
        def e2e_pre_gate(self, _wt, _env): return False

    change = Change(name="legacy-change", scope="", extras={})
    execute_e2e_gate(
        "legacy-change", change, str(wt),
        e2e_command="echo ok", e2e_timeout=600, e2e_health_timeout=30,
        profile=_FakeProfile(),
    )
    assert captured.get("port") == 7777, (
        "Fallback to profile.worktree_port must trigger when extras empty"
    )
