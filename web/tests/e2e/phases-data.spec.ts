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
  // Find a change that depends on another change WITHIN the same phase
  const phaseMap = new Map<number, typeof changes>()
  for (const c of changes) {
    const p = c.phase ?? 1
    phaseMap.set(p, [...(phaseMap.get(p) ?? []), c])
  }
  let withIntraPhaseDep: typeof changes[0] | undefined
  for (const [, phaseChanges] of phaseMap) {
    const names = new Set(phaseChanges.map(c => c.name))
    withIntraPhaseDep = phaseChanges.find(c =>
      c.depends_on?.some(d => names.has(d))
    )
    if (withIntraPhaseDep) break
  }
  if (!withIntraPhaseDep) test.skip()

  // Wait for phases to render, then check for the └ connector
  await page.waitForSelector('text=Phase 1', { timeout: 5000 })
  const content = await page.content()
  expect(content).toContain('└')
})
