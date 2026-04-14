"""Tests: findings extractors produce structured Findings from gate output.

See OpenSpec change: fix-e2e-infra-systematic (T2.1.5, T2.1.6).

Each extractor:
  * returns ≥1 structured finding on representative gate output
  * returns [] (NOT an exception) on unparseable / empty output
  * fingerprints findings stably across retries
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))


def test_fingerprint_stability():
    from set_orch.findings import fingerprint

    a = fingerprint("src/app.ts", 42, "Missing null check on session")
    b = fingerprint("src/app.ts", 42, "Missing null check on session")
    c = fingerprint("src/app.ts", 43, "Missing null check on session")
    d = fingerprint("src/app.ts", 42, "Different title")
    assert a == b, "Identical inputs must yield identical fingerprints"
    assert a != c and a != d
    assert len(a) == 8 and all(ch in "0123456789abcdef" for ch in a)


def test_review_extractor_happy_path():
    from set_orch.findings import extract_review_findings

    output = """
## Review

[CRITICAL] SQL injection in getProduct
File: src/app/api/products/[id]/route.ts:42
Fix: Replace `prisma.$queryRaw` with `prisma.product.findUnique({ where: { id } })`
to parameterize the id instead of interpolating it into the SQL string.

[CRITICAL] Hardcoded admin password in middleware
File: src/middleware.ts:18
Fix: Read from `process.env.ADMIN_PASSWORD` and throw at boot if missing.

---
"""
    findings = extract_review_findings(output)
    assert len(findings) == 2
    a, b = findings
    assert a.severity == "critical"
    assert a.title.startswith("SQL injection")
    assert a.file == "src/app/api/products/[id]/route.ts"
    assert a.line_start == 42
    assert "prisma.product.findUnique" in a.fix_block
    assert a.fingerprint and len(a.fingerprint) == 8
    assert b.file == "src/middleware.ts"
    assert b.line_start == 18


def test_review_extractor_without_file_still_produces_finding():
    from set_orch.findings import extract_review_findings

    output = """
[CRITICAL] Design token drift between spec and implementation
Fix: Align `--color-primary` in globals.css with the value from design-system.md (#78350F).
"""
    findings = extract_review_findings(output)
    assert len(findings) == 1
    f = findings[0]
    assert f.file == ""
    assert f.line_start == 0
    assert f.confidence == "medium"
    assert "78350F" in f.fix_block


def test_review_extractor_empty_returns_empty_list():
    from set_orch.findings import extract_review_findings
    assert extract_review_findings("") == []
    assert extract_review_findings("no critical findings here") == []


def test_spec_verify_extractor_accepts_multiple_markers():
    from set_orch.findings import extract_spec_verify_findings

    output = """
[CRITICAL] Missing AC-3 implementation
File: src/app/cart/actions.ts:15
Fix: Implement the `clearCart()` server action per AC-3.

[MISSING] spec.md requires a /api/cart/clear endpoint
File: src/app/api/cart/clear/route.ts

[FAIL] Spec says total must be tax-exclusive but implementation adds tax
File: src/lib/cart.ts:88
Fix: Move tax calc outside the cart-total formula.
"""
    findings = extract_spec_verify_findings(output)
    titles = [f.title for f in findings]
    assert any("Missing AC-3" in t for t in titles)
    assert any("requires a /api/cart/clear" in t for t in titles)
    assert any("tax-exclusive" in t for t in titles)
    # Severity mapping
    severities = {f.severity for f in findings}
    assert "critical" in severities
    assert "warning" in severities  # MISSING / FAIL map to warning


def test_e2e_extractor_parses_playwright_numbered_failures():
    from set_orch.findings import extract_e2e_findings

    output = """
Running 3 tests using 1 worker.

  1) [chromium] › tests/e2e/cart.spec.ts:42 › REQ-CART-001 adds item to cart
     Error: expect(locator).toHaveText(expected)
     Expected: "2 items"
     Received: "0 items"

       at tests/e2e/cart.spec.ts:47:18

  2) [chromium] › tests/e2e/checkout.spec.ts:18 › REQ-CHECKOUT-002 shows shipping form
     Error: Timed out 10000ms waiting for locator('[data-testid="shipping-form"]')

       at tests/e2e/checkout.spec.ts:23:12

2 failed
"""
    findings = extract_e2e_findings(output)
    assert len(findings) == 2
    a, b = findings
    assert a.file == "tests/e2e/cart.spec.ts" and a.line_start == 42
    assert "REQ-CART-001" in a.title
    assert "toHaveText" in a.fix_block or "toHaveText" in a.code_context
    assert b.file == "tests/e2e/checkout.spec.ts" and b.line_start == 18


def test_e2e_extractor_strips_ansi_escapes():
    from set_orch.findings import extract_e2e_findings

    output = "\x1b[31m  1) [chromium] \u203A tests/e2e/a.spec.ts:10 \u203A title\x1b[0m\n"
    findings = extract_e2e_findings(output)
    assert len(findings) == 1
    assert findings[0].file == "tests/e2e/a.spec.ts"
    assert findings[0].line_start == 10


def test_extractors_return_empty_on_malformed_input():
    from set_orch.findings import (
        extract_e2e_findings, extract_review_findings, extract_spec_verify_findings,
    )
    # Non-matching blob — should return empty lists, not exceptions
    blob = "random error log lines with no markers\n\ttraceback...\n"
    assert extract_review_findings(blob) == []
    assert extract_spec_verify_findings(blob) == []
    assert extract_e2e_findings(blob) == []


def test_render_findings_block_orders_by_severity():
    from set_orch.findings import Finding, fingerprint, render_findings_block

    fs = [
        Finding(id="1", severity="warning", title="w", file="a", line_start=1,
                fingerprint=fingerprint("a", 1, "w")),
        Finding(id="2", severity="critical", title="c", file="b", line_start=2,
                fingerprint=fingerprint("b", 2, "c")),
        Finding(id="3", severity="info", title="i", file="c", line_start=3,
                fingerprint=fingerprint("c", 3, "i")),
    ]
    text = render_findings_block(fs)
    # critical first, then warning, then info
    c_idx = text.index("[CRITICAL]")
    w_idx = text.index("[WARNING]")
    i_idx = text.index("[INFO]")
    assert c_idx < w_idx < i_idx


def test_findings_from_dicts_tolerates_unknown_keys():
    from set_orch.findings import findings_from_dicts

    raw = [
        {"id": "1", "title": "ok", "unexpected_field": "ignored", "severity": "critical",
         "file": "x.ts", "line_start": 1},
        {"not_a_real_dict": None},  # still a dict, just weird
        "totally-not-a-dict",
    ]
    out = findings_from_dicts(raw)
    assert len(out) >= 1
    assert out[0].severity == "critical" and out[0].file == "x.ts"
