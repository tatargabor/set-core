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
  reporter: "html",
  use: {
    baseURL: `http://localhost:${port}`,
    headless: true,
    locale: "en-US",
    screenshot: "on",
    trace: "on-first-retry",
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
      NEXTAUTH_URL: `http://localhost:${port}`,
    },
  },
  globalSetup: "./tests/e2e/global-setup.ts",
});
