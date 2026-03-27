import { test, expect } from '@playwright/test'
import { getApiState, navigateToTab, hasGates, type ChangeInfo } from './helpers'

let changes: ChangeInfo[]

test.beforeAll(async ({ request }) => {
  const state = await getApiState(request)
  changes = state.changes
})

test.beforeEach(async ({ page }) => {
  await navigateToTab(page, 'phases')
})

test('at least one phase header visible', async ({ page }) => {
  // Phase headers contain "Phase N" text
  await expect(page.getByText('Phase 1')).toBeVisible()
})

test('phase header shows done/total count', async ({ page }) => {
  // Look for the "N/N" pattern in phase headers
  const phaseHeader = page.locator('text=/Phase \\d/').first().locator('..')
  await expect(phaseHeader.locator('text=/\\d+\\/\\d+/')).toBeVisible()
})

test('gate badges appear on phases tab', async ({ page }) => {
  const withGates = changes.find(c => hasGates(c))
  if (!withGates) return test.skip()
  // Gate badges should exist somewhere on the phases tab
  await expect(page.locator('[title*=": pass"]').first()).toBeVisible()
})

test('completed phase shows check icon', async ({ page }) => {
  // ✅ emoji for completed phases
  const allMerged = changes.every(c => ['merged', 'done', 'skipped'].includes(c.status))
  if (!allMerged) {
    // At least phase 1 should be completed if there are phase 2 changes
    const hasPhase2 = changes.some(c => (c.phase ?? 1) >= 2)
    if (!hasPhase2) return test.skip()
  }
  await expect(page.locator('text=✅').first()).toBeVisible()
})

test('child changes have indent', async ({ page }) => {
  const withDeps = changes.find(c => c.depends_on && c.depends_on.length > 0)
  if (!withDeps) return test.skip()
  // The ChangeRow uses paddingLeft for depth > 0 and renders "└" connector
  // Check the DOM for the connector character
  const content = await page.content()
  expect(content).toContain('└')
})
