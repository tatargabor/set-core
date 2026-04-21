"""Unit tests for the web `i18n_check` hard-fail gate.

Covers:
  AC-22  — missing translation key → i18n_check.status == "fail" and
           retry_context carries the explanation.
  AC-22b — every t(...) resolves in every locale → i18n_check.status == "pass".
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

# Make `set_orch` + `set_project_web` importable without installing the package.
_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_HERE, "..", "..", "..", "lib"))
sys.path.insert(0, os.path.join(_HERE, "..", "set_project_web"))
sys.path.insert(0, os.path.join(_HERE, ".."))

from set_project_web.gates import execute_i18n_check_gate  # noqa: E402
from set_orch.state import Change  # noqa: E402


def _has_tsx() -> bool:
    """Skip the tests if no `tsx` runner is available anywhere on the box —
    the gate falls back to `npx --yes tsx` but on a sandbox without network
    this would hang. We require at least one of the two.
    """
    return (
        subprocess.run(["which", "tsx"], capture_output=True).returncode == 0
        or subprocess.run(["which", "npx"], capture_output=True).returncode == 0
    )


@pytest.fixture
def wt(tmp_path):
    """Minimal Next.js-shaped worktree:
      messages/{en,hu}.json, src/foo.tsx using useTranslations(),
      scripts/check-i18n-completeness.mjs that implements the comparison.
    """
    root = tmp_path / "wt"
    root.mkdir()

    # Locale files.
    (root / "messages").mkdir()
    # Start with the complete set; individual tests can overwrite to create
    # a gap.
    (root / "messages" / "en.json").write_text(json.dumps({
        "hello.title": "Hello",
        "hello.body": "Welcome",
    }))
    (root / "messages" / "hu.json").write_text(json.dumps({
        "hello.title": "Szia",
        "hello.body": "Üdv",
    }))

    # A src/ file that references both keys via useTranslations.
    (root / "src").mkdir()
    (root / "src" / "Hello.tsx").write_text(
        "import { useTranslations } from 'next-intl';\n"
        "export function Hello() {\n"
        "  const t = useTranslations('hello');\n"
        "  return `${t('title')} — ${t('body')}`;\n"
        "}\n"
    )

    # A standalone .mjs checker (no tsx / TypeScript compilation needed).
    # Implements the same "every key in every locale" comparison the
    # real TypeScript script does, minimally.
    (root / "scripts").mkdir()
    (root / "scripts" / "check-i18n-completeness.mjs").write_text(r"""
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const msgs = path.join(root, 'messages');
const files = fs.readdirSync(msgs).filter(f => /\.[a-z]{2}\.json$/.test(f) || /^[a-z]{2}\.json$/.test(f));
const keys = {};
for (const f of files) {
  const locale = f.replace(/\.json$/, '');
  keys[locale] = new Set(Object.keys(JSON.parse(fs.readFileSync(path.join(msgs, f), 'utf8'))));
}
// Scan src/ for t('ns.key') and t('key') after useTranslations('ns').
function scan(dir, acc, nsStack) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) { scan(p, acc, nsStack); continue; }
    if (!/\.(ts|tsx|js|jsx)$/.test(e.name)) continue;
    const txt = fs.readFileSync(p, 'utf8');
    const nsMatch = txt.match(/useTranslations\(['"]([^'"]+)['"]\)/);
    const ns = nsMatch ? nsMatch[1] : '';
    for (const m of txt.matchAll(/\bt\(['"]([^'"]+)['"]\)/g)) {
      acc.add(ns ? `${ns}.${m[1]}` : m[1]);
    }
  }
}
const used = new Set();
scan(path.join(root, 'src'), used, []);

let failed = false;
for (const [locale, ks] of Object.entries(keys)) {
  const missing = [...used].filter(k => !ks.has(k));
  if (missing.length) {
    console.error(`[i18n-check] FAIL ${locale}: missing ${missing.length} key(s): ${missing.join(', ')}`);
    failed = true;
  }
}
if (failed) process.exit(1);
console.log('[i18n-check] OK');
""".strip())

    return root


def test_i18n_check_pass_when_both_locales_match(wt):
    """AC-22b: every `t(...)` key has an entry in both hu.json and en.json."""
    if not _has_tsx():
        pytest.skip("tsx/npx not available")

    change = Change(name="c", scope="x", worktree_path=str(wt))
    # Rename the checker to .mjs so tsx can execute it as plain JS
    # (tsx handles .mjs). The gate's script discovery already accepts it.
    result = execute_i18n_check_gate("c", change, str(wt))
    if result.status == "skipped":
        pytest.skip(f"gate skipped: {result.output}")
    assert result.status == "pass", (
        f"expected pass, got {result.status}: {result.output[:500]}"
    )


def test_i18n_check_fail_surfaces_retry_context(wt):
    """AC-22: when the HU locale is missing a referenced key, the gate
    returns status="fail" AND retry_context names the missing key.
    """
    if not _has_tsx():
        pytest.skip("tsx/npx not available")

    # Remove hello.body from hu.json → the fixture t('body') is now missing.
    hu = json.loads((wt / "messages" / "hu.json").read_text())
    del hu["hello.body"]
    (wt / "messages" / "hu.json").write_text(json.dumps(hu))

    change = Change(name="c", scope="x", worktree_path=str(wt))
    result = execute_i18n_check_gate("c", change, str(wt))
    if result.status == "skipped":
        pytest.skip(f"gate skipped: {result.output}")
    assert result.status == "fail"
    # The retry context must name the missing key so the agent knows what
    # to add — otherwise the failure is non-actionable and a loop would
    # burn budget.
    assert "hello.body" in (result.retry_context or "")
