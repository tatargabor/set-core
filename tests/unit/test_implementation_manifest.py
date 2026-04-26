"""Unit tests for `_extract_implementation_manifest` — core (project-agnostic).

The extractor is project-agnostic at the core: it consumes
`profile.scope_manifest_extensions()` (file extension list) and
`profile.scope_manifest_extras(scope)` (project-type-specific section)
from the active profile. These tests pin the universal behavior with the
default profile (CoreProfile) — extensions = `json/yaml/yml/md/toml`,
no JSX extras.

Project-specific behavior (TSX/JSX files for web, .py files for python,
JSX `<Component>` extras) is tested in each module's own tests:
- `modules/web/tests/test_scope_manifest_web.py`
"""

from __future__ import annotations

from set_orch.dispatcher import _extract_implementation_manifest


def test_install_clause_extracts_packages_universal():
    """The `install <list>` pattern is universal across npm/pip/cargo/etc.
    Even with the default profile (no source-language extensions), the
    package extraction works."""
    scope = "Run pip install requests/click/pydantic to add the CLI tools."
    out = _extract_implementation_manifest(scope)
    assert "## Implementation Manifest" in out
    assert "### Required packages" in out
    assert "`requests`" in out
    assert "`click`" in out
    assert "`pydantic`" in out
    # Whitespace stops the capture — narrative after the package list
    # must NOT be promoted to a package
    assert "`to`" not in out
    assert "`add`" not in out


def test_scoped_packages_preserved_universal():
    """`@types/node`-style scoped packages must stay intact across all
    project types — the slash-rejoin logic is in core."""
    scope = "install @org/lib/@types/node, plus other-pkg."
    out = _extract_implementation_manifest(scope)
    assert "`@org/lib`" in out
    assert "`@types/node`" in out


def test_config_files_extracted_with_default_profile():
    """Default profile (no project type) extracts config files only:
    json, yaml, yml, md, toml. Source files are skipped because the
    default extension list doesn't include them."""
    scope = (
        "Edit package.json and pyproject.toml. Update README.md "
        "and ci.yaml. Also touch src/main.py for the entrypoint."
    )
    out = _extract_implementation_manifest(scope)
    assert "`package.json`" in out
    assert "`pyproject.toml`" in out
    assert "`README.md`" in out
    assert "`ci.yaml`" in out
    # main.py is NOT in the default extension list — would appear if a
    # python profile registered .py
    assert "`src/main.py`" not in out


def test_package_json_alternation_order():
    """`json` must be matched before `js` so `package.json` survives
    intact rather than getting clipped to `package.js`. Profile-supplied
    extension lists must put longer extensions first; the default core
    list does."""
    scope = "Edit package.json to add scripts."
    out = _extract_implementation_manifest(scope)
    assert "`package.json`" in out
    assert "`package.js`" not in out


def test_framework_names_rejected_universal():
    """`Next.js`, `Node.js`, `Vue.ts`, `React.js` — single capitalized
    word + short extension — are framework references, not source files.
    The reject heuristic is project-agnostic and triggers on basename
    shape regardless of which extensions the profile registered."""
    scope = (
        "Built on Next.js with Node.js backend. Edit Vue.ts to add "
        "the route. Update kebab-name.json with new config."
    )
    out = _extract_implementation_manifest(scope)
    # Framework names rejected
    assert "Next.js" not in out
    assert "Node.js" not in out
    assert "Vue.ts" not in out
    # But real config file with kebab basename survives
    assert "`kebab-name.json`" in out


def test_test_paths_excluded():
    """Test files are covered by the Required Tests section — never
    duplicate them in the manifest."""
    scope = "Edit src.json and tests/e2e/foo.spec.ts and a.test.ts."
    out = _extract_implementation_manifest(scope)
    assert "`src.json`" in out
    assert "spec.ts" not in out
    assert "test.ts" not in out


def test_directive_text_present():
    """Manifest must include the imperative directive — agents skim
    section headers and the first bullet, so the directive must lead.
    Wording must be honest: "flag", not "fail review"."""
    scope = "install foo/bar. Edit config.json."
    out = _extract_implementation_manifest(scope)
    assert "Implementation Manifest" in out
    assert "tasks.md" in out
    assert "diff" in out
    assert "proposal.md" in out  # Tells agent how to handle waivers
    assert "flag" in out.lower()  # Honest claim, not "fail"
    assert "fail" not in out.lower()  # No overpromising


