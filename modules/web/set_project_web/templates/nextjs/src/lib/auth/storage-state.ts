/**
 * Playwright storageState helpers for admin / privileged auth in e2e tests.
 *
 * Usage (projects using NextAuth Credentials provider):
 *
 *   // tests/e2e/admin.setup.ts
 *   import { test as setup } from '@playwright/test';
 *   import { createAdminStorageState } from '@/lib/auth/storage-state';
 *
 *   setup('authenticate as admin', async ({ page }) => {
 *     await createAdminStorageState(page, 'tests/e2e/.auth/admin.json');
 *   });
 *
 *   // playwright.config.ts — add a setup project that runs admin.setup.ts
 *   // and depends: ['setup'] on admin-scoped test projects.
 *
 * The helper is intentionally thin: it drives the `/login` form that the
 * Credentials provider exposes, then writes the browser's cookies +
 * localStorage snapshot to disk via `page.context().storageState({ path })`.
 * Projects with a custom login form can pass `options.selectors` to override
 * which fields to fill.
 */
import { Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { dirname } from "node:path";

export interface AdminStorageStateOptions {
  loginUrl?: string;
  email?: string;
  password?: string;
  selectors?: {
    email?: string;
    password?: string;
    submit?: string;
  };
  /** Path on the resulting page that proves we are signed in as admin. */
  verifyPath?: string;
  /** Locator that must be visible on the verify page (default: /admin dashboard). */
  verifyLocator?: string;
}

export async function createAdminStorageState(
  page: Page,
  storagePath: string,
  options: AdminStorageStateOptions = {},
): Promise<void> {
  const loginUrl = options.loginUrl ?? "/login";
  const email = options.email ?? process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
  const password = options.password ?? process.env.E2E_ADMIN_PASSWORD ?? "admin123";
  const emailSelector = options.selectors?.email ?? 'input[name="email"]';
  const passwordSelector = options.selectors?.password ?? 'input[name="password"]';
  const submitSelector = options.selectors?.submit ?? 'button[type="submit"]';
  const verifyPath = options.verifyPath ?? "/admin";
  const verifyLocator = options.verifyLocator ?? '[data-testid="admin-dashboard"], [data-testid="admin-sidebar"]';

  await page.goto(loginUrl);
  await page.locator(emailSelector).fill(email);
  await page.locator(passwordSelector).fill(password);
  await Promise.all([
    page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 30_000 }),
    page.locator(submitSelector).click(),
  ]);

  // Verify we actually landed as an admin. A wrong password silently lands on
  // a redirect-to-login loop; without verification the storageState would be
  // saved as an unauthenticated session and every admin test would fail.
  await page.goto(verifyPath);
  await page.locator(verifyLocator).first().waitFor({ state: "visible", timeout: 15_000 });

  await mkdir(dirname(storagePath), { recursive: true });
  await page.context().storageState({ path: storagePath });
}

/**
 * Convenience wrapper that builds the storageState file inline during a single
 * `test()` — use for one-off admin tests that don't want a separate setup project.
 */
export async function withAdminAuth<T>(
  page: Page,
  fn: () => Promise<T>,
  options?: AdminStorageStateOptions,
): Promise<T> {
  await createAdminStorageState(page, "tests/e2e/.auth/admin.json", options);
  return fn();
}
