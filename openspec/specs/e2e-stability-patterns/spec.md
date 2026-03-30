# Spec: E2E Stability Patterns

## Status: new

## Requirements

### REQ-E2E-GLOBALSETUP: Global setup must load dotenv and clean stale cache
- `global-setup.ts` template MUST load dotenv before any Prisma command (DATABASE_URL from .env)
- `global-setup.ts` template MUST delete `.next/` directory before test run to prevent stale `clientReferenceManifest` errors after merges
- Template code must be self-contained (import `dotenv/config` and `fs`/`path`)

### REQ-E2E-PLAYWRIGHT-CONFIG: Playwright config must be production-hardened
- Template MUST load dotenv at top of `playwright.config.ts`
- Template MUST spread `...process.env` into `webServer.env` so child process inherits all env vars
- Template MUST set `NEXTAUTH_SECRET` and `NEXTAUTH_URL` in webServer.env (derived from port)
- Template MUST set browser locale via `use.locale` (matching project's primary locale)
- Template MUST set `retries: process.env.CI ? 0 : 1` for transient dev server hydration flakes
- Template MUST set `headless: true` explicitly

### REQ-E2E-SELECTORS: Strict selector conventions in testing rule
- Rule MUST require `data-testid` attributes for all interactive elements that E2E tests target — not text-based selectors that break on i18n or merge
- Rule MUST warn about `getByRole('heading')` without `{ level: N }` — strict mode violations when page has multiple headings (h1 + footer h3/h4)
- Rule MUST require scoping selectors to a container (e.g., `page.getByRole('banner').getByText(...)`) when multiple matches are possible

### REQ-E2E-HYDRATION: Dev server hydration race handling
- Rule MUST document that Next.js dev server may return HTML during route compilation instead of JSON for API calls — tests must retry API calls
- Rule MUST require `waitUntil: 'networkidle'` for navigation to pages with hydration-dependent interactions (language switchers, client-side buttons)
- Rule MUST document that language/locale switchers should use `<Link>` not `<button onClick>` to avoid hydration dependency

### REQ-E2E-TESTUSER: Test user seeding requirement
- Rule MUST require that seed data includes a test user with known credentials (e.g., `test@example.com` / `password123`) for E2E login tests
- Rule MUST require that E2E test specs document which seed user they log in as

### REQ-E2E-NODEENV: NODE_ENV guard for test endpoints
- Rule MUST document that Next.js dev server sets `NODE_ENV=development`, never `test`
- Test-only API routes (e.g., `/api/test-email-log`) MUST guard with `process.env.NODE_ENV !== 'production'`, not `=== 'test'`