def test_empty_scope_returns_empty():
    assert _extract_implementation_manifest("") == ""


def test_purely_descriptive_scope_yields_nothing():
    """Scope with no install / file / extras directives should produce
    no manifest — don't render an empty section."""
    out = _extract_implementation_manifest(
        "This change refactors internal logic to improve clarity."
    )
    assert out == ""


def test_stopwords_filtered_from_packages():
    """Common English words ('and', 'with', 'for') must not promote to
    package names. The whitespace-stop in the regex keeps narrative out
    of the capture in the first place; stopwords are the second line of
    defense for short words that end up in the captured chunk."""
    # When narrative immediately follows `install`, the whitespace-stop
    # captures only the next word — which may be a stopword.
    scope = "install and configure foo/bar later in setup."
    out = _extract_implementation_manifest(scope)
    # `and` is captured by the regex but filtered as a stopword
    assert "`and`" not in out
    # `foo`/`bar` are NOT directly after `install` so they don't get
    # extracted — this is correct conservative behavior.
    assert "`foo`" not in out
    assert "`bar`" not in out


def test_idempotent_no_duplicates():
    scope = "install foo/bar. Then install foo/baz."
    out = _extract_implementation_manifest(scope)
    assert out.count("`foo`") == 1
    assert out.count("`bar`") == 1
    assert out.count("`baz`") == 1


def test_no_jsx_extras_with_default_profile():
    """Default profile has no `scope_manifest_extras` — JSX components
    are NOT extracted unless a project-type profile (e.g. WebProjectType)
    contributes them. This is the project-independence guarantee."""
    scope = (
        "Wrap children in <ThemeProvider> and add <Toaster /> to the layout."
    )
    out = _extract_implementation_manifest(scope)
    # Default profile doesn't contribute JSX extras → no JSX section
    assert "ThemeProvider" not in out
    assert "Toaster" not in out
    assert "Required components" not in out


def test_negated_files_excluded():
    """Scopes routinely write `NO page.tsx, NO layout.tsx, NO header/footer`
    to mark exclusions. The manifest MUST NOT promote these to required
    files — that would lead the agent to create files the planner
    explicitly forbade. Witnessed in foundation-shadcn-theme-shell scope:
    `NO page.tsx, NO layout.tsx, NO header/footer, NO contact-dialog,
    NO tests`."""
    scope = (
        "Configure components.json. NO page.tsx, NO layout.tsx, "
        "NO header.tsx — those come later. But DO create utils.json."
    )
    out = _extract_implementation_manifest(scope)
    assert "`components.json`" in out
    assert "`utils.json`" in out
    # Negated files MUST be filtered
    assert "page.tsx" not in out  # Filtered (default profile has no .tsx anyway)
    assert "layout.tsx" not in out
    assert "header.tsx" not in out


def test_add_dependencies_pattern_extracts_packages():
    """Planners use multiple phrasings: `install X`, `Add npm dependencies:
    X, Y, Z`, `Install packages: A, B`. The extractor must handle the
    common variants — otherwise scope clauses that explicitly enumerate
    deps via the `Add ... dependencies:` form are silently dropped.
    Witnessed in foundation-shadcn-theme-shell: only `primitives` got
    extracted because `Add npm dependencies: next-themes, sonner, ...`
    didn't match the install-only regex."""
    scope = (
        "Add npm dependencies: next-themes, sonner, "
        "class-variance-authority, clsx, tailwind-merge, lucide-react."
    )
    out = _extract_implementation_manifest(scope)
    for pkg in (
        "next-themes", "sonner", "class-variance-authority",
        "clsx", "tailwind-merge", "lucide-react",
    ):
        assert f"`{pkg}`" in out, f"missing dependency {pkg}"


def test_install_packages_colon_pattern():
    """Variant: `Install packages: foo, bar, baz`."""
    scope = "Install packages: alpha, beta, gamma."
    out = _extract_implementation_manifest(scope)
    for pkg in ("alpha", "beta", "gamma"):
        assert f"`{pkg}`" in out
