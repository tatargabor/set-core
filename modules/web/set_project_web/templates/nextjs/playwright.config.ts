import "dotenv/config";
import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.PW_PORT) || 3000;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 1 : undefined,
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
    reuseExistingServer: !process.env.CI,
    env: {
      ...process.env,
      NEXTAUTH_SECRET:
        process.env.NEXTAUTH_SECRET || "test-secret-for-e2e",
      NEXTAUTH_URL: `http://localhost:${port}`,
    },
  },
});
