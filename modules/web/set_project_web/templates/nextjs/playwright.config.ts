import "dotenv/config";
import { randomBytes } from "node:crypto";
import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.PW_PORT) || 3000;

// NEXTAUTH_SECRET for the E2E webServer.
//
// This MUST be set at config load time (before `webServer.env` spreads
// process.env below) because globalSetup runs AFTER the webServer child
// process is spawned — too late for it to inherit the value.
//
// Precedence:
//   1. Real `.env` / `NEXTAUTH_SECRET` set in the environment (e.g. CI secret).
//   2. Otherwise: a cryptographically random secret generated per test run.
//
// Safe because playwright.config.ts is never loaded by production builds —
// it only runs when `npx playwright test` invokes it. This does NOT violate
// security-patterns.md § 10 (which bans fallbacks in *production* code).
if (!process.env.NEXTAUTH_SECRET) {
  process.env.NEXTAUTH_SECRET = randomBytes(32).toString("base64");
}

export default defineConfig({
  testDir: "./tests/e2e",
  // Single worker: SQLite has writer contention under concurrent connections,
  // and stateful auth tests reuse the same test user. Override only when the
  // app uses Postgres/MySQL with per-worker database isolation.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  // Per-test cap. 30s is enough for typical interactions; assertion-heavy
  // tests can override locally with test.setTimeout().
  timeout: 30_000,
  // Global suite cap. Sized for ~150-200 tests at ~3-5s each + login per
  // test (~3s) + webServer cold start (Next.js prod build can be 30s+) +
  // prisma seed. 1h gives ample headroom — the set-orch e2e gate timeout
  // is the outer kill switch (3600s default, see verifier.DEFAULT_E2E_TIMEOUT).
  globalTimeout: 3_600_000,
  reporter: "html",
  use: {
    baseURL: `http://localhost:${port}`,
    headless: true,
    locale: "en-US",
    screenshot: "on",
    trace: "on-first-retry",
    // Action and navigation defaults — Playwright's defaults (no timeout)
    // cause hung tests to consume globalTimeout instead of failing fast.
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: `npx next dev -p ${port}`,
    port,
    reuseExistingServer: false,
    env: {
      ...process.env,
      // NextAuth v4 (legacy) — kept for back-compat with apps still on v4.
      NEXTAUTH_URL: `http://localhost:${port}`,
      // NextAuth v5 (Auth.js) — required for the dynamic test ports
      // (3xxx/4xxx) the e2e gate assigns per worktree. Without these,
      // every /api/auth/* call throws `UntrustedHost`, which causes
      // auth-dependent tests to hang waiting for a session that never
      // arrives — the gate then hits its outer timeout. Setting both
      // here is safe: playwright.config.ts is never loaded in production.
      AUTH_URL: `http://localhost:${port}`,
      AUTH_TRUST_HOST: "true",
    },
  },
  globalSetup: "./tests/e2e/global-setup.ts",
});
