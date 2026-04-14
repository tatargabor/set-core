"""Regression test: web template ships i18n baseline keys mirrored across locales.

See OpenSpec change: fix-e2e-infra-systematic (T1.1).

Missing or out-of-sync baseline keys (home.*, nav.*, footer.*, common.*) cause
cascading Playwright failures on fresh scaffolds — a single missing key triggers
next-intl MISSING_MESSAGE, which the UI surfaces as a hydration error, which
every page-level e2e test then flakes on. Ensuring the template ships a complete
and mirrored baseline eliminates this class of spurious gate failure.
"""

from __future__ import annotations

import json
from pathlib import Path

_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / (
    "modules/web/set_project_web/templates/nextjs/messages"
)

# Baseline namespaces and the minimum keys each must define. If you add a key
# here, add it to both hu.json and en.json in the template.
_REQUIRED = {
    "home": {"title", "subtitle", "cta"},
    "nav": {"home", "login", "logout", "register"},
    "footer": {"copyright", "privacy", "terms"},
    "common": {"loading", "error", "save", "cancel", "submit", "search"},
}


def _load(locale: str) -> dict:
    p = _TEMPLATE_DIR / f"{locale}.json"
    assert p.is_file(), f"Template missing baseline locale file: {p}"
    return json.loads(p.read_text())


def test_hu_has_all_required_baseline_keys():
    data = _load("hu")
    for ns, keys in _REQUIRED.items():
        assert ns in data, f"hu.json missing namespace '{ns}'"
        missing = keys - set(data[ns].keys())
        assert not missing, f"hu.json missing keys under '{ns}': {missing}"


def test_en_has_all_required_baseline_keys():
    data = _load("en")
    for ns, keys in _REQUIRED.items():
        assert ns in data, f"en.json missing namespace '{ns}'"
        missing = keys - set(data[ns].keys())
        assert not missing, f"en.json missing keys under '{ns}': {missing}"


def _flatten(d: dict, prefix: str = "") -> set[str]:
    out: set[str] = set()
    for k, v in d.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, full))
        else:
            out.add(full)
    return out


def test_hu_and_en_have_identical_key_sets():
    """Sidecar merge is deep — unbalanced key sets between locales produce
    MISSING_MESSAGE errors on the locale that's short a key. Baseline MUST be
    mirrored one-for-one across locales."""
    hu_keys = _flatten(_load("hu"))
    en_keys = _flatten(_load("en"))
    only_hu = hu_keys - en_keys
    only_en = en_keys - hu_keys
    assert not only_hu, f"Keys only in hu.json (missing from en.json): {sorted(only_hu)}"
    assert not only_en, f"Keys only in en.json (missing from hu.json): {sorted(only_en)}"


def test_script_present_and_shebang():
    script = _TEMPLATE_DIR.parent / "scripts" / "check-i18n-completeness.ts"
    assert script.is_file(), f"i18n check script missing: {script}"
    head = script.read_text().splitlines()[0]
    assert head.startswith("#!") or "env tsx" in head or "tsx" in head, head
