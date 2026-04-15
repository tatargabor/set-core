"""Regression test: web-conventions.md encodes the Radix Select click-hang fix.

Observed on craftbrew-run-20260415-0146 admin-products REQ-ADM-002:AC-1:
`locator.click: Timeout 10000ms exceeded ... performing click action` on a
`role=option` element that Playwright confirmed was visible+enabled. Radix
Select commits selection on `pointerup`, closes the portal, detaches the
option — Playwright's post-click "verify element settled" step then races a
non-existent element and times out.

The fix agent worked around this with `element.dispatchEvent(new MouseEvent(...))`,
which makes the test pass but stops exercising the real pointer-event chain —
production code paths go unverified. We codify:

  1. The root cause in web-conventions.md (three mechanics: portal mount,
     pointer-vs-click, re-render cascade) so agents understand why the naive
     pattern flakes.
  2. Keyboard navigation as the preferred pattern.
  3. `click({ noWaitAfter: true })` as the fallback.
  4. An explicit ban on `dispatchEvent('click')`.
  5. A re-query rule for locators captured before a filter change.

This test pins those sections in place so an accidental edit can't silently
delete the hard-won guidance.
"""

from __future__ import annotations

from pathlib import Path

_CONVENTIONS = Path(__file__).resolve().parents[2] / (
    "modules/web/set_project_web/templates/nextjs/rules/web-conventions.md"
)


def _text() -> str:
    assert _CONVENTIONS.is_file(), f"Template missing: {_CONVENTIONS}"
    return _CONVENTIONS.read_text()


def test_radix_section_explains_root_cause():
    text = _text()
    # Three distinct mechanics must be called out — not just "portal race".
    assert "Portal mount" in text, "missing portal-mount mechanic"
    assert "Pointer events, not click" in text, "missing pointer-vs-click mechanic"
    assert "re-render cascade" in text, "missing re-render-cascade mechanic"


def test_radix_section_bans_dispatch_event_workaround():
    text = _text()
    # The specific anti-pattern we saw in the wild must be explicitly forbidden.
    assert "dispatchEvent" in text, "dispatchEvent must be named"
    assert "DO NOT DO THIS" in text or "Forbidden" in text, (
        "dispatchEvent must be flagged as forbidden, not merely mentioned"
    )


def test_radix_section_recommends_keyboard_first():
    text = _text()
    # Keyboard path is the primary recommendation — its presence, not merely
    # `.click()` with workarounds, is what avoids the post-action settle hang.
    assert "page.keyboard.press" in text, "keyboard pattern missing"
    assert "Enter" in text, "Enter key-press step missing"


def test_radix_section_documents_no_wait_after_fallback():
    text = _text()
    # If keyboard is not viable, noWaitAfter is the documented mouse fallback.
    assert "noWaitAfter" in text, "noWaitAfter fallback missing"


def test_radix_section_requires_toContainText_confirmation():
    text = _text()
    # Every pattern must end with a trigger.toContainText(value) assertion
    # before the test proceeds — otherwise the next action races the commit.
    assert "toContainText" in text, "post-selection confirmation assertion missing"


def test_radix_section_explains_requery_after_filter():
    text = _text()
    # The second-order bug: locators captured before onValueChange become
    # detached after router.replace re-hydrates the table. Re-query rule.
    assert "re-query" in text.lower(), "re-query rule for post-filter locators missing"
    assert "detached" in text.lower() or "stale" in text.lower(), (
        "must explain the detached/stale-locator failure mode"
    )


def test_quick_reference_table_mentions_requery():
    text = _text()
    # The quick-reference row for #6 should hint at the second failure mode
    # so readers skimming the table are steered to the re-query guidance.
    lines = [ln for ln in text.splitlines() if ln.startswith("|") and "#6" in ln]
    assert lines, "quick-reference entry for #6 missing"
    assert any("re-query" in ln.lower() or "row detached" in ln.lower() for ln in lines), (
        "quick-reference #6 row should mention the re-query / detach angle"
    )
