import { defineConfig } from '@playwright/test'

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:7400'

if (!process.env.E2E_PROJECT) {
  console.error('E2E_PROJECT env var is required. Set it to a registered project name with completed orchestration.')
  console.error('Example: E2E_PROJECT=minishop-run10 pnpm test:e2e')
  process.exit(1)
}

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  retries: 0,
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['list'],
  ],
  use: {
    baseURL: BASE_URL,
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },
})
