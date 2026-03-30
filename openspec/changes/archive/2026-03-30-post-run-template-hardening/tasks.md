# Tasks: post-run-template-hardening

## 1. Template Code — global-setup.ts

- [x] 1.1 Add `import 'dotenv/config'` at top of `modules/web/set_project_web/templates/nextjs/tests/e2e/global-setup.ts` so DATABASE_URL is available from .env for Prisma commands [REQ: REQ-E2E-GLOBALSETUP]
- [x] 1.2 Add `.next` cache cleanup before Prisma commands: `import { existsSync, rmSync } from 'fs'; import { join } from 'path'; const nextDir = join(__dirname, '../../.next'); if (existsSync(nextDir)) rmSync(nextDir, { recursive: true });` [REQ: REQ-E2E-GLOBALSETUP]

## 2. Template Code — playwright.config.ts

- [x] 2.1 Add `import 'dotenv/config'` at top of `modules/web/set_project_web/templates/nextjs/playwright.config.ts` [REQ: REQ-E2E-PLAYWRIGHT-CONFIG]
- [x] 2.2 Add `env: { ...process.env, NEXTAUTH_SECRET: process.env.NEXTAUTH_SECRET || 'test-secret-for-e2e', NEXTAUTH_URL: \`http://localhost:\${port}\` }` to `webServer` block [REQ: REQ-E2E-PLAYWRIGHT-CONFIG]
- [x] 2.3 Change retries from `process.env.CI ? 2 : 0` to `process.env.CI ? 2 : 1` (1 local retry for transient hydration flakes) [REQ: REQ-E2E-PLAYWRIGHT-CONFIG]
- [x] 2.4 Add `headless: true` and `locale: 'en-US'` to `use` block (locale is a sensible default, projects override per their primary locale) [REQ: REQ-E2E-PLAYWRIGHT-CONFIG, REQ-I18N-E2E-LOCALE]

## 3. Rule — testing-conventions.md

- [x] 3.1 Add "## Post-Merge E2E Stability" section after "Playwright Infrastructure Bootstrap": document .next cache deletion in global-setup, dotenv loading requirement, NEXTAUTH_SECRET in webServer env [REQ: REQ-E2E-GLOBALSETUP, REQ-E2E-PLAYWRIGHT-CONFIG]
- [x] 3.2 Add "## Selector Best Practices" section: data-testid MUST for interactive elements, getByRole('heading') must specify `{ level: N }`, scope selectors to container when multiple matches possible [REQ: REQ-E2E-SELECTORS]
- [x] 3.3 Add "## Hydration Race Conditions" section: waitUntil networkidle for hydration-dependent pages, language switchers must use Link not button, API calls from tests must handle HTML-instead-of-JSON during route compilation (retry pattern) [REQ: REQ-E2E-HYDRATION]
- [x] 3.4 Add to "Playwright Infrastructure Bootstrap" section: seed data MUST include a test user with known credentials, E2E specs must document which seed user they use [REQ: REQ-E2E-TESTUSER]
- [x] 3.5 Add "## Test-Only Endpoints" section: NODE_ENV guard must be `!== 'production'` not `=== 'test'` because Next.js dev server sets NODE_ENV=development [REQ: REQ-E2E-NODEENV]

## 4. Rule — auth-conventions.md

- [x] 4.1 Add one-liner to "## Password & Credentials" section: `process.env.JWT_SECRET || "fallback"` is FORBIDDEN — cross-reference security-patterns.md § 10 for details [REQ: REQ-AUTH-NO-SECRET-FALLBACK]
- [x] 4.2 Add "## Layout-Level Session Validation" section after "Middleware": protected layout MUST call getSession()/verifyToken() not just check cookie presence, root layout conditional nav must also validate JWT [REQ: REQ-AUTH-LAYOUT-VALIDATION]
- [x] 4.3 Add to "## Auth Library" section: after successful registration, auto-login via signIn() rather than redirect to login page [REQ: REQ-AUTH-POST-REGISTER]

## 5. Rule — auth-middleware.md (framework-rules/web/)

- [x] 5.1 Update middleware matcher pattern in "Pattern: Route Protection Middleware" to explicitly show excluding ALL /api routes: `matcher: ['/((?!api|_next|.*\\..*).*)']` — add warning that partial exclusions (only /api/auth) let i18n/auth middleware corrupt other API responses [REQ: REQ-AUTH-MIDDLEWARE-API-EXCLUDE, REQ-I18N-MIDDLEWARE]

## 6. Rule — security-patterns.md (framework-rules/web/)

- [x] 6.1 Add "## 10. Secret Environment Variables" section to `framework-rules/web/security-patterns.md`: NEVER use fallback/default values for secret env vars (JWT_SECRET, NEXTAUTH_SECRET, DATABASE_URL with credentials). Missing = crash at startup. This is general web security, not Next.js-specific [REQ: REQ-AUTH-NO-SECRET-FALLBACK]

## 7. Rule — functional-conventions.md

- [x] 7.1 Add "## Slug Generation" section after "Database Patterns": slugs MUST strip/transliterate accented characters (provide JS example: `str.normalize('NFD').replace(/[\u0300-\u036f]/g, '')`), test with non-ASCII input [REQ: REQ-UI-SLUG-ENCODING]
- [x] 7.2 Add "## URL Filter Encoding" section: when filter values may contain commas, use pipe `|` as delimiter between values, or URL-encode individual values [REQ: REQ-UI-FILTER-ENCODING]
- [x] 7.3 Add "## Rendering Consistency" section: saved/cached data views MUST reuse the same components as live views — never render raw JSON or use different formatting for the same data shape [REQ: REQ-UI-RENDER-CONSISTENCY]

