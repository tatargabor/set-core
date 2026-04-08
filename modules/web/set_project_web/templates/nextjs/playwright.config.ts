import "dotenv/config";
import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.PW_PORT) || 3000;

// NEXTAUTH_SECRET MUST be provided by global-setup.ts or .env — no fallback.
// Fallback secrets violate security-patterns.md § 10 (allow stale cookies
// to bypass auth). global-setup.ts crashes loudly if it's missing.

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
