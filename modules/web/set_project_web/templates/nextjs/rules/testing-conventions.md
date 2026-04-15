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
   import 'dotenv/config';
   import { execSync } from 'child_process';
   import { existsSync, rmSync } from 'fs';
   import { join } from 'path';

   async function globalSetup() {
     // Clean stale .next cache — prevents clientReferenceManifest errors after merges
     const nextDir = join(__dirname, '../../.next');
     if (existsSync(nextDir)) rmSync(nextDir, { recursive: true });

     execSync('npx prisma generate', { stdio: 'inherit' });
     execSync('npx prisma db push --force-reset', { stdio: 'inherit' });
     execSync('npx prisma db seed', { stdio: 'inherit' });
   }
   export default globalSetup;
   ```
5. Seed data MUST include a test user with known credentials (e.g., `test@example.com` / `password123`) for E2E login tests. E2E spec files must document which seed user they log in as.
6. Add `testPathIgnorePatterns` to jest config (see Jest/Playwright Coexistence below)

Feature changes only create their own `tests/e2e/<feature>.spec.ts` files, not infrastructure.

**Startup guide maintenance:** When the infrastructure/foundation change adds new setup steps (Playwright install, DB push, env vars), it MUST also update the `## Application Startup` section in CLAUDE.md so agents entering the worktree later know how to bootstrap the project.

## Prisma Tests — Jest Environment

Test files that import Prisma client **must** declare the `node` environment — the default `jsdom` environment causes Prisma to fail with cryptic errors:

