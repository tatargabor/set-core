---
paths:
  - "tests/**"
  - "**/*.test.*"
  - "**/*.spec.*"
  - "playwright.config.*"
  - "jest.config.*"
---
# Testing Conventions

## Testing Strategy — Testing Diamond

The Testing Diamond model prioritizes integration/E2E tests over unit tests for web applications. Web apps fail primarily at runtime boundaries (cookies, middleware, DB queries, redirects) — mock-based unit tests hide these failures.

- **Unit tests** (Jest/Vitest ~40%): pure logic, utilities, validation, formatting
- **Integration tests** (~50%): API routes, DB queries, component interactions
- **E2E tests** (Playwright ~10%): critical user flows against a running dev server

Reference: ISTQB CT-TAS v1.0 (2024) test levels — component, component integration, contract, UI (E2E).

## Two-Step Verification

Both test levels run pre-merge in the worktree:

**Step 1 — Fast feedback (~30s):**
- `test_command` (Jest/Vitest) — catches type errors, import errors, logic bugs
- Build check (`pnpm build`) — catches TypeScript errors

**Step 2 — Thorough validation (~2min):**
- `e2e_command` (Playwright) — catches runtime bugs (cookies, middleware, DB, auth flows)

**Post-merge (optional):**
- `smoke_command` — cross-feature integration tests on main. Only needed when multiple features must be tested together after merge.

## Unit Tests — What to Mock, What Not To
- DO mock: external APIs, email services, payment gateways
- DO NOT mock: Next.js runtime APIs (cookies(), headers(), redirect(), revalidatePath())
- DO NOT mock: database queries — use a test database or in-memory SQLite
- If a function calls cookies() or headers(), test it via Playwright, not Jest

## Playwright Functional Tests
- Each user-facing feature change MUST include Playwright test specs
- Test specs describe real user flows: navigate to page → interact with UI → verify outcome
- Tests run against `localhost` with a real dev server (not mocked)
- Use page object pattern for reusable selectors
- Test both happy path AND error states (invalid form data, unauthorized access)
- Auth-protected routes: test that unauthenticated users are redirected to login
- Form submissions: test with real data, verify server-side effects (DB records, redirects)

### Cold-Visit Tests (Critical)
Every E2E test file MUST include a **cold-visit test** — a test that navigates directly to the page as the very first action, without any prior setup (no login, no add-to-cart, no session cookie). This catches Server Component bugs where:
- `cookies().set()` is called from a Server Component instead of a Server Action
- Session creation crashes on first visit (no existing cookie → write attempt → Next.js error)
- Pages assume prior state that doesn't exist for new users

Example pattern:
```typescript
test("cold visit — page loads without prior session", async ({ page }) => {
  // Navigate directly — no prior actions, no cookies
  await page.goto("/cart");
  // Should show empty state, NOT crash with runtime error
  await expect(page.getByText("Your cart is empty")).toBeVisible();
});
```

Why: Agents naturally write E2E tests that set up state first (add product → visit cart). This means every test has a valid session cookie by the time it reaches the page. Cold-visit tests are the only way to catch cookie/session initialization bugs in Server Components.

## Playwright Infrastructure Bootstrap

The infrastructure/foundation change (first in dependency order) MUST set up Playwright:

1. Create `playwright.config.ts` with `PW_PORT` env var support and `webServer` auto-start
2. Add `@playwright/test` to devDependencies
3. Run `npx playwright install chromium` (browser cache at `~/.cache/ms-playwright/`, shared across worktrees)
4. Create `tests/e2e/global-setup.ts`:
   ```typescript
   import { execSync } from 'child_process';
   async function globalSetup() {
     execSync('npx prisma generate', { stdio: 'inherit' });
     execSync('npx prisma db push --force-reset', { stdio: 'inherit' });
     execSync('npx prisma db seed', { stdio: 'inherit' });
   }
   export default globalSetup;
   ```
