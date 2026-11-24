# Roadmap / Future Work

## 1. OpenSpec 1.2 Migration

**Status:** Planned
**Priority:** Medium
**Explored:** 2026-04-04

### Context

OpenSpec 1.2.0 introduces a profile system, drift detection, and template-based skill generation. Currently we're on 1.1.1 with 4 heavily customized skills (verify, explore, ff, apply) that contain set-core specific logic: REQ traceability, acceptance criteria parsing, scope enforcement, overshoot detection, VERIFY_RESULT sentinel output.

### Problem

Two conflicting skill ownership models:
- **Current:** set-core owns skills statically, deploys via `set-project init`
- **1.2:** openspec owns skills via templates, manages via `openspec update` + drift detection

Running `openspec update` on 1.2 would overwrite our customizations.

### Proposed Approach (A+C Hybrid)

1. **CLI upgrade** — `npm i -g @fission-ai/openspec@1.2.0` (skills untouched)
2. **Extract customizations to rules layer** — move REQ traceability, AC checking, scope enforcement, overshoot detection, VERIFY_RESULT output from SKILL.md files into `templates/core/rules/` (e.g. `set-verify-extensions.md`, `set-traceability.md`)
3. **Switch to stock 1.2 skills** — `openspec update` generates stock SKILL.md files, our custom logic lives in rules
4. **Update `set-project init`** — deploy stock skills (from openspec) + custom rules (from set-core), consumers become `openspec update` compatible

### Key Risk

Rules layer constraints may not apply as strongly as in-skill instructions during execution. Needs E2E validation before committing.

### Affected Components

| Component | Impact |
|-----------|--------|
| `.claude/skills/openspec-*` | 10 SKILL.md files — 6 stock, 4 custom |
| `lib/project/deploy.sh` | Skill deployment logic changes |
| `templates/core/rules/` | New rules files for extracted custom logic |
| `bin/set-openspec` | May need profile config support |
| Consumer projects | Skill source changes from set-core to openspec |

### Reference

- Analysis session: 2026-04-04 `/opsx:explore`
- Stock 1.2 templates: `dist/core/templates/workflows/`
- Current customizations: verify (+4500 chars), explore (+2000), ff (+1800), apply (+750)

---

## 2. NIS2 Compliance Layer

**Status:** Planned (artifacts ready)
**Priority:** Medium
**Explored:** 2026-04-04

### Context

EU NIS2 directive (2022/2555) mandates 10 cybersecurity risk-management measures for organizations in 18 critical sectors (effective Oct 2024). Many requirements map directly to automated checks enforceable in CI/CD pipelines and quality gates. set-core's web template already covers basic security (OWASP patterns, secret exposure), but lacks structured NIS2 coverage.

### Proposed Approach

Opt-in compliance layer activated by a single config flag (`compliance.nis2.enabled: true` in `set/orchestration/config.yaml`). Three pillars:

1. **Template rules** (3 new `.claude/rules/` files):
   - `security-nis2.md` — Art.21 coding patterns (auth, encryption, session mgmt, input validation)
   - `logging-audit.md` — structured audit trail (JSON format, mandatory fields, append-only)
   - `supply-chain.md` — dependency management (pinned versions, lockfile, no --force)

2. **Verification rules + forbidden patterns** (4 rules, 5 patterns):
   - `audit-trail-coverage` — API routes must reference audit logging
   - `security-headers-present` — next.config must have CSP/HSTS/X-Frame-Options
   - `no-unsafe-crypto` — no MD5, SHA1, Math.random for security values
   - `rate-limit-on-auth` — auth endpoints must have rate limiting
   - Forbidden: eval(), document.write(), innerHTML=, console.log in API, hardcoded credentials

3. **Dedicated `security-audit` gate** (3 sub-checks):
   - Dependency audit (`npm audit --json` for high/critical CVEs)
   - Security header validation (scan next.config)
   - Crypto pattern scan (weak algorithms in source)
   - Position: after test, before review. Change-type aware (cleanup → soft).

