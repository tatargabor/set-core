import { test, expect } from '@playwright/test'
import { getApiState, navigateToTab, formatTokens, hasGates, type ChangeInfo } from './helpers'

let changes: ChangeInfo[]

test.beforeAll(async ({ request }) => {
  const state = await getApiState(request)
  changes = state.changes
})

test.beforeEach(async ({ page }) => {
  await navigateToTab(page, 'changes')
})

test('change row count matches API', async ({ page }) => {
  // Each change name should appear in the table
  for (const c of changes) {
    await expect(page.locator(`text="${c.name}"`).first()).toBeVisible()
  }
})

test('merged change with test_result=pass shows T badge', async ({ page }) => {
  const withTest = changes.find(c => c.test_result === 'pass')
  if (!withTest) return test.skip()
  const row = page.locator('tr', { hasText: withTest.name })
  await expect(row.locator('[title="test: pass"]')).toBeVisible()
})

test('merged change with build_result=pass shows B badge', async ({ page }) => {
  const withBuild = changes.find(c => c.build_result === 'pass')
  if (!withBuild) return test.skip()
  const row = page.locator('tr', { hasText: withBuild.name })
  await expect(row.locator('[title="build: pass"]')).toBeVisible()
})

test('merged change with smoke_result=pass shows S badge', async ({ page }) => {
  const withSmoke = changes.find(c => c.smoke_result === 'pass')
  if (!withSmoke) return test.skip()
  const row = page.locator('tr', { hasText: withSmoke.name })
  await expect(row.locator('[title="smoke: pass"]')).toBeVisible()
})

test('change with review_result=null has no R badge', async ({ page }) => {
  const noReview = changes.find(c => c.review_result == null && hasGates(c))
  if (!noReview) return test.skip()
  const row = page.locator('tr', { hasText: noReview.name })
  await expect(row.locator('[title*="review"]')).not.toBeVisible()
})

test('change with no gate results shows dash', async ({ page }) => {
  const noGates = changes.find(c => !hasGates(c))
  if (!noGates) return test.skip()
  const row = page.locator('tr', { hasText: noGates.name })
  // The GateBar renders "—" when no gates
  const gateCell = row.locator('td').nth(5)
  await expect(gateCell).toContainText('—')
})

test('merged change with tokens shows non-dash values', async ({ page }) => {
  const withTokens = changes.find(c => c.status === 'merged' && (c.output_tokens ?? 0) > 0)
  if (!withTokens) return test.skip()
  const row = page.locator('tr', { hasText: withTokens.name })
  const tokenCell = row.locator('td').nth(4)
  const text = await tokenCell.textContent()
  expect(text).not.toBe('—/—')
  expect(text).not.toBe('0/0')
})

test('session count displayed when present', async ({ page }) => {
  const withSessions = changes.find(c => (c.session_count ?? 0) > 0)
  if (!withSessions) return test.skip()
  const row = page.locator('tr', { hasText: withSessions.name })
  const sessCell = row.locator('td').nth(2)
  await expect(sessCell).toContainText(String(withSessions.session_count))
})

test('duration shows time format for completed changes', async ({ page }) => {
  const completed = changes.find(c => c.started_at && c.completed_at)
  if (!completed) return test.skip()
  const row = page.locator('tr', { hasText: completed.name })
  const durCell = row.locator('td').nth(3)
  const text = await durCell.textContent()
  // Should match Xm Ys or Xs pattern, not "—"
  expect(text).not.toBe('—')
  expect(text).toMatch(/\d+[ms]/)
})