5. Add `testPathIgnorePatterns` to jest config (see Jest/Playwright Coexistence below)

Feature changes only create their own `tests/e2e/<feature>.spec.ts` files, not infrastructure.

**Startup guide maintenance:** When the infrastructure/foundation change adds new setup steps (Playwright install, DB push, env vars), it MUST also update the `## Application Startup` section in CLAUDE.md so agents entering the worktree later know how to bootstrap the project.

## Prisma Tests — Jest Environment

Test files that import Prisma client **must** declare the `node` environment — the default `jsdom` environment causes Prisma to fail with cryptic errors:

```typescript
/**
 * @jest-environment node
 */
import { prisma } from '@/lib/prisma'
// ...
```

Add this docblock at the top of every test file that uses Prisma directly.

## pnpm Non-Interactive Builds

In worktrees and CI, `pnpm` may prompt interactively for approval of build scripts (`pnpm approve-builds`), blocking the process. Prevent this by adding to `package.json`:

```json
{
  "pnpm": {
    "onlyBuiltDependencies": []
  }
}
```

This allows all packages to run their postinstall scripts without interactive prompts.

## jest.config.ts — Correct Keys

Common mistake: `setupFilesAfterSetup` does NOT exist in Jest. The correct key is `setupFilesAfterEnv`:

```typescript
// ✓ correct
setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],

// ✗ wrong — silently ignored by Jest
setupFilesAfterSetup: ['<rootDir>/jest.setup.ts'],
```

## Jest/Playwright Coexistence

Jest's default `testRegex` matches `.spec.ts` files. When Playwright tests exist in `tests/e2e/`, Jest picks them up and crashes on Playwright imports in jsdom:

```
TypeError: Class extends value undefined is not a constructor or null
```

**Fix:** Add to `jest.config.ts`:
```typescript
testPathIgnorePatterns: ["/node_modules/", "/tests/e2e/"],
```

This MUST be set up in the infrastructure/foundation change alongside `playwright.config.ts`.

## Port Isolation for Parallel E2E

The orchestrator sets `PW_PORT` env var per worktree (random in 3100-3999) to avoid port collisions between parallel changes.

`playwright.config.ts` template:
```typescript
const PORT = process.env.PW_PORT ? parseInt(process.env.PW_PORT) : 3100;
export default defineConfig({
  use: {
    baseURL: `http://localhost:${PORT}`,
    headless: true,  // explicit — never open a browser window in CI/agent pipelines
    screenshot: 'on',
  },
  webServer: {
    command: `pnpm dev --port ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: false,  // fail fast on port collision
    timeout: 120_000,
  },
  globalSetup: './tests/e2e/global-setup.ts',
});
```

## DB Isolation for E2E Tests

**SQLite (automatic):** Each worktree has its own `prisma/dev.db` file. Schema divergence between worktrees (different changes adding different models) is naturally isolated — each worktree's `prisma db push` creates tables matching its own schema.

**PostgreSQL/MySQL (future):** Per-worktree database names via `DATABASE_URL` override. The orchestrator will support `e2e_db_setup`/`e2e_db_teardown` hooks.

**Always run `prisma generate` before `prisma db push`** — without it, the Prisma client doesn't know about models added by the current change, causing seed/test failures.

## Test File Organization
- Unit tests: co-located with source (`src/**/*.test.ts`) or `__tests__/`
- Playwright tests: `tests/e2e/*.spec.ts` (one file per feature area)
- Shared fixtures: `tests/e2e/fixtures/`
- Global setup: `tests/e2e/global-setup.ts`

## What the Planner Must Specify
For each feature change, the planner scope MUST include:
- An explicit file deliverable: `Create tests/e2e/<feature>.spec.ts`
- Pages to visit and expected initial state
- User interactions (click, fill, select, navigate)
- Test data (form values, credentials)
- Expected outcomes (visible text, URL changes, redirects)
- Error scenarios to cover

Do NOT just list scenario descriptions — create actual test files.