4. **E2E scaffold** (`micro-web-nis2`):
   - Extends micro-web with login page + audit log viewer
   - Validates NIS2 gate enforcement end-to-end
   - Runner: `tests/e2e/runners/run-micro-web-nis2.sh`

### NIS2 Articles Covered

| Article | Topic | Enforcement |
|---------|-------|-------------|
| 21(2)(b) | Incident handling | Audit logging rules + verification rule |
| 21(2)(d) | Supply chain | supply-chain.md + dep audit gate |
| 21(2)(e) | Secure development | Forbidden patterns + crypto scan |
| 21(2)(h) | Cryptography | no-unsafe-crypto rule + hardcoded cred pattern |
| 21(2)(i) | Access control | Auth conventions + rate-limit rule |
| 21(2)(j) | MFA/auth | Template scaffold (middleware) |

### Key Design Decisions

- **Opt-in via config** — zero impact on non-NIS2 projects
- **Template rules always deployed** with self-gating instruction (agent ignores if NIS2 not enabled)
- **Verification rules + gate conditional** — `_is_nis2_enabled()` checks config at profile load
- **No new core abstractions** — uses existing VerificationRule, GateDefinition, forbidden patterns

### Affected Components

| Component | Impact |
|-----------|--------|
| `modules/web/set_project_web/project_type.py` | +4 verification rules, +5 forbidden patterns, +1 gate (conditional) |
| `modules/web/set_project_web/gates.py` | New `execute_security_audit_gate()` |
| `modules/web/set_project_web/templates/nextjs/rules/` | 3 new rule files |
| `tests/e2e/scaffolds/micro-web-nis2/` | New scaffold (spec, config, conventions) |
| `tests/e2e/runners/run-micro-web-nis2.sh` | New runner script |

### Reference

- Analysis session: 2026-04-04 `/opsx:explore` + `/opsx:ff`
- OpenSpec change: `openspec/changes/nis2-compliance-layer/` (26 tasks, 8 AC, all artifacts complete)
- NIS2 directive: EU 2022/2555, Article 21 (10 mandatory measures)
- ENISA Technical Implementation Guidance (June 2025, 170 pages)

---

## 3. shadcn/ui Design Connector

**Status:** Planned (artifacts ready)
**Priority:** Medium
**Explored:** 2026-04-04

### Context

The design pipeline currently requires a Figma MCP to generate `design-snapshot.md`. For Tailwind-based projects using shadcn/ui, the design tokens already live in the filesystem — `tailwind.config.ts`, `globals.css` CSS variables, and `components.json`. A local parser can extract these without any external tool dependency.

The Figma MCP was dropped from active use due to instability (auth issues, slow fetches). The static approach (generate → commit → pipeline consumes) proved more reliable. The shadcn connector follows the same pattern: `set-design-sync --source shadcn` generates `design-system.md` from local files, which gets committed and consumed by the existing pipeline.

### Proposed Approach

1. **Parser** (`lib/design/shadcn_parser.py`):
   - Parse `components.json` → detect shadcn/ui, extract config
   - Parse `tailwind.config.ts`/`.js` → extract `theme.extend` tokens (v3) or `@theme` CSS blocks (v4)
   - Parse `globals.css` → extract `:root` and `.dark` CSS custom properties
   - Scan `src/components/ui/` → build installed component catalog
   - Output: `design-system.md` in same format bridge.sh consumes

2. **Detection** (`lib/design/bridge.sh`):
   - New `detect_shadcn_project()` — checks for `components.json` with valid `tailwind` section
   - Fallback path: when no design MCP detected but shadcn/ui present

3. **CLI integration** (`set-design-sync --source shadcn`):
   - Static generation before orchestration start (not runtime preflight)
   - Output is committed, reviewable, editable — same model as Figma snapshots

