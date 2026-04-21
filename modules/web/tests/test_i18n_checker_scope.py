"""Regression tests for the i18n completeness checker's binding scope handling.

The previous implementation used a file-global `Map<variable, namespace>`
that got overwritten by later bindings in the same file. When two function
scopes each declared `const t = useTranslations(...)` with different
namespaces, the second binding silently reassigned all preceding `t(...)`
calls to the wrong namespace — producing false-positive missing-key reports.

Observed in craftbrew-run-20260421-0025 / catalog-listings-and-homepage,
where `generateMetadata` used `t` for a category namespace and the Page
function used `t` for `nav`. The agent worked around the bug by renaming
`t` → `tNav`; this test locks in the fix to the checker itself.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest


def _has_runner() -> bool:
    if shutil.which("tsx"):
        return True
    return shutil.which("npx") is not None


CHECKER_SRC = os.path.join(
    os.path.dirname(__file__), "..",
    "set_project_web", "templates", "nextjs", "scripts",
    "check-i18n-completeness.ts",
)


@pytest.fixture
def fixture_root(tmp_path):
    """Minimal Next.js-shaped tree that the checker can scan."""
    root = tmp_path / "wt"
    (root / "messages").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "scripts").mkdir()
    shutil.copy(CHECKER_SRC, root / "scripts" / "check-i18n-completeness.ts")
    return root


def _run_checker(root) -> subprocess.CompletedProcess:
    if not _has_runner():
        pytest.skip("tsx/npx not available")
    runner_cmd = ["npx", "--yes", "tsx"] if not shutil.which("tsx") else ["tsx"]
    return subprocess.run(
        [*runner_cmd, "scripts/check-i18n-completeness.ts"],
        cwd=str(root), capture_output=True, text=True, timeout=60,
    )


def _nested_set(obj, dotted_key, value):
    """Assign {a: {b: {c: value}}} for dotted_key='a.b.c' — matches the
    nested-object layout the checker's hasKey() traverses.
    """
    parts = dotted_key.split(".")
    cur = obj
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def _write_locales(root, keys_by_ns):
    """keys_by_ns = {"nav": ["home", "coffees"], "catalog.listings.kavek": ["title"]}

    Namespaces with dots are expanded into the correctly-nested object shape
    the checker expects (matches real next-intl locale files).
    """
    payload: dict = {}
    for ns, keys in keys_by_ns.items():
        for k in keys:
            _nested_set(payload, f"{ns}.{k}", f"stub-{k}")
    # every locale gets the same set — we're testing key resolution, not translation
    for locale in ("en", "hu"):
        (root / "messages" / f"{locale}.json").write_text(json.dumps(payload))


# ─────────────────────────────────────────────────────────────────────
# Regression: sibling function scopes with the same binding name
# ─────────────────────────────────────────────────────────────────────


class TestSiblingScope:
    def test_two_functions_same_var_different_namespace(self, fixture_root):
        """The exact catalog-listings-and-homepage pattern.

        `generateMetadata` binds `t` to one namespace; `Page` binds `t` to
        another. Each function only calls keys from its own namespace.
        Checker must resolve each call against the nearest preceding
        binding — not a file-global winner.
        """
        _write_locales(fixture_root, {
            "catalog.listings.kavek": ["title", "description"],
            "nav": ["home", "coffees"],
        })

        (fixture_root / "src" / "kavek" / "page.tsx").parent.mkdir(parents=True)
        (fixture_root / "src" / "kavek" / "page.tsx").write_text(
            "import { getTranslations } from 'next-intl/server';\n"
            "\n"
            "export async function generateMetadata() {\n"
            "  const t = await getTranslations({ namespace: 'catalog.listings.kavek' });\n"
            "  return { title: t('title'), description: t('description') };\n"
            "}\n"
            "\n"
            "export default async function Page() {\n"
            "  const t = await getTranslations({ namespace: 'nav' });\n"
            "  return `${t('home')} / ${t('coffees')}`;\n"
            "}\n"
        )

        result = _run_checker(fixture_root)

        assert result.returncode == 0, (
            "checker wrongly flagged keys as missing — probably resolved "
            "`t('title')` against namespace 'nav' instead of 'catalog.listings.kavek'.\n\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_single_binding_unchanged(self, fixture_root):
        """Sanity: a file with one binding must keep working (happy path)."""
        _write_locales(fixture_root, {"hello": ["title", "body"]})
        (fixture_root / "src" / "Hello.tsx").write_text(
            "import { useTranslations } from 'next-intl';\n"
            "export function Hello() {\n"
            "  const t = useTranslations('hello');\n"
            "  return `${t('title')} / ${t('body')}`;\n"
            "}\n"
        )

        result = _run_checker(fixture_root)
        assert result.returncode == 0, \
            f"single-binding smoke failed — {result.stdout}\n{result.stderr}"

    def test_still_detects_genuinely_missing_keys(self, fixture_root):
        """Negative safety: proximity resolution must NOT hide real missing keys."""
        _write_locales(fixture_root, {"nav": ["home"]})  # no "coffees"
        (fixture_root / "src" / "page.tsx").write_text(
            "import { useTranslations } from 'next-intl';\n"
            "export function Page() {\n"
            "  const t = useTranslations('nav');\n"
            "  return `${t('home')} ${t('coffees')}`;\n"
            "}\n"
        )

        result = _run_checker(fixture_root)
        assert result.returncode == 1, \
            "checker missed a genuinely-absent key (nav.coffees)"
        combined = result.stdout + result.stderr
        assert "nav.coffees" in combined, \
            f"missing-key output did not mention nav.coffees:\n{combined}"
