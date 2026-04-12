import { test, expect } from '@playwright/test'
import { navigateToTab, PROJECT } from './helpers'

/**
 * Gate history sub-tabs — render per-run buttons inside gate output pane
 * when the change journal has multiple runs for a gate. When the journal is
 * empty or missing, the pane falls back to the legacy single-run view.
 *
 * Uses page.route() to mock the /journal endpoint so the test is portable
 * across any project — it doesn't depend on the live project actually having
 * multi-run journal data.
 */

test.beforeEach(async ({ page }) => {
  await navigateToTab(page, 'log')
})

test('Session tab label is present (renamed from Task)', async ({ page }) => {
  // Wait for LogPanel to render
  await page.waitForTimeout(2000)
  const sessionButton = page.locator('button', { hasText: 'Session' }).first()
  const exists = await sessionButton.count()
  // Legacy layouts may not have a selected change → skip
  if (exists === 0) test.skip()
  await expect(sessionButton).toBeVisible()
})

test('gate history sub-tabs render with mocked journal', async ({ page }) => {
  // Intercept the /journal endpoint and return a 3-run fixture
  await page.route(`**/api/${PROJECT}/changes/*/journal`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        entries: [],
        grouped: {
          e2e: [
            { run: 1, result: 'fail', output: 'run 1 failed', ts: '2026-04-12T10:00:00Z', ms: 1200 },
            { run: 2, result: 'fail', output: 'run 2 failed differently', ts: '2026-04-12T10:05:00Z', ms: 1500 },
            { run: 3, result: 'pass', output: 'run 3 passed', ts: '2026-04-12T10:10:00Z', ms: 900 },
          ],
        },
      }),
    })
  })

  // Reload to trigger the mocked fetch
  await page.reload()
  await page.waitForTimeout(2000)

  // Find any gate button in the sub-tab bar. If no change is selected, skip.
  const sessionBtn = page.locator('button', { hasText: 'Session' }).first()
  if ((await sessionBtn.count()) === 0) test.skip()

  const e2eBtn = page.locator('button', { hasText: /^E2E/ }).first()
  const e2eCount = await e2eBtn.count()
  if (e2eCount === 0) test.skip()

  await e2eBtn.click()
  await page.waitForTimeout(500)

  // Expect three run sub-tabs
  const run1 = page.locator('button', { hasText: /Run 1/ })
  const run2 = page.locator('button', { hasText: /Run 2/ })
  const run3 = page.locator('button', { hasText: /Run 3/ })
  await expect(run1).toBeVisible()
  await expect(run2).toBeVisible()
  await expect(run3).toBeVisible()

  // Click Run 2 and verify output changes
  await run2.click()
  await page.waitForTimeout(200)
  await expect(page.locator('pre', { hasText: 'run 2 failed differently' })).toBeVisible()
})

test('gate history falls back when journal is empty', async ({ page }) => {
  await page.route(`**/api/${PROJECT}/changes/*/journal`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ entries: [], grouped: {} }),
    })
  })

  await page.reload()
  await page.waitForTimeout(2000)

  const sessionBtn = page.locator('button', { hasText: 'Session' }).first()
  if ((await sessionBtn.count()) === 0) test.skip()

  // With empty grouped journal, no "Run N" buttons should be visible
  const run1 = page.locator('button', { hasText: /^Run 1/ })
  await expect(run1).toHaveCount(0)
})