4. **E2E scaffold** (`micro-web-shadcn`):
   - Extend micro-web with shadcn/ui config (components.json, CSS vars, ui/ components)
   - Validates connector end-to-end

### Key Design Decisions

- **Static, not runtime** — generate + commit before orchestration, like Figma snapshots
- **Regex-based token extraction** — no Node.js/AST dependency, covers common Tailwind config patterns
- **MCP takes priority** — if Figma/Penpot MCP registered, use it; shadcn is the fallback
- **Core-only** (`lib/design/`) — not module-specific, works for any shadcn/ui project
- **Tailwind v3 + v4** — JS config `theme.extend` and CSS `@theme` both supported

### Token flow

```
components.json ─┐
tailwind.config  ├──▶ shadcn_parser.py ──▶ design-system.md ──▶ [existing pipeline]
globals.css      │     (set-design-sync)    (committed)          planner → dispatch → verify
src/components/ui/┘
```

### Affected Components

| Component | Impact |
|-----------|--------|
| `lib/design/shadcn_parser.py` | New file — parser core |
| `lib/design/bridge.sh` | +`detect_shadcn_project()`, fallback chain update |
| `lib/set_orch/planner.py` | `_fetch_design_context()` shadcn fallback path |
| `bin/set-design-sync` | CLI entry point for static generation |
| `tests/e2e/scaffolds/micro-web-shadcn/` | New scaffold with shadcn/ui config |

### Reference

