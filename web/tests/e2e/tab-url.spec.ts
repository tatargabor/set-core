/**
 * The open tab is in the address bar, and the address bar opens that tab.
 *
 * Both directions, because either one alone is a half-feature: a URL that records the tab but
 * cannot restore it is a link that lies, and a URL that restores a tab it never writes is one
 * nobody can produce by using the product.
 *
 * Driven by real navigation and real clicks — the thing being tested is what a reader can copy
 * out of the browser and paste back into it, which no programmatic state change exercises.
 */
import { test, expect } from '@playwright/test'
import { PROJECT, settle } from './screens'

test('the tab a reader opens ends up in the URL', async ({ page }) => {
  await page.goto(`/p/${PROJECT}/status`)
  await settle(page, '[data-status-tab]')

  // Landing writes the tab it actually opened, so a copied link is never silent about it.
  await expect.poll(() => new URL(page.url()).searchParams.get('tab')).not.toBeNull()

  await page.locator('[data-status-tab="changes"]').first().click()
  await expect.poll(() => new URL(page.url()).searchParams.get('tab')).toBe('changes')
})

test('a URL naming a tab opens that tab', async ({ page }) => {
  await page.goto(`/p/${PROJECT}/status?tab=health`)
  await settle(page, '[data-status-tab]')

  const health = page.locator('[data-status-tab="health"]').first()
  await expect(health).toHaveAttribute('aria-selected', 'true')

  // …and it is the one actually rendered, not merely the one marked. A tab strip that
  // highlights one panel while showing another is the contradiction this surface forbids.
  //
  // Anchored BELOW the tab strip on purpose: every tab's name appears in the strip itself, so
  // asserting on the page as a whole would pass no matter which panel was open — a check that
  // cannot fail, dressed as one that verifies something.
  const panel = page.locator('[role="tablist"] ~ *').last()
  await expect(panel).toContainText('health')
  await expect(panel).not.toContainText('release-readiness')
})
