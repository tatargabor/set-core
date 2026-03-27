import { test, expect } from '@playwright/test'
import { getApiState, navigateToTab, hasGates } from './helpers'

test.beforeEach(async ({ page }) => {
  await navigateToTab(page, 'changes')
})

test('clicking gate badges opens detail panel', async ({ page, request }) => {
  const state = await getApiState(request)
  const withGates = state.changes.find(c => hasGates(c))
  if (!withGates) test.skip()

  const gateIcon = page.locator(`[title*=": pass"]`).first()
  if (!(await gateIcon.isVisible().catch(() => false))) test.skip()
  await gateIcon.click()

  // A detail row should appear after the change row
  const detailRow = page.locator('tr').filter({ has: page.locator('td[colspan]') }).first()
  await expect(detailRow).toBeVisible()
})

test('clicking again collapses detail panel', async ({ page, request }) => {
  const state = await getApiState(request)
  const withGates = state.changes.find(c => hasGates(c))
  if (!withGates) test.skip()

  const gateIcon = page.locator(`[title*=": pass"]`).first()
  if (!(await gateIcon.isVisible().catch(() => false))) test.skip()

  // Open
  await gateIcon.click()
  const detailRow = page.locator('tr').filter({ has: page.locator('td[colspan]') }).first()
  await expect(detailRow).toBeVisible()

  // Close
  await gateIcon.click()
  await expect(detailRow).not.toBeVisible()
})
