"""Web-specific tests for the dispatcher's Implementation Manifest.

The core extractor (`set_orch.dispatcher._extract_implementation_manifest`)
is project-agnostic — it consumes the active profile's
`scope_manifest_extensions()` and `scope_manifest_extras()` hooks. These
tests exercise the WebProjectType implementation:

- TSX/JSX/TS/JS/CSS extensions surface in the file section
- `<PascalCase>` JSX components surface as the extras section

Why this lives in modules/web/tests/: per modular-architecture.md, web
patterns (React, JSX, .tsx) belong in modules/web/, not lib/set_orch/.
The core test (tests/unit/test_implementation_manifest.py) only checks
project-agnostic behavior with the default profile.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from set_orch.dispatcher import _extract_implementation_manifest
from set_project_web.project_type import WebProjectType


@pytest.fixture
def web_profile():
    """Force `load_profile()` (imported lazily inside the dispatcher) to
    return WebProjectType. The dispatcher does
    `from .profile_loader import load_profile` inside the function, so we
    must patch at the source module."""
    profile = WebProjectType()
    with patch("set_orch.profile_loader.load_profile", return_value=profile):
        yield profile


# Verbatim scope from micro-web-run-20260426-1127 — the run that merged
# with 4 missing deps, 2 missing shells, and 0 ThemeProvider wrap.
FAILING_SCOPE = (
    "Infrastructure for the entire scaffold. Set up package.json scripts "
    "('dev', 'build' = 'next build', 'test' = 'vitest run', 'test:e2e' = "
    "'playwright test'), install next/react/tailwind/shadcn/next-themes/"
    "sonner/react-hook-form/zod/vitest/@playwright/test. Create "
    "vitest.config.ts (jsdom env, exclude tests/e2e/**), playwright.config.ts "
    "(workers:1, reuseExistingServer:false, screenshot:'on', headless:true, "
    "webServer auto-start). Mount v0-export shells: copy site-header.tsx, "
    "site-footer.tsx, theme-provider.tsx, mobile-nav.tsx into src/components/ "
    "and src/app/globals.css. Create src/app/layout.tsx wrapping children "
    "in <ThemeProvider attribute='class' defaultTheme='system'> + sonner "
    "<Toaster />."
)


def test_web_extensions_registered():
    """WebProjectType registers source-language extensions on top of
    universal ones. The profile may return them in any order — the
    dispatcher's regex-builder sorts by descending length so the
    alternation matches longest-first (`json` before `js`,
    `tsx` before `ts`). The contract here is just: all needed
    extensions are present."""
    web = WebProjectType()
    exts = web.scope_manifest_extensions()
    for e in ("tsx", "jsx", "ts", "js", "css", "json", "yaml", "md"):
        assert e in exts, f"web profile must register .{e}"


def test_web_failing_scope_extracts_missing_packages(web_profile):
    """The exact 4 packages the failing run silently dropped (next-themes,
    sonner, react-hook-form, zod) MUST appear in the manifest."""
    out = _extract_implementation_manifest(FAILING_SCOPE)
    for pkg in ("next-themes", "sonner", "react-hook-form", "zod"):
        assert f"`{pkg}`" in out, f"missing package {pkg} from web manifest"
    # Scoped packages preserved
    assert "`@playwright/test`" in out
    # Other packages from the same install clause
    for pkg in ("next", "react", "vitest"):
        assert f"`{pkg}`" in out


def test_web_failing_scope_extracts_missing_files(web_profile):
    """The 2 shell files the failing run skipped (theme-provider.tsx,
    mobile-nav.tsx) MUST appear. Plus other source files in scope."""
    out = _extract_implementation_manifest(FAILING_SCOPE)
    for f in (
        "theme-provider.tsx",
        "mobile-nav.tsx",
        "site-header.tsx",
        "site-footer.tsx",
        "vitest.config.ts",
        "playwright.config.ts",
    ):
        assert f"`{f}`" in out, f"missing file {f} from web manifest"
    # Path-prefixed
    assert "`src/app/layout.tsx`" in out
    assert "`src/app/globals.css`" in out


def test_web_jsx_extras_surface_pascalcase_components(web_profile):
    """Web-specific extras: `<ThemeProvider>` and `<Toaster />` must
    appear as a Required Components section. This is the JSX-specific
    bit that lives in WebProjectType, not in core."""
    out = _extract_implementation_manifest(FAILING_SCOPE)
    assert "Required components" in out
    assert "`<ThemeProvider>`" in out
    assert "`<Toaster>`" in out


def test_web_jsx_lowercase_html_tags_skipped(web_profile):
    """`<div>`, `<header>`, `<footer>` are HTML — not user components.
    The extras extractor (web profile) requires PascalCase initial."""
    scope = "Wrap content in <div> and <header> alongside <CustomThing>."
    out = _extract_implementation_manifest(scope)
    assert "`<CustomThing>`" in out
    assert "`<div>`" not in out
    assert "`<header>`" not in out


def test_web_section_ordering(web_profile):
    """Packages → Files → Components — matches the agent's natural
    workflow (install deps, write files, mount components)."""
    out = _extract_implementation_manifest(FAILING_SCOPE)
    pkg_idx = out.find("Required packages")
    file_idx = out.find("Required files")
    cmp_idx = out.find("Required components")
    assert 0 < pkg_idx < file_idx < cmp_idx


def test_web_test_paths_still_excluded(web_profile):
    """Even with .ts in the web extension list, test paths must be
    excluded from Required Files (covered by Required Tests section)."""
    scope = (
        "Mount src/components/foo.tsx and create tests/e2e/smoke.spec.ts."
    )
    out = _extract_implementation_manifest(scope)
    assert "`src/components/foo.tsx`" in out
    assert "spec.ts" not in out
    assert "smoke" not in out


def test_web_framework_name_rejected_universally(web_profile):
    """`Next.js` is rejected even though `js` is in the web extension
    list — the framework-name heuristic is universal."""
    scope = "Built on Next.js with Tailwind 4. Edit foo-bar.js to wire it."
    out = _extract_implementation_manifest(scope)
    assert "Next.js" not in out
    # Real source file (kebab basename) survives
    assert "`foo-bar.js`" in out


def test_web_default_extras_empty_when_no_jsx(web_profile):
    """Web profile only emits the components section if there ARE
    PascalCase JSX tags in scope. A scope with no components → no
    extras section."""
    scope = "install foo/bar. Edit config.json. No JSX needed."
    out = _extract_implementation_manifest(scope)
    assert "Required packages" in out
    assert "Required files" in out
    assert "Required components" not in out
