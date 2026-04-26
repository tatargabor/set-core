"""Regression tests for stub-test detection in the coverage gate.

Witnessed in ``micro-web-run-20260426-1704`` contact-wizard-form:
the agent generated 18 e2e tests with empty ``// TODO: implement``
bodies, all of which "passed" trivially (no assertions to fail). The
coverage gate's structural-only check (``test exists for REQ-X``)
counted them as covering, so the change merged with a blank contact
page — the wizard component compiled fine, but the page never rendered
it. Cost: ~$120 of agent fix-loop on a bug that should have been
gate-blocked at first dispatch.

These tests pin the fix: ``detect_stub_tests`` and the resulting
filter in ``build_test_coverage`` must keep stub tests from inflating
coverage. If a future contributor relaxes the filter, the
contact-wizard-style merge slips through again.
"""

from __future__ import annotations

import pytest

from set_orch.test_coverage import (
    TestCase,
    build_test_coverage,
    detect_stub_tests,
    _is_stub_match,
)


# ─── detect_stub_tests ──────────────────────────────────────────────────


def test_empty_body_with_todo_marker_is_stub(tmp_path):
    """Witnessed contact-wizard-form scaffold: every test had this shape."""
    spec = tmp_path / "contact-wizard-form.spec.ts"
    spec.write_text("""
import { test, expect } from '@playwright/test';

test('REQ-FORM-001:AC-1 — Dialog opens from contact-dialog-trigger @SMOKE', { tag: '@smoke' }, async ({ page }) => {
    // TODO: implement
});

test('REQ-FORM-001:AC-2 — Stepper indicator shows 3 steps', async ({ page }) => {
    // TODO: implement
});
""")
    stubs = detect_stub_tests(spec)
    assert len(stubs) == 2
    names = {n for _, n in stubs}
    assert "REQ-FORM-001:AC-1 — Dialog opens from contact-dialog-trigger @SMOKE" in names
    assert "REQ-FORM-001:AC-2 — Stepper indicator shows 3 steps" in names


def test_real_body_with_expect_is_not_stub(tmp_path):
    spec = tmp_path / "real.spec.ts"
    spec.write_text("""
import { test, expect } from '@playwright/test';

test('real test', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/foo/);
});
""")
    assert detect_stub_tests(spec) == set()


def test_commented_expect_does_not_count(tmp_path):
    """An ``// expect(...)`` line is dead code, not a real assertion."""
    spec = tmp_path / "fake.spec.ts"
    spec.write_text("""
import { test, expect } from '@playwright/test';

test('hidden stub', async ({ page }) => {
    // expect(page.url()).toBe('/');  -- commented out
});
""")
    stubs = detect_stub_tests(spec)
    assert ("fake.spec.ts", "hidden stub") in stubs


def test_block_commented_expect_does_not_count(tmp_path):
    spec = tmp_path / "fake.spec.ts"
    spec.write_text("""
test('block-comment stub', async ({ page }) => {
    /* expect(page).toHaveTitle('foo');
       expect(page).toBeOK();
    */
});
""")
    stubs = detect_stub_tests(spec)
    assert ("fake.spec.ts", "block-comment stub") in stubs


def test_test_skip_form_detected(tmp_path):
    """``test.skip(...)`` and ``test.only(...)`` use ``test.<modifier>``."""
    spec = tmp_path / "skip.spec.ts"
    spec.write_text("""
test.skip('skipped stub', async () => {
    // TODO: implement
});
""")
    stubs = detect_stub_tests(spec)
    assert ("skip.spec.ts", "skipped stub") in stubs


def test_mixed_stub_and_real_in_same_file(tmp_path):
    """Stubs detected per-test, not per-file."""
    spec = tmp_path / "mixed.spec.ts"
    spec.write_text("""
test('real one', async ({ page }) => {
    await expect(page).toHaveURL(/foo/);
});

test('stub one', async ({ page }) => {
    // TODO: implement
});

test('another real', async ({ page }) => {
    await page.goto('/foo');
    expect(page.url()).toContain('/foo');
});
""")
    stubs = detect_stub_tests(spec)
    assert ("mixed.spec.ts", "stub one") in stubs
    assert ("mixed.spec.ts", "real one") not in stubs
    assert ("mixed.spec.ts", "another real") not in stubs


def test_describe_wrapped_test_still_detected(tmp_path):
    """Tests inside ``describe`` blocks must still be scannable."""
    spec = tmp_path / "described.spec.ts"
    spec.write_text("""
test.describe('REQ-FORM-001 group', () => {
    test('inner stub', async () => {
        // TODO: implement
    });

    test('inner real', async ({ page }) => {
        await page.goto('/');
        await expect(page.locator('h1')).toBeVisible();
    });
});
""")
    stubs = detect_stub_tests(spec)
    assert ("described.spec.ts", "inner stub") in stubs
    assert ("described.spec.ts", "inner real") not in stubs


