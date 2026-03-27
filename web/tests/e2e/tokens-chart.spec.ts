import { test, expect } from '@playwright/test'
import { navigateToTab, getApiState } from './helpers'

test.beforeEach(async ({ page }) => {
  await navigateToTab(page, 'tokens')
})

test('chart SVG renders', async ({ page }) => {
  // Recharts renders an SVG element
  await expect(page.locator('svg.recharts-surface').first()).toBeVisible()
})

test('chart has bars with height for projects with token data', async ({ page, request }) => {
  const state = await getApiState(request)
  const hasTokens = state.changes.some(c => (c.output_tokens ?? 0) > 0)
  if (!hasTokens) return test.skip()

  // Recharts renders rect elements for bars — various class names depending on version
  // Look for any rect inside the recharts container with non-zero dimensions
  const rects = page.locator('.recharts-surface rect[height]')
  const count = await rects.count()
  // Filter to rects with actual height > 0
  let nonZero = 0
  for (let i = 0; i < Math.min(count, 50); i++) {
    const h = await rects.nth(i).getAttribute('height')
    if (h && parseFloat(h) > 1) nonZero++
  }
  expect(nonZero).toBeGreaterThan(0)
})
