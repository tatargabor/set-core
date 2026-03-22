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
            TemplateInfo(
                id="spa",
                description="Generic single-page application (minimal starting point)",
                template_dir="templates/spa",
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

    def planning_rules(self) -> str:
        rules_file = Path(__file__).parent / "planning_rules.txt"
        if rules_file.is_file():
            return rules_file.read_text()
        return ""

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
        """Detect package manager install command for dependency sync."""
        lockfiles = {
            "pnpm-lock.yaml": "pnpm install --frozen-lockfile",
            "yarn.lock": "yarn install --frozen-lockfile",
            "bun.lockb": "bun install --frozen-lockfile",
            "bun.lock": "bun install --frozen-lockfile",
            "package-lock.json": "npm ci",
        }
        for lockfile, cmd in lockfiles.items():
            if (Path(project_path) / lockfile).is_file():
                return cmd
        pkg_json = Path(project_path) / "package.json"
        if pkg_json.is_file():
            pm = self.detect_package_manager(project_path) or "npm"
            return f"{pm} install"
        return None

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
        """Register web-specific gates: e2e (Playwright) and lint (forbidden patterns)."""
        from set_orch.gate_runner import GateDefinition
        from .gates import execute_e2e_gate, execute_lint_gate

        return [
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

    def e2e_gate_env(self, port: int) -> dict[str, str]:
        """Map isolated port to Playwright/Next.js env vars."""
        return {
            "PW_PORT": str(port),
            "PORT": str(port),
            "PLAYWRIGHT_SCREENSHOT": "on",
        }

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

    def decompose_hints(self) -> list:
        """Return web-specific decomposition hints for the planner."""
        return [
            "For each product category in the database schema enum, create a separate listing page task — do not use one category as a representative example.",
            "Every new user-facing route must have a corresponding i18n key task if the project uses internationalization.",
            "If a detail page ([slug]/page.tsx) exists, ensure the parent listing page also exists.",
            "Admin pages for all spec-mentioned resources must be created — not just the primary ones.",
        ]
