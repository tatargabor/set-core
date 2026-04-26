"""Unit tests for `_extract_implementation_manifest`.

Why this exists: planner scopes are dense paragraphs (600+ chars) that mix
NPM installs, file mounts, and JSX wrap directives. Agents have been seen
cherry-picking items they grasp and silently dropping the rest from
`tasks.md` (e.g. mounting `site-header.tsx` while skipping the `next-themes`
install). This extractor surfaces every directive as a bulleted checklist
in `input.md` so the agent has nowhere to hide them.

These tests pin the contract on real failure-mode scopes (the
`test-and-layout-foundation` scope from `micro-web-run-20260426-1127`).
"""

from __future__ import annotations

from set_orch.dispatcher import _extract_implementation_manifest

# Verbatim scope from the run that failed to install next-themes/sonner
# and skipped theme-provider.tsx mounting.
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
    "<Toaster />. Header is sticky border-b with 'Micro Web' title."
)


def test_packages_extracted_from_slash_separated_install_clause():
    out = _extract_implementation_manifest(FAILING_SCOPE)
    # The four shells the failing run silently dropped MUST be flagged.
    assert "`next-themes`" in out
    assert "`sonner`" in out
    assert "`react-hook-form`" in out
    assert "`zod`" in out
    # @scoped packages must stay intact (not split into "@playwright" + "test")
    assert "`@playwright/test`" in out
    # Common deps from the same install clause
    assert "`next`" in out
    assert "`react`" in out
    assert "`tailwind`" in out


def test_files_extracted_with_extensions():
    out = _extract_implementation_manifest(FAILING_SCOPE)
    # Shell files the agent skipped
    assert "`theme-provider.tsx`" in out
    assert "`mobile-nav.tsx`" in out
    assert "`site-header.tsx`" in out
    assert "`site-footer.tsx`" in out
    # Config files explicitly mentioned in scope
    assert "`vitest.config.ts`" in out
    assert "`playwright.config.ts`" in out
    # Path-prefixed files
    assert "`src/app/layout.tsx`" in out
    assert "`src/app/globals.css`" in out


def test_test_paths_excluded_from_files():
    """Test paths are covered by the Required Tests section. Don't double-list."""
    scope = (
        "Mount v0-export/components/foo.tsx and create tests/e2e/smoke.spec.ts "
        "and src/lib/util.ts."
    )
    out = _extract_implementation_manifest(scope)
    assert "`src/lib/util.ts`" in out
    assert "tests/e2e/smoke.spec.ts" not in out
    assert "smoke.spec.ts" not in out


def test_jsx_components_extracted():
    out = _extract_implementation_manifest(FAILING_SCOPE)
    assert "`<ThemeProvider>`" in out
    assert "`<Toaster>`" in out


def test_lowercase_html_tags_not_extracted():
    """`<div>`, `<header>`, `<footer>` etc. are HTML — not user components."""
    scope = "Wrap content in <div> and <header> and <CustomComponent>."
    out = _extract_implementation_manifest(scope)
    assert "`<CustomComponent>`" in out
    assert "`<div>`" not in out
    assert "`<header>`" not in out


def test_directive_text_present():
    """Manifest must include the imperative directive — agents skim section
    headers and the first bullet, so the directive must lead."""
    out = _extract_implementation_manifest(FAILING_SCOPE)
    assert "Implementation Manifest" in out
    assert "tasks.md" in out  # Tells agent where to enumerate
    assert "diff" in out  # Tells agent the verification surface
    # Tells agent to NOT silently drop, and what to do instead
    assert "proposal.md" in out
    assert "drop" in out.lower() or "skip" in out.lower() or "correct" in out.lower()
    # Promises a review/gate flag — must NOT overpromise blocking failure
    # since the review is currently SUGGESTION-level for this category.
    assert "flag" in out.lower()


def test_empty_scope_returns_empty():
    assert _extract_implementation_manifest("") == ""
    # A purely descriptive paragraph with no installs/files/components yields
    # nothing actionable.
    assert _extract_implementation_manifest(
        "This change adds a small refactor to internal logic."
    ) == ""


def test_stopwords_filtered_from_packages():
    """Common english words after 'install' (e.g. 'install and configure ...')
    must not be promoted to package names."""
    scope = "Run npm install and verify, then create foo.tsx."
    out = _extract_implementation_manifest(scope)
    assert "`and`" not in out
    assert "`verify`" not in out


def test_section_ordering_stable():
    """Packages → Files → Components — matches the agent's natural workflow
    (install deps, write files, mount components). Don't reorder."""
    out = _extract_implementation_manifest(FAILING_SCOPE)
    pkg_idx = out.find("Required NPM packages")
    file_idx = out.find("Required files")
    mount_idx = out.find("Required components")
    assert 0 < pkg_idx < file_idx < mount_idx


def test_idempotent_no_duplicates():
    """If the scope mentions `next-themes` twice, list it once."""
    scope = (
        "install next-themes/sonner. Then install next-themes/react. "
        "Mount theme-provider.tsx and theme-provider.tsx."
    )
    out = _extract_implementation_manifest(scope)
    assert out.count("`next-themes`") == 1
    assert out.count("`theme-provider.tsx`") == 1


def test_framework_names_not_extracted_as_files():
    """`Next.js`, `Node.js`, `React.ts` are framework references — never
    actual source filenames. Rejecting them prevents the manifest from
    listing impossible-to-create files (which would confuse the agent or
    block review)."""
    scope = (
        "Built on Next.js with Node.js backend and React.ts types. "
        "Configure tailwind.config.js to add custom colors."
    )
    out = _extract_implementation_manifest(scope)
    assert "Next.js" not in out
    assert "Node.js" not in out
    assert "React.ts" not in out
    # tailwind.config.js IS a real file (kebab-style stem) — must still appear
    assert "`tailwind.config.js`" in out


def test_package_json_not_clipped_to_package_js():
    """The alternation `tsx|ts|json|js|...` had `js` matching first, so
    `package.json` was captured as `package.js`. Longer extensions must
    win the alternation."""
    scope = "Edit package.json to add the new script."
    out = _extract_implementation_manifest(scope)
    assert "`package.json`" in out
    assert "`package.js`" not in out
