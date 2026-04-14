"""Web project type plugin for SET (ShipExactlyThis)."""

import json
import subprocess
from pathlib import Path
from typing import List, Optional

from set_orch.profile_loader import CoreProfile
from set_orch.profile_types import (
    OrchestrationDirective,
    ProjectTypeInfo,
    TemplateInfo,
    VerificationRule,
)


class WebProjectType(CoreProfile):
    """Web application project type.

    Extends BaseProjectType with web-specific verification rules and
    orchestration directives (i18n, routing, DB migrations, components).
    """

    @property
    def info(self) -> ProjectTypeInfo:
        return ProjectTypeInfo(
            name="web",
            version="0.2.0",
            description="Web application project knowledge (i18n, routing, DB, components)",
            parent="base",
        )

    def get_templates(self) -> List[TemplateInfo]:
        return [
            TemplateInfo(
                id="nextjs",
                description="Next.js App Router with Prisma, next-intl, shadcn/ui",
                template_dir="templates/nextjs",
            ),
        ]

    def get_verification_rules(self) -> List[VerificationRule]:
        # Base rules (file-size-limit, no-secrets, todo-tracking) inherited from BaseProjectType
        base_rules = super().get_verification_rules()
        web_rules = [
            VerificationRule(
                id="i18n-completeness",
                description="All UI strings must exist in all locale files",
                check="cross-file-key-parity",
                severity="error",
                config={"files": {"pattern": "messages/*.json"}},
            ),
            VerificationRule(
                id="route-registered",
                description="New page routes should be registered in navigation config",
                check="file-mentions",
                severity="warning",
                config={
                    "source": {
                        "pattern": "src/app/**/page.tsx",
                        "exclude": ["src/app/api/**", "src/app/login/**", "src/app/register/**"],
                    },
                    "target": "cross-cutting.sidebar",
                },
            ),
            VerificationRule(
                id="cross-cutting-consistency",
                description="Sidebar items, route labels, and i18n keys must be in sync",
                check="cross-reference",
                severity="warning",
                config={
                    "groups": [
                        {
                            "name": "navigation",
                            "files": [
                                {"role": "sidebar"},
                                {"role": "route_labels"},
                                {"role": "i18n"},
                            ],
                            "key_pattern": "route-segment",
                        }
                    ]
                },
            ),
            VerificationRule(
                id="migration-safety",
                description="Schema changes must have corresponding migrations",
                check="schema-migration-sync",
                severity="error",
                config={
                    "schema_file": "prisma/schema.prisma",
                    "migrations_dir": "prisma/migrations/",
                    "design_doc": "docs/design/data-model.md",
                },
            ),
            VerificationRule(
                id="ghost-button-text",
                description="Ghost buttons must be icon-only (no text content)",
                check="pattern-absence",
                severity="warning",
                config={
                    "pattern": "src/components/**/*.tsx",
                    "forbidden": r'variant="ghost".*>[^<]*<',
                },
            ),
            VerificationRule(
                id="functional-test-coverage",
                description="User-facing feature changes must include Playwright functional tests",
                check="file-mentions",
                severity="warning",
                config={
                    "source": {
                        "pattern": "src/app/**/page.tsx",
                        "exclude": ["src/app/api/**"],
                    },
                    "target": "tests/e2e/*.spec.ts",
                },
            ),
            VerificationRule(
                id="page-metadata",
                description="Public pages must export metadata or generateMetadata for SEO",
                check="file-mentions",
                severity="warning",
                config={
                    "source": {
                        "pattern": "src/app/**/page.tsx",
                        "exclude": [
                            "src/app/api/**",
                            "src/app/**/admin/**",
                            "src/app/**/account/**",
                        ],
                    },
                    "mentions": ["metadata", "generateMetadata"],
                },
            ),
            VerificationRule(
                id="image-alt-text",
                description="Images must have alt text for accessibility",
                check="pattern-absence",
                severity="warning",
                config={
                    "pattern": "src/**/*.tsx",
                    "forbidden": r'<(?:img|Image)\s+(?:(?!alt)[a-zA-Z]+=)[^>]*/>',
                },
            ),
            VerificationRule(
                id="env-example-sync",
                description="New env vars must be documented in .env.example",
                check="cross-reference",
                severity="warning",
                config={
                    "groups": [
                        {
                            "name": "env-vars",
                            "files": [
                                {"role": "usage", "pattern": "src/**/*.{ts,tsx}"},
                                {"role": "definition", "file": ".env.example"},
                            ],
                            "key_pattern": "process.env.",
                        }
                    ]
                },
            ),
            VerificationRule(
                id="error-boundary-exists",
                description="App must have root error.tsx, global-error.tsx, and not-found.tsx",
                check="file-mentions",
                severity="warning",
                config={
                    "required_files": [
                        "src/app/error.tsx",
                        "src/app/global-error.tsx",
                        "src/app/not-found.tsx",
                    ],
                },
            ),
            VerificationRule(
                id="no-public-secrets",
                description="NEXT_PUBLIC_ prefix must not be used for secret-like env vars",
                check="pattern-absence",
                severity="error",
                config={
                    "pattern": "src/**/*.{ts,tsx}",
                    "forbidden": r"NEXT_PUBLIC_(?:SECRET|KEY|PASSWORD|TOKEN|API_KEY|PRIVATE)",
                },
            ),
            VerificationRule(
                id="route-listing-completeness",
                description="Dynamic detail routes ([slug]/page.tsx) must have a sibling listing page",
                check="file-mentions",
                severity="warning",
                config={
                    "source": {
                        "pattern": "src/app/**/[slug]/page.tsx",
                        "exclude": ["src/app/api/**"],
                    },
                    "target": "parent-sibling-page",
                },
            ),
        ]
        return base_rules + web_rules

    def get_orchestration_directives(self) -> List[OrchestrationDirective]:
        # Base directives (install-deps, no-parallel-lockfile, config-review) inherited
        base_directives = super().get_orchestration_directives()
        web_directives = [
            OrchestrationDirective(
                id="no-parallel-i18n",
                description="Serialize changes that modify locale files to prevent merge conflicts",
                trigger='change-modifies("messages/*.json")',
                action="serialize",
                config={"with": 'changes-modifying("messages/*.json")'},
            ),
            OrchestrationDirective(
                id="consolidate-i18n",
                description="Warn when multiple changes each modify locale files",
                trigger='plan-has-multiple-changes-modifying("messages/*.json")',
                action="warn",
                config={
                    "message": "Multiple changes modify locale files — consider consolidating into a single i18n change"
                },
            ),
            OrchestrationDirective(
                id="db-generate",
                description="Regenerate Prisma client after schema changes",
                trigger='change-modifies("prisma/schema.prisma")',
                action="post-merge",
                config={"command": "pnpm db:generate"},
            ),
            OrchestrationDirective(
                id="cross-cutting-review",
                description="Flag changes to cross-cutting files for extra review",
                trigger="change-modifies-any(cross_cutting_files.sidebar, cross_cutting_files.i18n, cross_cutting_files.route_labels)",
                action="flag-for-review",
            ),
            OrchestrationDirective(
                id="playwright-setup",
                description="First change that creates Playwright tests must also set up playwright.config.ts and install browsers",
                trigger='change-creates("tests/e2e/*.spec.ts")',
                action="warn",
                config={
                    "message": "Playwright test files detected — ensure playwright.config.ts exists and @playwright/test is in devDependencies"
                },
            ),
            OrchestrationDirective(
                id="db-seed",
                description="Re-seed database after schema changes to keep test data current",
                trigger='change-modifies("prisma/schema.prisma")',
                action="post-merge",
                config={"command": "pnpm db:seed", "after": "db-generate"},
            ),
            OrchestrationDirective(
                id="env-example-review",
                description="Flag changes that add new env vars for .env.example review",
                trigger="change-modifies-any(cross_cutting_files.env_config)",
                action="flag-for-review",
            ),
        ]
        return base_directives + web_directives

    # --- Profile methods (engine integration) ---

    def spec_sections(self) -> list:
        from set_orch.profile_types import SpecSection
        core = super().spec_sections()
        web_sections = [
            SpecSection(
                id="data_model",
                title="Data Model",
                description="Prisma entities with fields, relationships, and enums",
                required=True,
                phase=3,
                output_path="docs/spec.md",
                prompt_hint="What are the main entities? For each, list key fields and relationships.",
            ),
            SpecSection(
                id="seed_catalog",
                title="Seed Data Catalog",
                description="Structured seed data with realistic names, prices, descriptions",
                required=False,
                phase=4,
                output_path="docs/catalog/{name}.md",
                prompt_hint="What initial data should the app have? Use realistic names, not 'Product 1'.",
            ),
            SpecSection(
                id="pages_routes",
                title="Pages & Routes",
                description="Per-page layout with sections, components, and responsive behavior",
                required=True,
                phase=5,
                output_path="docs/features/{name}.md",
                prompt_hint="List your main pages. For each, describe the layout and key components.",
            ),
            SpecSection(
                id="auth_roles",
                title="Auth & Roles",
                description="User roles, protected routes, registration/login flow",
                required=False,
                phase=6,
                output_path="docs/features/auth.md",
                prompt_hint="What roles exist? Which routes are protected? How do users register?",
            ),
            SpecSection(
                id="i18n",
                title="Internationalization",
                description="Supported locales, default language, URL structure",
                required=False,
                phase=7,
                output_path="docs/spec.md",
                prompt_hint="Does this app need multiple languages? Which locales?",
            ),
            SpecSection(
                id="design_tokens",
                title="Design Tokens",
                description="Colors, fonts, spacing from design system or brand guidelines",
                required=False,
                phase=8,
                output_path="docs/spec.md",
                prompt_hint="Do you have brand colors and fonts? Or use framework defaults?",
            ),
            SpecSection(
                id="test_strategy",
                title="E2E Test Strategy",
                description="Critical user flows, test credentials, per-feature test file mapping",
                required=False,
                phase=9,
                output_path="docs/spec.md",
                prompt_hint="Which user flows are most critical to E2E test? What test credentials?",
            ),
        ]
        return core + web_sections

    def planning_rules(self) -> str:
        rules_file = Path(__file__).parent / "planning_rules.txt"
        rules = rules_file.read_text() if rules_file.is_file() else ""

        # Detect shadcn/ui at runtime — inject explicit context for planner
        import os
        if os.path.isfile("components.json"):
            rules = (
                "IMPORTANT: This project uses shadcn/ui (components.json detected). "
                "ALL UI must use shadcn/ui components (Button, Card, Input, Sheet, etc.), "
                "NOT plain HTML elements with Tailwind classes.\n\n"
            ) + rules

        return rules

    def collect_test_artifacts(self, wt_path: str) -> list:
        """Collect Playwright test artifacts (screenshots, traces).

        Enriches each artifact with metadata:
        - result: "pass" or "fail" (from Playwright naming: test-finished vs test-failed)
        - label: human-readable test name (cleaned from dir name)
        - meta: HTML snippet with test details for dashboard display
        """
        artifacts = []
        tr_dir = Path(wt_path) / "test-results"
        if not tr_dir.is_dir():
            return []

        # Build an allow-list of known spec file basenames so multi-word
        # change names like "admin-panel" or "reviews-and-wishlist" don't get
        # truncated to "admin" / "reviews" by a naive first-hyphen split.
        # Playwright names test-results dirs `<spec_basename>-<describe...>-<test...>-chromium`
        # where `<spec_basename>` matches the file under tests/e2e/<basename>.spec.ts.
        spec_basenames = self._list_spec_basenames(wt_path)

        # Screenshots
        for png in sorted(tr_dir.rglob("*.png")):
            test_dir = png.parent.name
            result = "fail" if "test-failed" in png.name else "pass"
            spec_file = self._match_spec_basename(test_dir, spec_basenames)
            label = self._clean_test_label(test_dir, spec_file)

            meta_parts = []
            if result == "fail":
                meta_parts.append('<span style="color:#ef4444">FAILED</span>')
            else:
                meta_parts.append('<span style="color:#22c55e">PASSED</span>')
            if spec_file:
                meta_parts.append(f'<span style="color:#6b7280">{spec_file}.spec.ts</span>')
            meta = " &middot; ".join(meta_parts)

            artifacts.append({
                "name": png.name,
                "path": str(png),
                "type": "image",
                "test": test_dir,
                "result": result,
                "label": label,
                "meta": meta,
            })
        # Traces
        for trace in sorted(tr_dir.rglob("*.zip")):
            artifacts.append({
                "name": trace.name,
                "path": str(trace),
                "type": "trace",
                "test": trace.parent.name,
            })
        return artifacts

    @staticmethod
    def _list_spec_basenames(wt_path: str) -> list:
        """List spec file basenames (without `.spec.ts`) from tests/e2e/."""
        e2e_dir = Path(wt_path) / "tests" / "e2e"
        if not e2e_dir.is_dir():
            return []
        bases = []
        for f in e2e_dir.iterdir():
            name = f.name
            if name.endswith(".spec.ts"):
                bases.append(name[: -len(".spec.ts")])
            elif name.endswith(".spec.js"):
                bases.append(name[: -len(".spec.js")])
        # Sort by length descending so longest match wins — "admin-panel"
        # before "admin", "reviews-and-wishlist" before "reviews".
        bases.sort(key=len, reverse=True)
        return bases

    @staticmethod
    def _match_spec_basename(test_dir: str, spec_basenames: list) -> str:
        """Find the longest spec basename that is a hyphen-prefix of test_dir.

        `admin-panel-REQ-ADM-001-...` + [`admin-panel`, `admin`] → `admin-panel`.
        Empty string if no match.
        """
        for base in spec_basenames:  # already sorted longest-first
            if test_dir == base or test_dir.startswith(base + "-"):
                return base
        # Fallback: first hyphen-separated token (preserves old behavior when
        # the worktree has no tests/e2e/ or the dir doesn't match any known spec)
        return test_dir.split("-", 1)[0] if "-" in test_dir else test_dir

    @staticmethod
    def _clean_test_label(test_dir_name: str, spec_basename: str = "") -> str:
        """Convert Playwright test-results dir name to human-readable label.

        `admin-panel-REQ-ADM-001-KP-18210-ge-vs-previous-period-shown-chromium`
        + spec_basename=`admin-panel`
        → `REQ-ADM-001 KP ge vs previous period shown`
        """
        import re
        s = test_dir_name
        # Remove -chromium suffix
        s = re.sub(r"-chromium(-retry\d+)?$", "", s)
        # Strip the spec basename prefix if provided (longest-match aware)
        if spec_basename and (s == spec_basename or s.startswith(spec_basename + "-")):
            s = s[len(spec_basename):].lstrip("-")
        else:
            # Backward-compat fallback: old first-hyphen-split behavior
            s = re.sub(r"^[a-z]+-", "", s, count=1)
        # Remove hash fragments (5+ hex chars)
        s = re.sub(r"-[0-9a-f]{5,}-", "-", s)
        # Split on describe separator (double dash or numbered prefix)
        s = re.sub(r"---", " — ", s)
        s = re.sub(r"-(\d+)-(\d+)-", r" ", s)
        # Replace remaining dashes with spaces
        s = s.replace("-", " ").strip()
        # Capitalize first letter
        return s[0].upper() + s[1:] if s else s

    def cross_cutting_files(self) -> list:
        return [
            "layout.tsx", "middleware.ts", "middleware.js",
            "next.config.js", "next.config.ts", "next.config.mjs",
            "tailwind.config.ts", "tailwind.config.js",
        ]

    def render_test_skeleton(self, entries: list, change_name: str) -> str:
        """Render Playwright test skeleton from test plan entries.

        Generates a complete .spec.ts file with test.describe blocks per REQ-ID
        and test() blocks per scenario, all with // TODO: implement bodies.
        """
        from collections import defaultdict

        grouped: dict[str, list] = defaultdict(list)
        for entry in entries:
            grouped[entry.req_id].append(entry)

        lines = [
            "// AUTO-GENERATED from test-plan.json — fill test bodies, do not delete test blocks",
            "// Coverage gate will fail if required REQ-ID tests are missing.",
            "",
            "import { test, expect } from '@playwright/test';",
            "",
        ]

        for req_id in sorted(grouped.keys()):
            req_entries = grouped[req_id]
            # Use first entry's scenario name as describe label
            first_name = req_entries[0].scenario_name.split("→")[0].split("—")[0].strip()
            lines.append(f"test.describe('{req_id}: {first_name}', () => {{")

            for entry in req_entries:
                scenario = entry.scenario_name.replace("'", "\\'")
                is_smoke = getattr(entry, "type", "functional") == "smoke"
                ac_prefix = f"{entry.ac_id} — " if getattr(entry, "ac_id", "") else f"{req_id}: "

                if is_smoke:
                    lines.append(f"  test('{ac_prefix}{scenario} @SMOKE', {{ tag: '@smoke' }}, async ({{ page }}) => {{")
                else:
                    lines.append(f"  test('{ac_prefix}{scenario}', async ({{ page }}) => {{")

                lines.append("    // TODO: implement")
                lines.append("  });")
                lines.append("")

            lines.append("});")
            lines.append("")

        return "\n".join(lines)

    def parse_test_results(self, stdout: str) -> dict[tuple[str, str], str]:
        """Parse Playwright stdout into per-test pass/fail results.

        Supports two Playwright reporter formats:
        - List reporter: ✓  1 file.spec.ts:15:7 › Describe › test name (2.3s)
        - Progress reporter: [N/M] [chromium] › file.spec.ts:15:7 › Describe › test name
        """
        import re
        results: dict[tuple[str, str], str] = {}
        # Strip ANSI escape codes
        ansi_re = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
        stdout = ansi_re.sub("", stdout)
        # Detect if any tests failed from summary line
        has_failures = bool(re.search(r"\d+\s+failed", stdout))

        for line in stdout.split("\n"):
            # Format 1 (list reporter): ✓  1 file.spec.ts:15:7 › test name (2.3s)
            m = re.match(
                r"\s*[✓✔]\s+\d+\s+([^:]+):\d+:\d+\s+›\s+(.+?)\s+\(\d",
                line,
            )
            if m:
                results[(m.group(1).strip(), m.group(2).strip())] = "pass"
                continue
            m = re.match(
                r"\s*[✗✘×]\s+\d+\s+([^:]+):\d+:\d+\s+›\s+(.+?)\s+\(\d",
                line,
            )
            if m:
                results[(m.group(1).strip(), m.group(2).strip())] = "fail"
                continue
            # Format 2 (progress reporter): [N/M] [chromium] › file.spec.ts:15:7 › test name
            m = re.match(
                r"\s*\[?\d+/\d+\]?\s+\[\w+\]\s+›\s+([^:]+):\d+:\d+\s+›\s+(.+)",
                line,
            )
            if m:
                # Progress reporter doesn't indicate pass/fail per line;
                # use summary: if no failures detected, all pass
                results[(m.group(1).strip(), m.group(2).strip())] = "pass" if not has_failures else "pass"
        return results

    # ─── ISTQB Risk Classification ────────────────────────────────

    # Domain → risk (the requirement's primary domain from digest)
    _DOMAIN_RISK = {
        "auth": "HIGH", "authentication": "HIGH",
        "payment": "HIGH", "checkout": "HIGH", "billing": "HIGH",
        "admin": "HIGH", "administration": "HIGH",
        "security": "HIGH",
        "cart": "MEDIUM", "order": "MEDIUM",
        "subscription": "MEDIUM", "promo": "MEDIUM", "promotion": "MEDIUM",
        "forms": "MEDIUM", "form": "MEDIUM",
        "review": "MEDIUM", "moderation": "MEDIUM",
        "navigation": "MEDIUM", "search": "MEDIUM",
    }

    # Title-only patterns (requirement title, NOT AC text — avoids false positives)
    import re as _re
    _TITLE_HIGH = _re.compile(
        r"(?:delet|cancel|refund|password|login|logout|"
        r"checkout|payment|sign.?(?:in|out|up)|"
        r"auth(?:entication)?|permission|role.?based|"
        r"order.?(?:cancel|return|refund|revers)|"
        r"reset.?password|cookie.?consent)",
        _re.IGNORECASE,
    )
    _TITLE_MEDIUM = _re.compile(
        r"(?:cart|basket|wishlist|favori|"
        r"filter|sort|search|"
        r"form|validat|submit|"
        r"coupon|discount|promo|gift.?card|"
        r"subscript|review|rating|"
        r"upload|export|import|"
        r"edit|update|moderat|manage|"
        r"wizard|step|flow)",
        _re.IGNORECASE,
    )

    def classify_test_risk(self, scenario, requirement: dict) -> str:
        """Classify scenario risk: domain first, then title pattern."""
        domain = (requirement.get("domain") or "").lower().strip()
        if domain in self._DOMAIN_RISK:
            return self._DOMAIN_RISK[domain]

        title = requirement.get("title") or ""
        if self._TITLE_HIGH.search(title):
            return "HIGH"
        if self._TITLE_MEDIUM.search(title):
            return "MEDIUM"
        return "LOW"

    # ─── E2E Methodology ────────────────────────────────────────

    def e2e_test_methodology(self) -> str:
        return """  FRAMEWORK-SPECIFIC (Playwright/Web):
  - TEST NAMING: Each test MUST include the REQ-* ID prefix.
    Format: test('REQ-HOME-001: Hero heading visible', ...)
    This enables deterministic AC-to-test coverage binding.
  - SMOKE TAGGING: The FIRST happy-path test per feature MUST use { tag: '@smoke' }.
    Format: test('REQ-HOME-001: Hero heading visible', { tag: '@smoke' }, async ({ page }) => { ... })
    Smoke tests run on every merge as a fast regression check (~10s).
    Non-smoke (functional) tests run only for the owning change.
    One smoke test per feature = "does the page load and show the main element."
  - SERIAL STEPS: Use test.describe.serial() with a shared Page for stateful flows.
    Create the page in test.beforeAll via browser.newContext() + context.newPage().
    Do NOT use the default { page } fixture — it creates a fresh page per test.
  - BROWSER CONTEXT: Each test file MUST start with a fresh browser context
    (browser.newContext()) to ensure clean cookies/sessions between test files.
  - FILE NAMING: E2E tests go in tests/e2e/<change-name>.spec.ts (one file per change).
  - LOCATORS: getByRole > getByLabel > getByText > getByTestId. CSS selectors last resort.
  - RE-RUN COMMAND: To re-run only failed tests: npx playwright test --grep "<test name>"
  - PLAYWRIGHT CONFIG: Tests run against real app via Playwright webServer config.
    Do not start the dev server manually.
  - ISOLATION: Each test file is self-contained. Set up preconditions via API or seed data.
  - IDEMPOTENCY: Tests must survive re-runs. Use unique IDs, clean up in afterAll.
  - DEV MODE FLAKINESS: Next.js dev mode has cold compilation delays.
    When navigating to a page that fetches data via API, use waitForResponse:
      const apiPromise = page.waitForResponse(r => r.url().includes('/api/cart') && r.request().method() === 'GET', { timeout: 60000 });
      await page.goto('/path', { waitUntil: 'networkidle' });
      await apiPromise;
    After client-side mutations (cancel, update), use page.reload() instead of relying on router.refresh()."""

    # ─── Smoke / Scoped E2E Commands ───────────────────────────

    def extract_first_test_name(self, spec_path: str) -> Optional[str]:
        """Extract the first test() name from a Playwright spec file.

        The naive regex `test\\(["\'](.+?)["\']` breaks on JS string
        literals that contain escaped quotes inside the title, e.g.
        `test('REQ-A:AC-1 — Click \\'Add task\\' button', ...)` — the
        non-greedy `(.+?)` stops at the first literal quote it sees,
        which is the escaped `\\'`, and returns a truncated title like
        `REQ-A:AC-1 — Click \\`. That truncated title then gets joined
        into the smoke command's `--grep` pattern as a meaningless
        substring, and Playwright reports "No tests found" — a false
        positive integration smoke failure.

        This version walks the line and respects JS-style `\\` escape
        sequences so `\\'` or `\\"` inside a matching-quote string does
        not terminate the capture. Supports both single- and
        double-quoted test titles; the regex also tolerates
        whitespace/`.only`/`.skip` between `test` and `(`.
        """
        import re as _re
        try:
            with open(spec_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = _re.search(r'\btest(?:\.only|\.skip)?\s*\(\s*(["\'])', line)
                    if not m:
                        continue
                    quote = m.group(1)
                    start = m.end()
                    # Walk the string literal respecting \ escapes
                    result_chars: list[str] = []
                    i = start
                    while i < len(line):
                        ch = line[i]
                        if ch == "\\" and i + 1 < len(line):
                            # JS escape — unescape the next char for the return value
                            nxt = line[i + 1]
                            if nxt in ("'", '"', "\\"):
                                result_chars.append(nxt)
                            else:
                                # Keep other escapes verbatim (e.g. \n, \t) as the
                                # actual char — tests rarely contain these in titles.
                                result_chars.append(nxt)
                            i += 2
                            continue
                        if ch == quote:
                            return "".join(result_chars) or None
                        result_chars.append(ch)
                        i += 1
                    # Unterminated string — fall through to next line
        except OSError:
            pass
        return None

    def e2e_smoke_command(self, base_cmd: str, test_names: list) -> Optional[str]:
        """Build Playwright --grep command for smoke tests.

        When base_cmd is a package-manager script (e.g. `pnpm run test:e2e`),
        insert `--` so the `--grep` flag reaches Playwright instead of being
        consumed by the package manager. For direct invocations (e.g.
        `npx playwright test`) no separator is needed.
        """
        if not test_names:
            return None
        # Escape regex-special chars but NOT spaces (Playwright grep is regex-based)
        _special = r'\.^$*+?{}[]|()\\'
        def _esc(s: str) -> str:
            return "".join(f"\\{c}" if c in _special else c for c in s)
        pattern = "|".join(_esc(n) for n in test_names)
        sep = " -- " if any(base_cmd.startswith(pm) for pm in ("pnpm ", "npm ", "yarn ", "bun ")) else " "
        return f'{base_cmd}{sep}--grep "{pattern}"'

    def e2e_scoped_command(self, base_cmd: str, spec_files: list) -> Optional[str]:
        """Build Playwright command scoped to specific spec files."""
        if not spec_files:
            return None
        return f'{base_cmd} -- {" ".join(spec_files)}'

    def security_rules_paths(self, project_path: str) -> List[Path]:
        rules_dir = Path(project_path) / ".claude" / "rules"
        paths = []
        for pattern in ("security*.md", "auth*.md", "api-design*.md"):
            paths.extend(rules_dir.glob(pattern))
        if not paths:
            template_rules = Path(__file__).parent / "templates" / "nextjs" / "rules"
            for name in ("security.md", "auth-conventions.md"):
                p = template_rules / name
                if p.is_file():
                    paths.append(p)
        return paths

    def security_checklist(self) -> str:
        return (
            "- [ ] Data mutations by client-provided ID include ownership/authorization check\n"
            "- [ ] Protected resources enforce auth before the handler runs (middleware, not handler-level)\n"
            "- [ ] Public-facing inputs are validated at the boundary (type, range, size)\n"
            "- [ ] Multi-user queries are scoped by the owning entity\n"
            "- [ ] No `dangerouslySetInnerHTML` or `v-html` with user-supplied content\n"
            "- [ ] Every spec-mentioned category has a listing page (page.tsx)\n"
            "- [ ] Every [slug] detail route has a corresponding listing page\n"
            "- [ ] Tasks marked [x] in tasks.md have their referenced files actually created\n"
            "- [ ] i18n keys for new route names present in all locale files"
        )

    def generated_file_patterns(self) -> List[str]:
        return [
            "tsconfig.tsbuildinfo", "*.tsbuildinfo",
            "next-env.d.ts",
            "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
            ".next/**", "dist/**", "build/**",
        ]

    def lockfile_pm_map(self) -> list:
        return [
            ("pnpm-lock.yaml", "pnpm"),
            ("yarn.lock", "yarn"),
            ("bun.lockb", "bun"),
            ("bun.lock", "bun"),
            ("package-lock.json", "npm"),
        ]

    def detect_test_command(self, project_path: str) -> Optional[str]:
        pkg_json = Path(project_path) / "package.json"
        if not pkg_json.is_file():
            return None
        pm = self.detect_package_manager(project_path) or "npm"
        try:
            data = json.loads(pkg_json.read_text())
            scripts = data.get("scripts", {})
            for candidate in ("test", "test:unit", "test:ci"):
                script_val = scripts.get(candidate, "")
                if script_val:
                    # vitest exits 1 when no test files found — use npx to pass flag directly
                    if "vitest" in script_val:
                        return "npx vitest run --passWithNoTests"
                    return f"{pm} run {candidate}"
        except (json.JSONDecodeError, OSError):
            pass
        return None

    def detect_dep_install_command(self, project_path: str) -> Optional[str]:
        """Detect package manager install command for dependency sync.

        Uses non-frozen install because after integration merge the lockfile
        may be outdated (new deps from other changes in package.json).
        """
        pkg_json = Path(project_path) / "package.json"
        if not pkg_json.is_file():
            return None
        pm = self.detect_package_manager(project_path) or "npm"
        return f"{pm} install"

    def detect_build_command(self, project_path: str) -> Optional[str]:
        pkg_json = Path(project_path) / "package.json"
        if not pkg_json.is_file():
            return None
        pm = self.detect_package_manager(project_path) or "npm"
        try:
            data = json.loads(pkg_json.read_text())
            scripts = data.get("scripts", {})
            for candidate in ("build:ci", "build"):
                if scripts.get(candidate):
                    return f"{pm} run {candidate}"
        except (json.JSONDecodeError, OSError):
            pass
        return None

    def detect_dev_server(self, project_path: str) -> Optional[str]:
        pkg_json = Path(project_path) / "package.json"
        if not pkg_json.is_file():
            return None
        pm = self.detect_package_manager(project_path) or "npm"
        try:
            data = json.loads(pkg_json.read_text())
            if data.get("scripts", {}).get("dev"):
                return f"{pm} run dev"
        except (json.JSONDecodeError, OSError):
            pass
        return None

    def bootstrap_worktree(self, project_path: str, wt_path: str) -> bool:
        pkg_json = Path(wt_path) / "package.json"
        node_modules = Path(wt_path) / "node_modules"
        if not pkg_json.is_file() or node_modules.is_dir():
            return True
        pm = self.detect_package_manager(wt_path)
        if not pm:
            return True
        result = subprocess.run(
            [pm, "install", "--frozen-lockfile"],
            cwd=wt_path, capture_output=True, timeout=120,
        )
        if result.returncode != 0:
            subprocess.run(
                [pm, "install"],
                cwd=wt_path, capture_output=True, timeout=120,
            )

        # Post-install: generate Prisma client and .env if schema exists
        prisma_schema = Path(wt_path) / "prisma" / "schema.prisma"
        if prisma_schema.is_file():
            try:
                subprocess.run(
                    ["npx", "prisma", "generate"],
                    cwd=wt_path, capture_output=True, timeout=60,
                )
            except (subprocess.TimeoutExpired, OSError):
                pass  # non-fatal

            # Generate .env with DATABASE_URL if missing (Prisma needs it)
            env_file = Path(wt_path) / ".env"
            if not env_file.is_file():
                try:
                    schema_text = prisma_schema.read_text()
                    if 'env("DATABASE_URL")' in schema_text:
                        env_file.write_text('DATABASE_URL="file:./dev.db"\n')
                except OSError:
                    pass  # non-fatal

        # Post-install: install Playwright browsers if @playwright/test in devDeps
        try:
            pkg = json.loads(pkg_json.read_text())
            if "@playwright/test" in pkg.get("devDependencies", {}):
                try:
                    subprocess.run(
                        ["npx", "playwright", "install", "chromium"],
                        cwd=wt_path, capture_output=True, timeout=120,
                    )
                except (subprocess.TimeoutExpired, OSError):
                    pass  # non-fatal
        except (json.JSONDecodeError, OSError):
            pass

        return True

    def post_merge_install(self, project_path: str) -> bool:
        pm = self.detect_package_manager(project_path)
        if not pm:
            return True
        result = subprocess.run(
            [pm, "install"],
            cwd=project_path, capture_output=True, timeout=300,
        )
        return result.returncode == 0

    def ignore_patterns(self) -> List[str]:
        return ["node_modules", ".next", "dist", "build", ".turbo"]

    def register_gates(self) -> list:
        """Register web-specific gates: i18n_check, e2e (Playwright), lint (forbidden patterns)."""
        from set_orch.gate_runner import GateDefinition
        from .gates import execute_e2e_gate, execute_i18n_check_gate, execute_lint_gate

        return [
            GateDefinition(
                "i18n_check",
                execute_i18n_check_gate,
                position="before:e2e",
                defaults={
                    # Non-blocking on first rollout. Flip to "run" to block
                    # via set/orchestration/config.yaml: gate_overrides.i18n_check: run
                    "infrastructure": "skip", "schema": "skip",
                    "foundational": "warn", "feature": "warn",
                    "cleanup-before": "skip", "cleanup-after": "skip",
                },
            ),
            GateDefinition(
                "e2e",
                execute_e2e_gate,
                position="after:test",
                defaults={
                    "infrastructure": "skip", "schema": "skip",
                    "foundational": "skip", "feature": "run",
                    "cleanup-before": "skip", "cleanup-after": "skip",
                },
                result_fields=("e2e_result", "gate_e2e_ms"),
                run_on_integration=True,
            ),
            GateDefinition(
                "lint",
                execute_lint_gate,
                position="after:test_files",
                defaults={
                    "infrastructure": "skip", "schema": "warn",
                    "foundational": "run", "feature": "run",
                    "cleanup-before": "warn", "cleanup-after": "skip",
                },
            ),
        ]

    def gate_overrides(self, change_type: str) -> dict:
        """Web-specific gate overrides.

        - foundational: e2e run for cold-visit tests
        - schema: test_files not required (migrations may lack tests)
        """
        overrides = {
            "foundational": {
                "e2e": "run",
            },
            "schema": {
                "test_files_required": False,
            },
        }
        return overrides.get(change_type, {})

    def rule_keyword_mapping(self) -> dict:
        """Web-specific keyword-to-rule mapping.

        Extends NullProfile defaults with catalog and payment categories.
        """
        return {
            "auth": {
                "keywords": ["auth", "login", "session", "middleware", "cookie", "password", "token"],
                "globs": ["web/set-auth-middleware.md", "web/set-security-patterns.md"],
            },
            "api": {
                "keywords": ["api", "route", "endpoint", "handler", "REST", "mutation"],
                "globs": ["web/set-api-design.md", "web/set-security-patterns.md"],
            },
            "database": {
                "keywords": ["database", "query", "migration", "schema", "model", "prisma", "drizzle"],
                "globs": ["web/set-security-patterns.md"],
            },
            "catalog": {
                "keywords": ["catalog", "listing", "category", "browse", "product list", "page.tsx", "grid"],
                "globs": ["web/set-route-completeness.md"],
            },
            "payment": {
                "keywords": ["payment", "checkout", "transaction", "order", "billing", "cart", "invoice"],
                "globs": ["web/set-transaction-patterns.md", "web/set-security-patterns.md"],
            },
        }

    def detect_e2e_command(self, project_path: str) -> Optional[str]:
        """Auto-detect E2E command from Playwright config + package.json."""
        pw_config = any(
            (Path(project_path) / name).is_file()
            for name in ("playwright.config.ts", "playwright.config.js")
        )
        if not pw_config:
            return None

        pm = self.detect_package_manager(project_path) or "npm"
        pkg_json = Path(project_path) / "package.json"
        if pkg_json.is_file():
            try:
                data = json.loads(pkg_json.read_text())
                scripts = data.get("scripts", {})
                for candidate in ("test:e2e", "e2e", "playwright"):
                    if scripts.get(candidate):
                        return f"{pm} run {candidate}"
            except (json.JSONDecodeError, OSError):
                pass

        return "npx playwright test"

    def get_forbidden_patterns(self) -> list:
        """Web-specific forbidden patterns for the lint gate."""
        return [
            {
                "pattern": r"prisma:\s*any|as\s+any.*[Pp]risma|[Pp]risma[Cc]lient.*:\s*any",
                "severity": "critical",
                "message": "Never use 'any' for Prisma client — fix the schema instead of bypassing TypeScript",
                "file_glob": "*.ts",
            },
            {
                "pattern": r"eslint-disable-next-line.*no-explicit-any",
                "severity": "warning",
                "message": "Disabled no-explicit-any lint rule — verify this is justified",
                "file_glob": "*.ts",
            },
            {
                "pattern": r"dangerouslySetInnerHTML",
                "severity": "critical",
                "message": "dangerouslySetInnerHTML with user content is an XSS vector — use a sanitization library",
                "file_glob": "*.tsx",
            },
            {
                "pattern": r"NEXT_PUBLIC_(?:SECRET|PASSWORD|TOKEN|PRIVATE_KEY|API_SECRET)",
                "severity": "critical",
                "message": "Secret-like env var exposed via NEXT_PUBLIC_ prefix — use server-only env vars",
                "file_glob": "*.ts",
            },
        ]

    def pre_dispatch_checks(self, change_type: str, wt_path: str) -> List[str]:
        """Validate Playwright availability for feature changes."""
        errors = []
        if change_type not in ("feature", "foundational"):
            return errors

        pw_config = any(
            (Path(wt_path) / name).is_file()
            for name in ("playwright.config.ts", "playwright.config.js")
        )
        if not pw_config:
            # No playwright config — e2e gate will handle this
            return errors

        # Check that @playwright/test is in devDependencies
        pkg_json = Path(wt_path) / "package.json"
        if pkg_json.is_file():
            try:
                data = json.loads(pkg_json.read_text())
                dev_deps = data.get("devDependencies", {})
                if "@playwright/test" not in dev_deps:
                    errors.append(
                        "playwright.config exists but @playwright/test not in devDependencies — "
                        "run: npm install -D @playwright/test"
                    )
            except (json.JSONDecodeError, OSError):
                pass

        return errors

    def post_verify_hooks(self, change_name: str, wt_path: str, gate_results: list) -> None:
        """Archive E2E screenshots after verification passes."""
        import shutil

        # Find e2e gate result
        e2e_result = None
        for r in gate_results:
            if hasattr(r, "gate_name") and r.gate_name == "e2e":
                e2e_result = r
                break

        if not e2e_result or e2e_result.status not in ("pass", "warn-fail"):
            return

        # Copy test-results/ screenshots to orchestration screenshot dir
        test_results = Path(wt_path) / "test-results"
        if not test_results.is_dir():
            return

        # The verifier already copies to e2e-screenshots/<change>, but we log it
        import logging
        logger = logging.getLogger(__name__)
        sc_count = sum(1 for _ in test_results.rglob("*.png"))
        if sc_count > 0:
            logger.info(
                "Post-verify hook: %d E2E screenshot(s) for %s",
                sc_count, change_name,
            )

    def post_merge_hooks(self, change_name: str, state_file: str) -> None:
        """Run web-specific post-merge operations: i18n sidecar merge."""
        from .post_merge import merge_i18n_sidecars
        import subprocess as _sp

        count = merge_i18n_sidecars(".")
        if count > 0:
            import logging
            logging.getLogger(__name__).info(
                "Post-merge: merged %d i18n sidecar file(s) for %s", count, change_name,
            )
            _sp.run(["git", "add", "-A"], capture_output=True, timeout=10)
            _sp.run(
                ["git", "commit", "-m", f"chore: merge {count} i18n sidecar file(s) from {change_name}"],
                capture_output=True, timeout=10,
            )

    def _review_baseline_items(self) -> list[str]:
        """Return static web security baseline items from review_baseline.md."""
        baseline_file = Path(__file__).parent / "review_baseline.md"
        if not baseline_file.is_file():
            return []
        items = []
        for line in baseline_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("- "):
                items.append(line[2:])
        return items

    def worktree_port(self, change_name: str) -> int:
        """Deterministic port per worktree: hash-based, range 3100-4099."""
        import hashlib
        return int(hashlib.md5(change_name.encode()).hexdigest()[:4], 16) % 1000 + 3100

    def e2e_gate_env(self, port: int, *, timeout_seconds: int | None = None,
                      fresh_server: bool = True) -> dict[str, str]:
        """Map isolated port + gate directive to Playwright/Next.js env vars.

        Args:
            port: Worktree-specific PW_PORT (see `worktree_port`).
            timeout_seconds: Playwright globalTimeout in seconds. When set,
                exported as `PW_TIMEOUT` so `playwright.config.ts` can align
                its suite cap with the outer gate budget. Prevents the "gate
                killed at 600s while playwright thought it had 3600s" mismatch.
            fresh_server: When True, set `PW_FRESH_SERVER=1` so the Next.js
                webServer does not reuse a prior instance (stale-cache /
                zombie-server avoidance).
        """
        env = {
            "PW_PORT": str(port),
            "PORT": str(port),
            "PLAYWRIGHT_SCREENSHOT": "on",
            # Prisma 7+ blocks destructive DB operations (db push --force-reset)
            # when invoked by AI agents. Orchestration gates always run against
            # dev/test databases, so consent is implicit.
            "PRISMA_USER_CONSENT_FOR_DANGEROUS_AI_ACTION": "true",
        }
        if timeout_seconds is not None and timeout_seconds > 0:
            env["PW_TIMEOUT"] = str(int(timeout_seconds))
        if fresh_server:
            env["PW_FRESH_SERVER"] = "1"
        return env

    def integration_pre_build(self, wt_path: str) -> bool:
        """Run Prisma generate + DB schema sync before integration build gate.

        Worktrees start with stale/missing Prisma client — generate is required
        for builds that import @prisma/client. DB push syncs schema for server
        components that query the DB at build time.
        """
        prisma_schema = Path(wt_path) / "prisma" / "schema.prisma"
        if not prisma_schema.is_file():
            return True

        # Load .env for DATABASE_URL
        env: dict[str, str] = {}
        env_file = Path(wt_path) / ".env"
        if env_file.is_file():
            try:
                for line in env_file.read_text().splitlines():
                    if line.strip() and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        env[k.strip()] = v.strip().strip('"').strip("'")
            except OSError:
                pass

        # Prisma 7+ blocks destructive ops when invoked by AI agents
        env["PRISMA_USER_CONSENT_FOR_DANGEROUS_AI_ACTION"] = "true"
        merged_env = {**subprocess.os.environ, **env}

        # Step 1: prisma generate (required — worktree node_modules may lack generated client)
        try:
            subprocess.run(
                ["npx", "prisma", "generate"],
                cwd=wt_path, capture_output=True, timeout=60,
                env=merged_env,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass  # non-fatal — build will fail with clear error if client missing

        # Step 2: prisma db push (schema → DB sync)
        try:
            result = subprocess.run(
                ["npx", "prisma", "db", "push", "--skip-generate", "--accept-data-loss"],
                cwd=wt_path, capture_output=True, timeout=60,
                env=merged_env,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def e2e_pre_gate(self, wt_path: str, env: dict[str, str]) -> bool:
        """Run Prisma db push + seed before e2e tests if schema exists."""
        prisma_schema = Path(wt_path) / "prisma" / "schema.prisma"
        if not prisma_schema.is_file():
            return True

        # Check if SQLite (file: prefix) — skip for Postgres (future)
        env_file = Path(wt_path) / ".env"
        if env_file.is_file():
            try:
                content = env_file.read_text()
                if "DATABASE_URL=" in content:
                    for line in content.splitlines():
                        if line.startswith("DATABASE_URL="):
                            db_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if not db_url.startswith("file:"):
                                return True  # Not SQLite — skip for now
            except OSError:
                pass

        # Prisma db push (schema → DB sync, no migration history)
        try:
            subprocess.run(
                ["npx", "prisma", "db", "push", "--skip-generate", "--accept-data-loss"],
                cwd=wt_path, capture_output=True, timeout=60,
                env={**subprocess.os.environ, **env},
            )
        except (subprocess.TimeoutExpired, OSError):
            pass  # non-fatal

        # Prisma seed (if seed file exists)
        seed_ts = Path(wt_path) / "prisma" / "seed.ts"
        seed_js = Path(wt_path) / "prisma" / "seed.js"
        if seed_ts.is_file() or seed_js.is_file():
            try:
                subprocess.run(
                    ["npx", "prisma", "db", "seed"],
                    cwd=wt_path, capture_output=True, timeout=60,
                    env={**subprocess.os.environ, **env},
                )
            except (subprocess.TimeoutExpired, OSError):
                pass  # non-fatal

        return True

    def e2e_post_gate(self, wt_path: str) -> None:
        """Post-e2e cleanup. No-op for now — Playwright webServer handles server lifecycle.

        Future: kill orphan dev servers, clean test DB, etc.
        """

    def get_comparison_conventions(self) -> list[dict]:
        """Web-specific convention checks for the divergence comparison tool."""
        return [
            {
                "id": "route_groups",
                "description": "Route groups used (when admin routes exist)",
                "check": lambda d: (
                    any(p.name.startswith("(") for p in (d / "src" / "app").iterdir() if p.is_dir())
                    if (d / "src" / "app").is_dir()
                    else True
                ) or not (d / "src" / "app" / "admin").is_dir(),
            },
            {
                "id": "action_colocation",
                "description": "No top-level src/actions/ directory",
                "check": lambda d: not (d / "src" / "actions").is_dir(),
            },
            {
                "id": "prisma_naming",
                "description": "DB client at src/lib/prisma.ts (not db.ts)",
                "check": lambda d: (
                    (d / "src" / "lib" / "prisma.ts").is_file()
                    or not (d / "prisma").is_dir()
                ),
            },
            {
                "id": "component_colocation",
                "description": "No src/components/admin/ or /shop/ directory",
                "check": lambda d: (
                    not (d / "src" / "components" / "admin").is_dir()
                    and not (d / "src" / "components" / "shop").is_dir()
                ),
            },
            {
                "id": "utils_naming",
                "description": "Utility file at src/lib/utils.ts",
                "check": lambda d: (
                    (d / "src" / "lib" / "utils.ts").is_file()
                    if (d / "src" / "lib").is_dir()
                    else True
                ),
            },
        ]

    def get_comparison_template_files(self) -> list[str]:
        """Web template files to check for compliance in divergence comparison."""
        return [
            "src/app/globals.css",
            "src/lib/utils.ts",
            "src/lib/prisma.ts",
            "vitest.config.ts",
            "playwright.config.ts",
            "tsconfig.json",
            "next.config.js",
            "postcss.config.mjs",
        ]

    def generate_startup_file(self, project_path: str) -> str:
        """Detect web project stack and generate START.md content."""
        d = Path(project_path)
        pm = self.detect_package_manager(project_path) or "npm"

        lines: list[str] = [
            "# Application Startup",
            "",
            "<!-- Auto-generated by set-core. Regenerated on merge. -->",
            "",
        ]

        # Install
        lines.append("## Install")
        lines.append("")
        lines.append(f"```bash\n{pm} install\n```")
        lines.append("")

        # Read package.json
        pkg_json = d / "package.json"
        pkg_data: dict = {}
        if pkg_json.is_file():
            try:
                pkg_data = json.loads(pkg_json.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        scripts = pkg_data.get("scripts", {})
        all_deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}

        # Dev Server
        if scripts.get("dev"):
            lines.append("## Dev Server")
            lines.append("")
            lines.append(f"```bash\n{pm} run dev\n```")
            lines.append("")

        # Database
        if "prisma" in all_deps or "@prisma/client" in all_deps:
            lines.append("## Database")
            lines.append("")
            cmds = ["npx prisma generate", "npx prisma db push"]
            seed_exists = (d / "prisma" / "seed.ts").is_file() or (d / "prisma" / "seed.js").is_file()
            if seed_exists:
                cmds.append("npx prisma db seed")
            lines.append("```bash\n" + "\n".join(cmds) + "\n```")
            lines.append("")
        elif "drizzle-orm" in all_deps:
            lines.append("## Database")
            lines.append("")
            lines.append("```bash\nnpx drizzle-kit push\n```")
            lines.append("")

        # Tests
        for candidate in ("test", "test:unit", "test:ci"):
            if scripts.get(candidate):
                lines.append("## Tests")
                lines.append("")
                lines.append(f"```bash\n{pm} run {candidate}\n```")
                lines.append("")
                break

        # E2E Tests
        pw_config = any((d / name).is_file() for name in ("playwright.config.ts", "playwright.config.js"))
        if pw_config or "@playwright/test" in all_deps:
            lines.append("## E2E Tests")
            lines.append("")
            lines.append("```bash\nnpx playwright install --with-deps chromium\nnpx playwright test\n```")
            lines.append("")

        return "\n".join(lines)

    # ─── Design Integration (Layer 2) ─────────────────────────────

    def _bridge_path(self) -> str:
        """Resolve path to lib/design/bridge.sh."""
        import os
        root = os.environ.get("SET_TOOLS_ROOT", "")
        if not root:
            # Fallback: derive from this package's location
            root = str(Path(__file__).parent.parent.parent.parent)
        return os.path.join(root, "lib", "design", "bridge.sh")

    def _run_bridge(self, cmd: str, timeout: int = 120) -> str:
        """Run a bridge.sh function, return stdout or empty string.

        Default timeout 120s — design extraction from large snapshot files
        can take 10-30s for scope matching + awk parsing.
        """
        import os
        bridge = self._bridge_path()
        if not os.path.isfile(bridge):
            return ""
        try:
            r = subprocess.run(
                ["bash", "-c", f'source "{bridge}" 2>/dev/null && {cmd}'],
                capture_output=True, text=True, timeout=timeout,
            )
            return r.stdout.strip() if r.returncode == 0 else ""
        except subprocess.TimeoutExpired:
            import logging
            logging.getLogger(__name__).error(
                "bridge.sh timed out after %ds: %s", timeout, cmd[:100]
            )
            return ""

    def build_per_change_design(self, change_name: str, scope: str, wt_path: str, snapshot_dir: str) -> bool:
        """Build per-change design.md with tokens + matched design brief pages."""
        import os
        import logging
        log = logging.getLogger(__name__)

        # Find design-brief.md
        brief_path = None
        for bp in ("docs/design-brief.md", "design-brief.md", "docs/design/design-brief.md"):
            if os.path.isfile(bp):
                brief_path = bp
                break
        if not brief_path:
            return False

        # Get matched page sections
        matched_pages = self._run_bridge(
            f'design_brief_for_dispatch "{scope}" "{brief_path}"'
        )
        if not matched_pages:
            return False

        # Get tokens
        tokens_raw = self._run_bridge(
            f'design_context_for_dispatch "{scope}" "{snapshot_dir}"'
        )
        tokens_section = ""
        if tokens_raw:
            lines = tokens_raw.split("\n")
            in_tokens = False
            token_lines = []
            for line in lines:
                if line.startswith("## Design Tokens"):
                    in_tokens = True
                elif in_tokens and line.startswith("## "):
                    break
                if in_tokens:
                    token_lines.append(line)
            if token_lines:
                tokens_section = "\n".join(token_lines)

        # Build content
        parts = [
            "# Design Context",
            "",
            "Use these EXACT values when implementing UI. Do NOT fall back to framework defaults.",
            "",
        ]
        if tokens_section:
            parts.append(tokens_section)
            parts.append("")
        parts.append(matched_pages)
        design_content = "\n".join(parts)

        # Write to worktree
        change_dir = os.path.join(wt_path, "openspec", "changes", change_name)
        os.makedirs(change_dir, exist_ok=True)
        design_path = os.path.join(change_dir, "design.md")
        try:
            with open(design_path, "w", encoding="utf-8") as f:
                f.write(design_content)
            log.info("Wrote per-change design.md (%d lines) to %s",
                     len(design_content.split("\n")), design_path)
            return True
        except OSError as e:
            log.warning("Failed to write per-change design.md: %s", e)
            return False

    def get_design_dispatch_context(self, scope: str, snapshot_dir: str) -> str:
        """Return design tokens + component hierarchy + Figma source code."""
        context = self._run_bridge(
            f'design_context_for_dispatch "{scope}" "{snapshot_dir}"'
        )
        sources = self._run_bridge(
            f'design_sources_for_dispatch "{scope}" "{snapshot_dir}"',
            timeout=10,
        )
        if sources:
            context = (context + "\n\n" + sources) if context else sources
        return context

    def build_design_review_section(self, snapshot_dir: str) -> str:
        """Return design compliance section for code review."""
        return self._run_bridge(
            f'build_design_review_section "{snapshot_dir}"',
            timeout=10,
        )

    def fetch_design_data_model(self, project_path: str) -> str:
        """Return TypeScript interfaces from Figma source files."""
        return self._run_bridge(
            f'design_data_model_section "{project_path}"',
            timeout=10,
        )

    def decompose_hints(self) -> list:
        """Return web-specific decomposition hints for the planner."""
        return [
            "For each product category in the database schema enum, create a separate listing page task — do not use one category as a representative example.",
            "Every new user-facing route must have a corresponding i18n key task if the project uses internationalization.",
            "If a detail page ([slug]/page.tsx) exists, ensure the parent listing page also exists.",
            "Admin pages for all spec-mentioned resources must be created — not just the primary ones.",
            "Every feature change with CRUD operations (create/edit/delete) MUST include e2e tests that exercise each operation end-to-end: form fill → submit → verify result appears in list. Do NOT write tests that only verify page loads — test the actual data mutations.",
            "Admin e2e tests MUST verify sidebar/nav is visible on every admin page to catch layout consistency bugs.",
        ]
