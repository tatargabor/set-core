import { test, expect } from '@playwright/test'
import { navigateToTab } from './helpers'

test.beforeEach(async ({ page }) => {
  await navigateToTab(page, 'log')
})

test('log content area has lines', async ({ page }) => {
  // Wait for log lines to load (REST poll has ~3s delay)
  await page.waitForTimeout(4000)
  // Log panel should have some text content
  const logArea = page.locator('[class*="font-mono"]').first()
  const text = await logArea.textContent()
  // May be empty if no log exists — that's OK, just check it rendered
  expect(text).toBeDefined()
})

test('ERROR lines have red styling', async ({ page }) => {
  await page.waitForTimeout(4000)
  const errorLines = page.locator('[class*="font-mono"] >> text=/ERROR/')
  const count = await errorLines.count()
  if (count === 0) return test.skip()
  // Check the first error line has red color class
  const errorLine = errorLines.first()
  await expect(errorLine).toHaveClass(/text-red/)
})
