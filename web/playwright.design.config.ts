import { defineConfig } from '@playwright/test'

const APP_URL = process.env.E2E_DESIGN_URL || 'http://localhost:3200'

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'design-screenshots.spec.ts',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: APP_URL,
    screenshot: 'only-on-failure',
  },
})