```typescript
/**
 * @jest-environment node
 */
import { prisma } from "@/lib/prisma"
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

## Vitest/Playwright Coexistence

Vitest's default include pattern matches `.spec.ts` files. When Playwright tests exist in `tests/e2e/`, Vitest picks them up, tries to import `@playwright/test` in node — and hangs or crashes.

**Fix:** Add to `vitest.config.ts`:
```typescript
export default defineConfig({
  test: {
    exclude: ["**/node_modules/**", "**/tests/e2e/**"],
  },
})
```

Also: the `test` script in `package.json` MUST use `vitest run` (single-run), NOT `vitest` (watch mode). Watch mode hangs indefinitely in CI/gate pipelines:
```json
"test": "vitest run"
```

This MUST be set up in the infrastructure/foundation change alongside `playwright.config.ts`.

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
  // `list` — NOT `html`. `html` buffers every artifact until suite end and
  // has caused OOM (SIGKILL) when combined with `screenshot: 'on'` on
  // realistic suites. `list` streams output and is parseable by the
  // orchestrator's failure extractor.
  reporter: 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    headless: true,  // explicit — never open a browser window in CI/agent pipelines
    // ALWAYS — pass and fail. The per-attempt archive relies on every
    // run producing artifacts so the user can verify tests actually
    // re-executed after a fix. `'only-on-failure'` is FORBIDDEN (flagged
    // by the rules gate) — a green run with zero screenshots is
    // indistinguishable from a run that never executed.
    screenshot: 'on',
    trace: 'on',
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

### Screenshot capture — MANDATORY per-attempt

- `screenshot: 'on'` — every test, pass and fail. FORBIDDEN: `'only-on-failure'`, `'off'`, `false`. The rules gate flags these as critical.
- `trace: 'on'` — every test. FORBIDDEN: `'on-first-retry'`, `'off'`. Per-attempt archive needs traces too.
- `reporter: 'list'` — NOT `'html'` (OOM risk with `screenshot: 'on'`). The rules gate warns on `'html'`.
- Rationale: The orchestrator archives `test-results/` to `<runtime>/screenshots/e2e/<change>/attempt-N/` after every E2E gate run. A passing run with zero artifacts is indistinguishable from a run that never executed — the user cannot verify the fix actually re-triggered the tests. Always-on capture is the forensic contract.

## DB Isolation for E2E Tests

**SQLite (automatic):** Each worktree has its own `prisma/dev.db` file. Schema divergence between worktrees (different changes adding different models) is naturally isolated — each worktree's `prisma db push` creates tables matching its own schema.

**PostgreSQL/MySQL (future):** Per-worktree database names via `DATABASE_URL` override. The orchestrator will support `e2e_db_setup`/`e2e_db_teardown` hooks.

**Always run `prisma generate` before `prisma db push`** — without it, the Prisma client doesn't know about models added by the current change, causing seed/test failures.

### Workers Must Be 1 with SQLite

SQLite has a single-writer constraint. Concurrent Playwright workers writing to the same `dev.db` (login attempts, session creation, order writes) cause `SQLITE_BUSY` errors and flaky tests with non-deterministic failure patterns.

**Required `playwright.config.ts` setting:**
```typescript
export default defineConfig({
  fullyParallel: false,
  workers: 1,  // SQLite single-writer constraint
  ...
})
```

Override only when the project uses Postgres/MySQL with per-worker database isolation. The default template ships with `workers: 1` for safety.

## Rate Limiters Must Skip Outside Production

Auth and API rate limiters (login, password reset, OTP, etc.) MUST short-circuit when `NODE_ENV !== "production"`. E2E suites repeatedly log in as the same test user and will trigger the rate limit after the configured threshold (typically 5 attempts/minute), causing the rest of the run to fail with `429` responses unrelated to the actual feature being tested.

**Required pattern:**
```typescript
// src/lib/rate-limit.ts
export function rateLimit(key: string, opts = { maxAttempts: 5, windowMs: 60_000 }) {
  // Skip in dev/test — E2E tests reuse the same credentials
  if (process.env.NODE_ENV !== "production") {
    return { success: true }
  }
  // ... real rate-limit logic
}
```

**Anti-pattern:** Only checking `NODE_ENV === "test"`. Playwright runs the dev server with `NODE_ENV=development`, not `test`, so the rate limiter still triggers. Use `!== "production"` to cover both dev and test contexts.

## Unique Values for Tests That Write Unique-Constrained Entities

Tests that `CREATE` rows with a UNIQUE column (coupon `code`, promo `slug`, user `email`, invitation `token`) MUST generate a distinct value per test run. Sharing a literal value across multiple tests causes a second-invocation crash on retry, and cross-file collisions when a different `.spec.ts` touches the same entity. The failure surfaces as `Unique constraint failed` or as a silent "element not found" when the create returns the existing row instead of a new one.

**Wrong — every test uses the same code, the retry hits a uniqueness violation:**
```typescript
test("admin creates coupon", async ({ page }) => {
  await page.getByLabel("Code").fill("SUMMER20"); // ← collides on retry, collides with another spec
  await page.getByRole("button", { name: "Create" }).click();
});
```

**Correct — derive from `testInfo` or the worker index:**
```typescript
test("admin creates coupon", async ({ page }, testInfo) => {
  const code = `E2E_${testInfo.workerIndex}_${Date.now().toString(36)}`;
  await page.getByLabel("Code").fill(code);
  // Store for teardown / later asserts
  testInfo.attach("created-coupon", { body: code, contentType: "text/plain" });
});
```

Alternatives: `crypto.randomUUID()` for long-lived entities, `testInfo.title` slugified for human-readable fixtures, or a per-worker prefix set in `globalSetup`. Whatever you pick, the value MUST differ across parallel workers AND across retries of the same test.

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

## Post-Merge E2E Stability

After merging other changes into main, E2E tests commonly break due to stale cache or missing env vars. The following patterns MUST be applied:

1. **`.next` cache cleanup in global-setup** — the `clientReferenceManifest` error occurs when `.next/` contains stale build artifacts from a previous branch. Global setup MUST delete `.next/` before running Prisma commands.
2. **dotenv loading** — `global-setup.ts` and `playwright.config.ts` MUST import `dotenv/config` at the top so `DATABASE_URL`, `NEXTAUTH_SECRET`, and other env vars are available from `.env` without explicit env var passing.
3. **NEXTAUTH_SECRET in webServer env** — Playwright's `webServer` spawns a child process that does NOT inherit the parent's dotenv. The config MUST spread `...process.env` into `webServer.env` and explicitly set `NEXTAUTH_SECRET` and `NEXTAUTH_URL` (derived from port). Without this, login silently fails due to unsigned JWTs.

## Selector Best Practices

- **Use `data-testid` for interactive elements** — text-based selectors (`getByText('Submit')`) break on i18n changes, merge-induced label changes, and locale variations. All buttons, inputs, and navigation elements that E2E tests target MUST have `data-testid` attributes.
- **Heading selectors MUST specify level** — `getByRole('heading')` without `{ level: N }` causes strict mode violations when the page has multiple headings (e.g., h1 in content + h3/h4 in footer). Always use `getByRole('heading', { level: 1 })`.
- **Scope selectors to containers** — when multiple elements match a selector, scope to a parent: `page.getByRole('banner').getByText('Home')` instead of `page.getByText('Home')`.
- **Password fields** — `getByLabel('Password')` may match both the input and a show/hide toggle button. Use `page.locator('#password')` or `data-testid` instead.

## Playwright Strict Mode on Repeated Elements

Playwright's default strict mode throws on selectors that match multiple elements. Common repeating components that trigger this:

- Star ratings / review badges / review counts (appear in listing cards AND detail pages AND cross-sell)
- Validation error messages (same error text shown above AND below the form)
- Cart badge counts (header + mobile drawer + footer mini-cart)
- "Add to cart" buttons (card view + detail view)
- Status pills / inventory stamps ("In stock", "Sale")

**Wrong — matches multiple elements, Playwright throws:**
```typescript
await expect(page.getByText(/★.*4\.5/)).toBeVisible();
await expect(page.getByText("This field is required")).toBeVisible();
```

**Correct — use `.first()`, scope to a container, or use `data-testid`:**
```typescript
// Option A: .first() when the test only cares any instance exists
await expect(page.getByText(/★.*4\.5/).first()).toBeVisible();