## 8. Rule — ui-conventions.md

- [x] 8.1 Add "## No Placeholder Content" section after "Loading & Empty States": components MUST use real sub-components with real data, never placeholder divs. Product grids use ProductCard, featured sections use actual components. "Coming soon" text is not acceptable in delivered code [REQ: REQ-UI-NO-PLACEHOLDERS]
- [x] 8.2 Add "## Navigation Integrity" to existing "## Layout Patterns" section: every navigation link (header, footer, sidebar, CTA buttons) MUST point to an existing route. Broken links are gate failures [REQ: REQ-UI-NO-PLACEHOLDERS]

## 9. Rule — NEW i18n-conventions.md

- [x] 9.1 Create `modules/web/set_project_web/templates/nextjs/rules/i18n-conventions.md` with frontmatter `paths: ["src/i18n/**", "messages/**", "src/middleware.*", "src/components/**/Header*", "src/components/**/Footer*"]` [REQ: REQ-I18N-TRANSLATION-KEYS]
- [x] 9.2 Write "## Translation Keys" section: all user-facing strings MUST use t('key'), units/measurements must have translation maps, seed data must have translations for all supported locales [REQ: REQ-I18N-TRANSLATION-KEYS]
- [x] 9.3 Write "## Sidecar File Resilience" section: per-change i18n sidecar imports MUST always use try/catch pattern, provide code example [REQ: REQ-I18N-SIDECAR-RESILIENCE]
- [x] 9.4 Write "## Language Switcher" section: MUST use Link with locale prop (not button+router.replace), explain hydration dependency reason [REQ: REQ-I18N-LANGUAGE-SWITCHER]
- [x] 9.5 Write "## Dynamic Route Links" section: next-intl pathnames require `{ pathname: '/path/[slug]', params: { slug } }` object format, string interpolation crashes. Language switcher on dynamic pages must use next/navigation usePathname() [REQ: REQ-I18N-DYNAMIC-ROUTES]
- [x] 9.6 Write "## E2E Testing with i18n" section: Playwright config must set use.locale, test assertions must match active locale translations [REQ: REQ-I18N-E2E-LOCALE]
- [x] 9.7 Write "## Middleware Configuration" section: cross-reference auth-middleware.md for the full matcher pattern. Note that next-intl middleware has the same requirement — must exclude /api routes to avoid rewriting JSON responses [REQ: REQ-I18N-MIDDLEWARE]

## 10. Engine — Merger sidecar handling

- [x] 10.1 In `modules/web/set_project_web/post_merge.py` (or the archive path in engine.py): after archiving a change, check if the change's worktree had i18n sidecar files. If so, verify that `src/i18n/request.ts` (or equivalent) wraps those imports in try/catch. Log a warning if bare imports are detected [REQ: REQ-ENGINE-SIDECAR-MERGE]

## 11. Engine — Dispatcher redispatch branch preservation

- [x] 11.1 In `lib/set_orch/dispatcher.py`, modify `_create_worktree` (or the redispatch path): when redispatching a change that already has a branch (`change/<name>`) with commits ahead of main, create the new worktree from that branch instead of from main. Add safety check: if the branch has merge conflicts with main, fall back to branching from main [REQ: REQ-ENGINE-REDISPATCH-BRANCH]

## 12. Engine — Issue ownership stall timeout

- [x] 12.1 In `lib/set_orch/dispatcher.py` `resume_stalled_changes()`: add a timeout check when skipping stalled changes owned by the issue pipeline. If ownership has lasted longer than `ISSUE_OWNERSHIP_TIMEOUT` (default 1800s / 30min), release ownership and allow normal stall recovery. Log warning when approaching timeout [REQ: REQ-ENGINE-ISSUE-TIMEOUT]

## Acceptance Criteria

- [x] AC-1: WHEN global-setup.ts template is deployed to a new project THEN dotenv is loaded and .next cache is cleaned before Prisma commands [REQ: REQ-E2E-GLOBALSETUP]
- [x] AC-2: WHEN playwright.config.ts template is deployed THEN it includes dotenv, env spread, NEXTAUTH vars, locale, and retry=1 for local [REQ: REQ-E2E-PLAYWRIGHT-CONFIG]
- [x] AC-3: WHEN testing-conventions.md is deployed THEN it contains sections on post-merge stability, selector best practices, hydration races, test user seeding, and NODE_ENV guards [REQ: REQ-E2E-SELECTORS, REQ-E2E-HYDRATION, REQ-E2E-TESTUSER, REQ-E2E-NODEENV]
- [x] AC-4: WHEN auth-conventions.md is deployed THEN it forbids hardcoded secret fallbacks and requires layout-level JWT validation [REQ: REQ-AUTH-NO-SECRET-FALLBACK, REQ-AUTH-LAYOUT-VALIDATION]
- [x] AC-5: WHEN i18n-conventions.md is deployed THEN it covers translation keys, sidecar resilience, Link-based switcher, dynamic routes, E2E locale, and middleware exclusion [REQ: REQ-I18N-*]
- [x] AC-6: WHEN a stalled change is owned by the issue pipeline for >30min THEN ownership is released and stall recovery proceeds [REQ: REQ-ENGINE-ISSUE-TIMEOUT]
- [x] AC-7: WHEN an agent is redispatched for a change that has committed artifacts on its branch THEN the new worktree preserves those commits [REQ: REQ-ENGINE-REDISPATCH-BRANCH]
- [x] AC-8: WHEN a change with i18n sidecars is archived THEN the app does not crash from missing sidecar imports [REQ: REQ-ENGINE-SIDECAR-MERGE]
