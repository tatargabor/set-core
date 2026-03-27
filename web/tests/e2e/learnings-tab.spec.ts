import { test, expect } from '@playwright/test'
import { navigateToTab, PROJECT } from './helpers'

test.beforeEach(async ({ page }) => {
  await navigateToTab(page, 'learnings')
})

test('gate stats section renders per-gate rows', async ({ page, request }) => {
  const res = await request.get(`/api/${PROJECT}/learnings`)
  const data = await res.json()
  const gates = Object.keys(data.gate_stats?.per_gate ?? {})
  if (gates.length === 0) return test.skip()

  // Wait for learnings to load
  await page.waitForTimeout(2000)
  for (const gate of gates) {
    await expect(page.locator(`text="${gate}"`).first()).toBeVisible()
  }
})

test('pass rate is a valid number', async ({ page, request }) => {
  const res = await request.get(`/api/${PROJECT}/learnings`)
  const data = await res.json()
  const gates = data.gate_stats?.per_gate ?? {}
  if (Object.keys(gates).length === 0) return test.skip()

  await page.waitForTimeout(2000)
  // Check that "NaN" does not appear in the learnings tab
  const content = await page.locator('[class*="overflow-auto"]').last().textContent()
  expect(content).not.toContain('NaN')
  expect(content).not.toContain('undefined')
})

test('reflections count displayed', async ({ page, request }) => {
  const res = await request.get(`/api/${PROJECT}/learnings`)
  const data = await res.json()
  const total = data.reflections?.total ?? 0
  if (total === 0) return test.skip()

  await page.waitForTimeout(2000)
  // The reflections count or "N reflections" should appear
  await expect(page.locator(`text=/${total}/`).first()).toBeVisible()
})