- Analysis session: 2026-04-04 `/opsx:ff`
- OpenSpec change: `openspec/changes/shadcn-ui-design-connector/` (22 tasks, 12 AC, all artifacts complete)
- shadcn/ui: [ui.shadcn.com](https://ui.shadcn.com)

---

## 4. Core/Web Layer Separation — Leaked Abstractions Cleanup

**Status:** Planned
**Priority:** High
**Explored:** 2026-04-04

### Context

The architecture rule is clear: `lib/set_orch/` (Layer 1) is abstract, `modules/web/` (Layer 2) holds framework-specific logic. In practice, ~170+ web-specific references have leaked into the core layer. This happened organically as features were built — web was the only project type, so shortcuts were taken. Now that the module system exists and external plugins are possible, these leaks block proper extensibility.

### What Leaked Where

#### `lib/set_orch/verifier.py` — Heaviest offender
- Hardcoded Jest/Vitest/Playwright output parsing (`parse_test_counts()`, `_collect_playwright_screenshots()`)
- TypeScript/Next.js error regex patterns (`.tsx` file patterns, Next.js module/route errors)
- `_run_phase_end_e2e()` directly imports from `set_project_web.gates`
- `_detect_build_command()` reads `package.json` scripts

#### `lib/set_orch/dispatcher.py` — Package management + i18n
- `install_dependencies()` hardcodes pnpm/yarn/npm detection and commands
- `_LOCKFILE_NAMES` set with JS-specific lockfiles
- i18n detection checks for `next-intl`, `react-intl`, `i18next`
- Read-first directive for `prisma/schema.prisma`

#### `lib/set_orch/compare.py` — Entirely Next.js-specific
- `collect_routes()` globs for `page.tsx` (Next.js App Router)
- `collect_schema()` parses `prisma/schema.prisma`
- `collect_deps()` reads `package.json`
- Hardcoded paths: `globals.css`, `vitest.config.ts`, `playwright.config.ts`

#### `lib/set_orch/dispatcher_schema.py` — Prisma parser in core
- Entire `parse_prisma_schema()` function with Prisma-specific regex
- Hardcoded `prisma/schema.prisma` path

#### `lib/set_orch/planner.py` — Package.json + test framework detection
- Reads `package.json` for test framework detection (`vitest`, `jest`, `mocha`)
- Checks for `vitest.config.*` files
- `tailwind.config.ts` in cross-cutting files list

#### `lib/set_orch/merger.py` — JS package management
- `install_dependencies_if_lockfile_changed()` hardcodes pnpm/npm
- Vitest/Jest "no test files" heuristics

#### `lib/set_orch/config.py` — Package manager detection
- `_detect_package_manager()` returns bun/pnpm/yarn/pip/poetry/npm
- `_detect_dev_server()` reads package.json scripts

#### `lib/set_orch/templates.py` — Web patterns in planning
- Prisma pattern detection in diff categorization
- `.tsx|jsx|vue|svelte` file extensions hardcoded
- Playwright test planning rules

#### `lib/set_orch/profile_loader.py` — npm install in core profile
- `install-deps-npm` task with hardcoded `npm install`
- JS lockfile triggers

#### `bin/` CLI tools — Web assumptions
- `set-merge`: `auto_resolve_package_json()`, pnpm-specific install flags, `tsconfig.tsbuildinfo`
- `set-new`: hardcoded npm/pnpm install logic
- `set-e2e-report`: Playwright screenshot capture, Jest test counts
- `set-orchestrate`: pnpm post-merge commands

#### `lib/design/` — Figma-only, not abstracted
- `fetcher.py`: Figma OAuth, MCP, URL parsing — no design tool abstraction
- `bridge.sh`: `detect_design_mcp()` hardcodes `figma|penpot|sketch|zeplin`
- `design_parser.py`: `.tsx` file parsing, Tailwind class extraction

### Proposed Approach

1. **Extend `ProjectType` ABC** with methods the core currently hardcodes:
   - `detect_package_manager() -> str`
   - `install_dependencies(wt_path) -> CommandResult`
   - `parse_test_output(stdout) -> TestCounts`
   - `collect_routes(wt_path) -> list[str]`
   - `collect_schema(wt_path) -> dict`
   - `parse_build_errors(stderr) -> list[BuildError]`
   - `get_cross_cutting_files() -> list[str]`
   - `get_lockfile_names() -> list[str]`
   - `detect_test_framework() -> str`
   - `resolve_auto_merge_conflicts(file) -> bool`

2. **Move implementations to `modules/web/`**:
   - Prisma parser → `modules/web/set_project_web/schema.py`
   - Playwright/Vitest output parsing → `modules/web/set_project_web/test_parsers.py`
   - Package manager detection/install → `modules/web/set_project_web/deps.py`
   - Next.js route collection → `modules/web/set_project_web/routes.py`
   - package.json merge → `modules/web/set_project_web/merge_helpers.py`

3. **Core calls through profile interface**:
   ```python
   # Before (leaked):
   pkg = Path("package.json")
   if "vitest" in json.loads(pkg.read_text()).get("devDependencies", {}): ...

   # After (abstracted):
   test_fw = profile.detect_test_framework()
   ```

4. **Design abstraction** — `lib/design/` should define a `DesignSource` ABC, with `FigmaSource` and `ShadcnSource` as implementations.

### Key Risk

This is a large refactor touching nearly every core file. Must be done incrementally — one subsystem at a time (e.g., test parsing first, then package management, then schema). Each step needs E2E validation to ensure no regression.

### Incremental Order (suggested)

| Phase | Subsystem | Core files touched | Risk |
|-------|-----------|-------------------|------|
| 1 | Test output parsing | verifier.py, merger.py | Medium — most isolated |
| 2 | Package management | dispatcher.py, merger.py, config.py, bin/set-merge | High — many call sites |
| 3 | Schema/route collection | compare.py, dispatcher_schema.py | Low — used by compare only |
| 4 | Build error parsing | verifier.py, templates.py | Medium |
| 5 | Design abstraction | lib/design/*.py, bridge.sh | Low — self-contained |
| 6 | CLI tools | bin/set-merge, set-new, set-e2e-report | Medium — user-facing |

### Reference

- Architecture rule: `.claude/rules/modular-architecture.md`
- Module system: `modules/web/set_project_web/project_type.py` (existing WebProjectType)
- Profile ABC: `lib/set_orch/profile_types.py` (ProjectType base class)
