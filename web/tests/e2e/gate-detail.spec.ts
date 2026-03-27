import { test, expect } from '@playwright/test'
import { getApiState, navigateToTab, hasGates } from './helpers'

test.beforeEach(async ({ page }) => {
  await navigateToTab(page, 'changes')
})

test('clicking gate badges opens detail panel', async ({ page, request }) => {
  const state = await getApiState(request)
  const withGates = state.changes.find(c => hasGates(c))
  if (!withGates) return test.skip()

  const row = page.locator('tr', { hasText: withGates.name })
  const gateArea = row.locator('[title*=": pass"]').first()
  await gateArea.click()

  // A detail row should appear after the change row
  const detailRow = page.locator('tr').filter({ has: page.locator('td[colspan]') }).first()
  await expect(detailRow).toBeVisible()
})

test('clicking again collapses detail panel', async ({ page, request }) => {
  const state = await getApiState(request)
  const withGates = state.changes.find(c => hasGates(c))
  if (!withGates) return test.skip()

  const row = page.locator('tr', { hasText: withGates.name })
  const gateArea = row.locator('[title*=": pass"]').first()

  // Open
  await gateArea.click()
  const detailRow = page.locator('tr').filter({ has: page.locator('td[colspan]') }).first()
  await expect(detailRow).toBeVisible()

  // Close
  await gateArea.click()
  await expect(detailRow).not.toBeVisible()
})