def test_missing_file_returns_empty_set(tmp_path):
    assert detect_stub_tests(tmp_path / "nope.spec.ts") == set()


# ─── Trivial-assertion gaming patterns ──────────────────────────────────


def test_expect_true_to_be_true_is_stub(tmp_path):
    """Most obvious gaming pattern — should be flagged as stub."""
    spec = tmp_path / "game.spec.ts"
    spec.write_text("""
test('gamed', async ({ page }) => {
    expect(true).toBe(true);
});
""")
    stubs = detect_stub_tests(spec)
    assert ("game.spec.ts", "gamed") in stubs


def test_numeric_literal_trivial_is_stub(tmp_path):
    spec = tmp_path / "game.spec.ts"
    spec.write_text("""
test('numeric gaming', async ({ page }) => {
    expect(1).toBe(1);
    expect(42).toEqual(42);
});
""")
    assert ("game.spec.ts", "numeric gaming") in detect_stub_tests(spec)


def test_string_literal_trivial_is_stub(tmp_path):
    spec = tmp_path / "game.spec.ts"
    spec.write_text("""
test('string gaming', async ({ page }) => {
    expect('').toBe('');
});
""")
    assert ("game.spec.ts", "string gaming") in detect_stub_tests(spec)


def test_null_undefined_trivials_are_stubs(tmp_path):
    spec = tmp_path / "game.spec.ts"
    spec.write_text("""
test('null gaming', async () => {
    expect(null).toBeNull();
});

test('undefined gaming', async () => {
    expect(undefined).toBeUndefined();
});
""")
    stubs = detect_stub_tests(spec)
    assert ("game.spec.ts", "null gaming") in stubs
    assert ("game.spec.ts", "undefined gaming") in stubs


def test_real_expect_alongside_trivial_is_not_stub(tmp_path):
    """If the test has at least one meaningful expect, it's real even
    if the agent also added a trivial one."""
    spec = tmp_path / "mixed.spec.ts"
    spec.write_text("""
test('real with sanity', async ({ page }) => {
    expect(true).toBe(true);  // sanity check
    await page.goto('/');
    await expect(page).toHaveTitle(/foo/);
});
""")
    assert detect_stub_tests(spec) == set()


def test_real_dom_expect_is_not_stub(tmp_path):
    """A page-state expect counts even without literals."""
    spec = tmp_path / "real.spec.ts"
    spec.write_text("""
test('real navigate', async ({ page }) => {
    await page.goto('/contact');
    await expect(page.locator('[data-testid="contact-dialog-trigger"]')).toBeVisible();
});
""")
    assert detect_stub_tests(spec) == set()


# ─── _is_stub_match ─────────────────────────────────────────────────────


def test_match_handles_describe_prefix():
    """Playwright reports ``describe › test``; stub set has just ``test``."""
    stubs = {("contact.spec.ts", "REQ-FORM-001:AC-1 — Dialog opens")}
    # Playwright runtime form
    assert _is_stub_match(
        "tests/e2e/contact.spec.ts",
        "REQ-FORM-001: Dialog opens from contact-dialog-trigger › REQ-FORM-001:AC-1 — Dialog opens",
        stubs,
    )


def test_match_exact_form():
    stubs = {("foo.spec.ts", "exact test")}
    assert _is_stub_match("foo.spec.ts", "exact test", stubs)


def test_no_match_different_file():
    stubs = {("foo.spec.ts", "name")}
    assert not _is_stub_match("bar.spec.ts", "name", stubs)


def test_empty_stub_set_returns_false():
    assert not _is_stub_match("any.spec.ts", "any name", set())


# ─── build_test_coverage with stubs ─────────────────────────────────────


def test_all_stubs_drives_coverage_to_zero():
    """Witnessed regression: 18/18 stubs gave 100% coverage. After fix,
    they give 0% so the gate fails."""
    test_cases = [
        TestCase(
            scenario_slug="dialog-opens",
            req_id="REQ-FORM-001",
            risk="MEDIUM",
            test_file="contact.spec.ts",
            test_name="REQ-FORM-001:AC-1 — Dialog opens",
            category="happy",
            ac_id="REQ-FORM-001:AC-1",
        ),
    ]
    test_results = {
        ("contact.spec.ts", "REQ-FORM-001:AC-1 — Dialog opens"): "pass",
    }
    stub_tests = {("contact.spec.ts", "REQ-FORM-001:AC-1 — Dialog opens")}

    cov = build_test_coverage(
        test_cases=test_cases,
        non_testable=[],
        test_results=test_results,
        digest_req_ids=["REQ-FORM-001"],
        stub_tests=stub_tests,
    )

    assert cov.covered_reqs == []
    assert cov.uncovered_reqs == ["REQ-FORM-001"]
    assert cov.coverage_pct == 0.0
    assert "contact.spec.ts::REQ-FORM-001:AC-1 — Dialog opens" in cov.stub_tests


