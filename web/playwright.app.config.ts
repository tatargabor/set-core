import { defineConfig } from '@playwright/test'

const APP_URL = process.env.E2E_APP_URL || 'http://localhost:3100'

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'app-screenshots.spec.ts',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false, // sequential — admin login state shared
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: APP_URL,
    screenshot: 'only-on-failure',
  },
})