// Option B: scope to the specific section under test
await expect(
  page.getByRole("article", { name: /product-detail/ }).getByText(/★.*4\.5/)
).toBeVisible();

// Option C: add data-testid to the element the test targets
await expect(page.getByTestId("product-detail-rating")).toBeVisible();
```

**The rule:** If a selector could plausibly match a cross-sell card, a related-products rail, or a mini-cart, add `.first()`, scope it, or use `data-testid`. Never rely on a bare text/role selector for any element that could appear more than once on a real page.

## Cross-Spec DB Pollution — Exact Counts Forbidden

Playwright runs specs alphabetically with a single worker under SQLite (required — see `Workers Must Be 1 with SQLite` above). The dev.db is reset + seeded **once per run**, before the first spec. Every spec after that inherits whatever rows earlier specs wrote. Any spec that calls `CREATE` actions — admin forms, factory helpers, fixtures — pollutes the row count seen by alphabetically-later specs.

This makes exact-count assertions against DB-backed listings fragile: a spec that passes in isolation can break when a sibling spec is added to the same suite months later.

**Wrong — passes alone, breaks when another spec adds products:**
```typescript
test("storefront shows all seeded products", async ({ page }) => {
  await page.goto("/products");
  const cards = page.getByTestId("product-card");
  await expect(cards).toHaveCount(6); // ← seed count; breaks if any other spec creates products
});
```

**Correct (preferred — works on all Playwright versions) — assert only seed rows by name:**
```typescript
test("storefront shows each seeded product by name", async ({ page }) => {
  await page.goto("/products");
  for (const name of ["Widget A", "Widget B", "Widget C"]) {
    await expect(page.getByTestId("product-card").filter({ hasText: name })).toBeVisible();
  }
});
```

**Also correct (Playwright ≥ 1.44) — `toHaveCount` with a minimum bound:**
```typescript
// Requires @playwright/test >= 1.44. The template ships 1.50+, so this is safe here.
test("storefront shows at least the seeded products", async ({ page }) => {
  await page.goto("/products");
  const cards = page.getByTestId("product-card");
  await expect(cards).toHaveCount({ min: 6 });
});
```

**Applicability:** Forbid `toHaveCount(N)` whenever the counted entity type is also written by any other spec in the same suite. Prefer the `.filter()` pattern when you care about *specific* rows — it is version-independent. Use `toHaveCount({ min: N })` only when the Playwright version is known to be ≥ 1.44. This applies to product listings, order history, admin lists, user directories — every page that reads a DB-backed collection.

## getByLabel Prefix Ambiguity — Require `exact: true`

`page.getByLabel("Foo")` uses **case-insensitive substring matching by default** when the argument is a plain string. Any label whose visible text contains `"Foo"` matches. When a form has labels like `"Description"` and `"Short Description"`, or `"Name"` and `"Display Name"`, or `"Price"` and `"Sale Price"`, the locator resolves to multiple elements and strict mode fires.

**Wrong — matches both `"Description"` and `"Short Description"`:**
```typescript
await page.getByLabel("Name").fill("Widget");
await page.getByLabel("Description").fill("A test product"); // ← strict-mode violation
await page.getByLabel("Short Description").fill("test");
```

**Correct — `{ exact: true }` on any label whose text is a substring of another:**
```typescript
await page.getByLabel("Name", { exact: true }).fill("Widget");
await page.getByLabel("Description", { exact: true }).fill("A test product");
await page.getByLabel("Short Description", { exact: true }).fill("test");
```

**Applicability:** Use `{ exact: true }` on every `getByLabel` call whose text is a prefix or suffix of another label on the same page. If unsure, default to `{ exact: true }` — there is no downside on labels that are already unique.

## `toHaveURL` Regex — Exclude Intermediate Routes

`toHaveURL(/\/admin/)` is a substring regex — it matches `/admin/login` immediately, long before the post-login redirect lands. Tests that wait on this assertion pass without the user ever being logged in, then fail downstream when the next action hits an unauthenticated API.

**Wrong — passes at `/admin/login` before the redirect:**
```typescript
await page.getByRole("button", { name: "Sign In" }).click();
await expect(page).toHaveURL(/\/admin/, { timeout: 15000 }); // ← matches /admin/login
await page.getByRole("link", { name: "Products" }).click(); // ← fails: not logged in
```

**Correct — negative lookahead excluding the login route:**
```typescript
await page.getByRole("button", { name: "Sign In" }).click();
await expect(page).toHaveURL(/\/admin(?!\/login)/, { timeout: 15000 });
```

**Also correct — anchor to a specific post-login path:**
```typescript
await page.getByRole("button", { name: "Sign In" }).click();
await expect(page).toHaveURL(/\/admin\/dashboard/, { timeout: 15000 });
```

**Applicability:** Use an exclusion pattern (negative lookahead) or anchor to a specific path whenever the target path has a login, setup, or onboarding sub-route sharing the same prefix. Never write a `toHaveURL` regex whose only constraint is "contains the protected prefix".

## `waitForURL` — Don't Use After Client-Side Navigation

Server Actions that call `router.push()` or `router.replace()` trigger client-side navigation. `page.waitForURL()` will timeout because no full page load event fires.

**Wrong — hangs after form submission with router.push():**
```typescript
await page.getByRole('button', { name: 'Save' }).click();
await page.waitForURL('/products');  // TIMEOUT — no "load" event
```

**Correct — poll-based URL assertion:**
```typescript
await page.getByRole('button', { name: 'Save' }).click();
await expect(page).toHaveURL(/\/products/, { timeout: 15000 });
```

**The rule:** After any form submission or action that uses `router.push()`/`redirect()`, use `expect(page).toHaveURL()` (which polls) instead of `page.waitForURL()` (which waits for a load event).

## `waitForURL` — Don't Use Locale-Only Patterns

`waitForURL` with a regex that matches the locale prefix alone will resolve as soon as the response hits *any* locale-prefixed URL — including the login page itself (`/hu/login`). The test then races forward before the actual redirect completes.

**Wrong — matches the login page too, resolves instantly:**
```typescript
await page.waitForURL(/\/hu\//);  // matches /hu/login AND /hu/account
```

**Correct — include the target path:**
```typescript
await page.waitForURL(/\/(hu|en)\/account/);
// or, exact final URL:
await page.waitForURL("**/account");
```

**The rule:** `waitForURL` patterns MUST include the target path, not just the locale prefix. If the test needs to wait for "any non-login page", use `waitForURL(url => !url.pathname.includes("/login"))`.

## shadcn/Radix Checkbox — Use `.click()`, Not `.check()`

shadcn/ui and Radix UI render checkboxes as `<button role="checkbox">` elements backed by state, not as native `<input type="checkbox">`. Playwright's `.check()` method targets native inputs and silently no-ops on the Radix version.

**Wrong — no-op on Radix checkbox:**
```typescript
await page.getByLabel("Only in stock").check();
```

**Correct — click the button:**
```typescript
await page.getByLabel("Only in stock").click();
// For assertions, use aria-checked (not .isChecked()):
await expect(page.getByLabel("Only in stock")).toHaveAttribute("aria-checked", "true");
```

**The rule:** For any form control from shadcn/ui, Radix, Headless UI, or similar state-driven component libraries, use `.click()` and assert via `aria-*` attributes. Reserve `.check()` for native `<input type="checkbox">`.

## Test Data MUST Come From Seed, Never Hardcoded

E2E tests that reference specific products, users, slugs, or IDs MUST source them from the seed data — never hardcode the values in the test file. When the seed changes (rename, locale flip, id reshuffle), hardcoded tests break after main merge even though nothing the test targets is broken.

**Wrong — hardcoded slug diverges from seed:**
```typescript
await page.goto(`/products/ethiopia-yirgacheffe`);  // seed uses a different slug
```

**Correct — import from a shared fixture derived from seed:**
```typescript
// tests/e2e/fixtures/seed-data.ts
import { prisma } from "@/lib/prisma";
export async function firstProductSlug() {
  const p = await prisma.product.findFirst({ orderBy: { createdAt: "asc" } });
  if (!p) throw new Error("seed did not create any products");
  return p.slug;
}

// tests/e2e/product.spec.ts
import { firstProductSlug } from "./fixtures/seed-data";
test("product detail", async ({ page }) => {
  const slug = await firstProductSlug();
  await page.goto(`/products/${slug}`);
});
```

Alternative: expose a `TEST_*` constant in `prisma/seed.ts` that the test imports directly. The point is a single source of truth.

**The rule:** No hardcoded slugs, emails, IDs, or titles in E2E tests. Either query the DB in a fixture helper, or import a named constant from the seed. When the seed changes, the test updates itself.

## i18n Smoke Check — Detect Raw Translation Keys

E2E tests that use `data-testid` selectors won't catch broken translations — the page renders with raw keys like `checkout_and_payment.step1.title` instead of translated text, but the test passes because the `data-testid` element exists.

Every E2E spec file MUST include at least one **i18n smoke assertion** that verifies actual translated text appears on the page and no raw namespace keys leak through:

```typescript
test("i18n smoke — no raw translation keys on page", async ({ page }) => {
  await page.goto("/hu/penztar");
  const body = await page.locator("body").innerText();
  // No raw namespace keys should appear in rendered text
  expect(body).not.toMatch(/\b\w+_and_\w+\.\w+\./);  // e.g. checkout_and_payment.step1.title
  expect(body).not.toMatch(/\b[a-z_]+\.[a-z_]+\.[a-z_]+/);  // e.g. admin_panel.sidebar.users
  // At least one expected translated string is present
  expect(body).toContain("Szállítás");  // or whatever the page's primary heading should be
});
```

**Why this matters:** The i18n sidecar merge can silently destroy translation namespaces (see deep-merge fix). Without a text-level assertion, a page can render entirely in raw keys and still pass all `data-testid` tests. One i18n smoke check per spec file catches this class of regression.

**The rule:** Every spec file must have at least one assertion that checks `innerText()` for raw key patterns. The regex `\b\w+_and_\w+\.\w+\.` catches the most common pattern (change-name-derived namespaces like `checkout_and_payment.step1.title`).

## `e2e-manifest.json` — Engine-Managed, Hands-Off

`e2e-manifest.json` at the project root is written and maintained by the orchestrator (dispatcher writes it on dispatch, verifier updates `spec_files` on completion). It holds cumulative REQ coverage and spec-file inventory across every merged change, plus a `requirements_by_change` map for per-change ownership.

**Agents MUST NOT edit `e2e-manifest.json` manually.** If a prior version of the agent touched it, that was a workaround for a dispatcher bug that is now fixed — hand-editing it today only risks re-introducing the same overwrite bug.

The in-change counterpart — your `messages/<locale>.<change>.json` i18n sidecars — follow the same "don't clobber other scopes" discipline: never overwrite a sidecar from a different change, and never reset one to `{}`.

## Hydration Race Conditions

Next.js dev server has known race conditions during E2E tests:

- **Route compilation returns HTML for API calls** — when a route is first accessed, the dev server compiles it. During compilation, API calls may receive an HTML response instead of JSON. Tests MUST retry API calls that receive non-JSON responses:
  ```typescript
  await expect(async () => {
    const res = await page.request.get('/api/data');
    expect(res.headers()['content-type']).toContain('json');
  }).toPass({ timeout: 10_000 });
  ```
- **Navigation to hydration-dependent pages** — use `waitUntil: 'networkidle'` when navigating to pages where the test immediately interacts with client-side elements (e.g., language switcher, add-to-cart button). Without this, the click fires before React hydration attaches the handler.
- **Language/locale switchers** — these MUST use `<Link>` with locale prop (renders `<a>` tag that works without JS), NOT `<button onClick>` with `router.replace()`. Under load, hydration delays leave buttons inert.
- **Playwright retries** — set `retries: 1` for local runs (not just CI) to handle transient hydration flakes. The template default is `process.env.CI ? 2 : 1`.

## Test-Only Endpoints

Test-only API routes (e.g., `/api/test-email-log` to inspect sent emails) need environment guards:

```typescript
// ✗ WRONG — Next.js dev server sets NODE_ENV=development, never "test"
if (process.env.NODE_ENV !== 'test') return NextResponse.json({ error: 'Not available' }, { status: 404 });

// ✓ CORRECT
if (process.env.NODE_ENV === 'production') return NextResponse.json({ error: 'Not available' }, { status: 404 });
```