def test_mixed_stubs_and_real_coverage_partial():
    """REQ with one stub + one real test = covered (the real one suffices)."""
    test_cases = [
        TestCase(
            scenario_slug="real",
            req_id="REQ-A",
            risk="MEDIUM",
            test_file="a.spec.ts",
            test_name="real test",
            category="happy",
        ),
        TestCase(
            scenario_slug="stub",
            req_id="REQ-A",
            risk="MEDIUM",
            test_file="a.spec.ts",
            test_name="stub test",
            category="happy",
        ),
        TestCase(
            scenario_slug="orphan-stub",
            req_id="REQ-B",
            risk="MEDIUM",
            test_file="b.spec.ts",
            test_name="b stub",
            category="happy",
        ),
    ]
    test_results = {
        ("a.spec.ts", "real test"): "pass",
        ("a.spec.ts", "stub test"): "pass",
        ("b.spec.ts", "b stub"): "pass",
    }
    stub_tests = {
        ("a.spec.ts", "stub test"),
        ("b.spec.ts", "b stub"),
    }

    cov = build_test_coverage(
        test_cases=test_cases,
        non_testable=[],
        test_results=test_results,
        digest_req_ids=["REQ-A", "REQ-B"],
        stub_tests=stub_tests,
    )

    assert "REQ-A" in cov.covered_reqs
    assert "REQ-B" in cov.uncovered_reqs
    assert cov.coverage_pct == 50.0


def test_no_stubs_param_keeps_legacy_behavior():
    """Backward-compat: omitting ``stub_tests`` matches the old logic."""
    test_cases = [
        TestCase(
            scenario_slug="t1",
            req_id="REQ-X",
            risk="MEDIUM",
            test_file="x.spec.ts",
            test_name="REQ-X:AC-1 — anything",
            category="happy",
            ac_id="REQ-X:AC-1",
        ),
    ]
    test_results = {("x.spec.ts", "REQ-X:AC-1 — anything"): "pass"}

    cov = build_test_coverage(
        test_cases=test_cases,
        non_testable=[],
        test_results=test_results,
        digest_req_ids=["REQ-X"],
    )
    assert cov.covered_reqs == ["REQ-X"]
    assert cov.coverage_pct == 100.0
    assert cov.stub_tests == []


def test_journey_fallback_does_not_trigger_on_stubs():
    """The 'no AC bindings, but plan has test files' fallback also
    excludes stub-only test_cases — otherwise stub-only changes would
    still hit covered=all via the fallback."""
    test_cases = [
        TestCase(
            scenario_slug="only-stub",
            req_id="REQ-J",
            risk="MEDIUM",
            test_file="j.spec.ts",
            test_name="j stub",  # plan has no AC-IDs
            category="happy",
        ),
    ]
    test_results = {("j.spec.ts", "j stub"): "pass"}
    stub_tests = {("j.spec.ts", "j stub")}

    cov = build_test_coverage(
        test_cases=test_cases,
        non_testable=[],
        test_results=test_results,
        digest_req_ids=["REQ-J"],
        stub_tests=stub_tests,
    )

    assert cov.covered_reqs == []
    assert cov.uncovered_reqs == ["REQ-J"]


# ─── End-to-end witnessed scenario ──────────────────────────────────────


def test_contact_wizard_form_regression(tmp_path):
    """Reproduces the witnessed micro-web-run-20260426-1704 case: 18 stubs
    in tests/e2e/, all REQ-FORM-* bound. After fix, 0% coverage."""
    spec = tmp_path / "contact-wizard-form.spec.ts"
    body_lines = ["import { test, expect } from '@playwright/test';", ""]
    test_cases = []
    test_results = {}
    req_ids = []
    for i in range(1, 19):
        ac = f"REQ-FORM-{(i - 1) // 3 + 1:03d}:AC-{(i - 1) % 3 + 1}"
        rid = ac.split(":")[0]
        name = f"{ac} — scenario {i}"
        body_lines.append(f"test('{name}', async ({{ page }}) => {{")
        body_lines.append("    // TODO: implement")
        body_lines.append("});")
        body_lines.append("")
        test_cases.append(TestCase(
            scenario_slug=f"scenario-{i}",
            req_id=rid,
            risk="MEDIUM",
            test_file="contact-wizard-form.spec.ts",
            test_name=name,
            category="happy",
            ac_id=ac,
        ))
        test_results[("contact-wizard-form.spec.ts", name)] = "pass"
        if rid not in req_ids:
            req_ids.append(rid)
    spec.write_text("\n".join(body_lines))

    stubs = detect_stub_tests(spec)
    assert len(stubs) == 18

    cov = build_test_coverage(
        test_cases=test_cases,
        non_testable=[],
        test_results=test_results,
        digest_req_ids=req_ids,
        stub_tests=stubs,
    )
    assert cov.coverage_pct == 0.0
    assert sorted(cov.uncovered_reqs) == sorted(req_ids)
    assert len(cov.stub_tests) == 18
