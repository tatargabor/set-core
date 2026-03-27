import { test, expect } from '@playwright/test'
import { getApiState, navigateToTab } from './helpers'

test.beforeEach(async ({ page }) => {
  await navigateToTab(page, 'changes')
})

test('merged change has no action buttons', async ({ page, request }) => {
  const state = await getApiState(request)
  const merged = state.changes.find(c => c.status === 'merged')
  if (!merged) return test.skip()

  const row = page.locator('tr', { hasText: merged.name })
  const actionCell = row.locator('td').last()
  // Should have no buttons
  const buttons = actionCell.locator('button')
  await expect(buttons).toHaveCount(0)
})

test('pending change shows Skip button', async ({ page, request }) => {
  const state = await getApiState(request)
  const pending = state.changes.find(c => c.status === 'pending')
  if (!pending) return test.skip()

  const row = page.locator('tr', { hasText: pending.name })
  await expect(row.locator('button', { hasText: 'Skip' })).toBeVisible()
})

test('running change shows Pause and Stop buttons', async ({ page, request }) => {
  const state = await getApiState(request)
  const running = state.changes.find(c =>
    ['running', 'verifying', 'implementing'].includes(c.status)
  )
  if (!running) return test.skip()

  const row = page.locator('tr', { hasText: running.name })
  await expect(row.locator('button', { hasText: 'Pause' })).toBeVisible()
  await expect(row.locator('button', { hasText: 'Stop' })).toBeVisible()
})
