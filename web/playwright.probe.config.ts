/**
 * Config for the design-review passes (layout probe + screenshot capture).
 *
 * Separate from `playwright.config.ts` because those two differ in the ways that matter here:
 * this one is serial (a shared page walked tab by tab), runs at the display's native 1920×1080
 * rather than a convenient 1280×720, and produces artifacts rather than assertions.
 *
 * The viewport is not cosmetic. Density, cramping and wasted space are exactly the properties
 * that change with the window, so measuring them at a size nobody uses answers a question
 * nobody asked.
 */
import { defineConfig } from '@playwright/test'

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:7400'

if (!process.env.E2E_PROJECT) {
  console.error('E2E_PROJECT is required — a registered project with data on the screens under review.')
  process.exit(1)
}

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: /(tab-url|row-open|side-scroll|flow-detail|layout-probe|design-review)\.spec\.ts/,
  timeout: 10 * 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: BASE_URL,
    viewport: { width: 1920, height: 1080 },
    screenshot: 'off',
    trace: 'off',
  },
})
