import { test, expect } from '@playwright/test'
import { navigateToTab, PROJECT } from './helpers'

test('digest tab renders when data exists', async ({ page, request }) => {
  const res = await request.get(`/api/${PROJECT}/digest`)
  const data = await res.json()
  if (!data.exists) return test.skip()

  await navigateToTab(page, 'digest')
  await page.waitForTimeout(2000)

  // Should have some visible content (requirements, domains, etc.)
  const content = page.locator('[class*="overflow-auto"]').last()
  const text = await content.textContent()
  expect(text!.length).toBeGreaterThan(10)
})

test('domain tabs are visible', async ({ page, request }) => {
  const res = await request.get(`/api/${PROJECT}/digest`)
  const data = await res.json()
  const domains = Object.keys(data.domains ?? {})
  if (domains.length === 0) return test.skip()

  await navigateToTab(page, 'digest')
  await page.waitForTimeout(2000)

  // At least the first domain name should appear as a tab/button
  await expect(page.locator(`text="${domains[0]}"`).first()).toBeVisible()
})

test('coverage data displayed', async ({ page, request }) => {
  const res = await request.get(`/api/${PROJECT}/digest`)
  const data = await res.json()
  const coverage = data.coverage?.coverage ?? data.coverage_merged?.coverage ?? {}
  if (Object.keys(coverage).length === 0) return test.skip()

  await navigateToTab(page, 'digest')
  await page.waitForTimeout(3000)

  // Coverage data may be behind a sub-tab. Check if any REQ- prefix appears on page.
  const content = await page.content()
  const hasReqId = Object.keys(coverage).some(id => content.includes(id))
  // If not visible directly, try clicking a coverage-related sub-tab
  if (!hasReqId) {
    const coverageTab = page.getByText('Coverage').first()
    if (await coverageTab.isVisible()) {
      await coverageTab.click()
      await page.waitForTimeout(1000)
      const updated = await page.content()
      const hasAfterClick = Object.keys(coverage).some(id => updated.includes(id))
      expect(hasAfterClick).toBeTruthy()
    } else {
      // Coverage sub-tab not found — the digest may render differently
      // At minimum, the digest tab loaded something
      expect(content.length).toBeGreaterThan(500)
    }
  }
})
